"""Daily progress reports and execution measurement.

Approving a report verifies the quantity. It does not accept or certify it.
Accepted quantity comes from an approved quality inspection offer, or from
approved construction inspections when no offer has accepted the work. Billing
certification stays closed.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import update

from app.domains.coordination.service import (
    REVIEW_GUARDS,
    _close_tasks,
    _lock,
    _open_stage,
    current_stage,
    review_payload,
)
from app.domains.engineering_documents.models import Drawing, DrawingRevision
from app.domains.engineering_documents.workflow import submit_record
from app.domains.identity_projects.models import Discipline, ProjectDiscipline, User
from app.domains.identity_projects.security import permitted
from app.domains.supply_chain.models import StockPosting
from app.domains.supply_chain.service import _authority, _policy

from .connections import linked_posting, posting_reference
from .models import (
    ActivityMilestone,
    ConstructionActivity,
    ConstructionItem,
    ProgressLabour,
    ProgressLine,
    ProgressReport,
    WorkPackage,
    now,
)
from .service import _area, _company, _member, day, qty

PROGRESS = "construction.progress"
PIPELINE = {"Pending Review", "Approved"}
EDITABLE = {"Draft", "Returned for Correction"}
HELD = {"Draft", "Pending Review", "Returned for Correction", "Approved"}
QTY = Decimal("0.001")
WEIGHT = Decimal("0.01")
MANUAL = (
    "Crew, equipment, and material references are manual. "
    "No attendance, equipment, or stores record was created. "
    "A material reference is not proof of installation."
)
LINKED = (
    "Crew and equipment references are manual. No attendance or equipment record was created. "
    "The stores posting is a reference only and was not changed. "
    "A material issue is not proof of installation."
)
LABOUR_NOTE = (
    "Labour hours name HR personnel of the executing company who were mobilized on the report date. "
    "A person missing a qualification that HR lists as required for the activity is blocked, here and again on submit. "
    "They are activity hours, not attendance, and HR reconciles them to approved attendance once the report is approved."
)
DAY_MINUTES = 1440
ACCEPTED = "QA acceptance is not open. Approval of a daily report does not accept the work."
CERTIFIED = "Certified quantity is supplied by Billing and is not open."


def _q(value):
    return Decimal(value).quantize(QTY)


def _w(value):
    return Decimal(value).quantize(WEIGHT)


def _pct(part, whole):
    if whole is None or whole <= 0:
        return None
    return format((part / whole * Decimal("100")).quantize(WEIGHT), "f")


def _lines(db, report):
    return db.query(ProgressLine).filter_by(report_id=report.id).order_by(ProgressLine.id).all()


def _activity_lines(db, activity):
    return (
        db.query(ProgressLine, ProgressReport)
        .join(ProgressReport, ProgressReport.id == ProgressLine.report_id)
        .filter(ProgressLine.activity_id == activity.id, ProgressReport.status.in_(tuple(HELD)))
        .all()
    )


def _discipline(db, project, discipline_id):
    row = (
        db.query(ProjectDiscipline)
        .filter_by(project_id=project.id, discipline_id=discipline_id, active=True)
        .first()
    )
    discipline = db.get(Discipline, discipline_id)
    if not row or not discipline:
        raise HTTPException(422, "Discipline is not active on this project")
    return discipline


def _editable(report):
    if report.status == "Pending Review":
        raise HTTPException(409, "This daily report is in review")
    if report.status not in EDITABLE:
        raise HTTPException(409, "This daily report can no longer be edited")


def _bump(db, report, version, values):
    changed = db.execute(
        update(ProgressReport)
        .where(ProgressReport.id == report.id, ProgressReport.version == version)
        .values(version=version + 1, modified_at=now(), **values)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This daily report changed. Reload it and try again")
    db.refresh(report)


def _started(db, package, activity=None):
    if package.impact_state == "Review required":
        raise HTTPException(
            422,
            f"A drawing impact review is open on {package.code}. {package.impact_detail} "
            "The responsible engineer relinks or accepts it before more progress is recorded.",
        )
    if package.status == "On Hold":
        raise HTTPException(422, "This work package is on hold. Daily progress stays closed until work resumes")
    from app.domains.quality.findings import work_blocked

    if work_blocked(db, package, activity):
        raise HTTPException(422, "A quality hold blocks this work.")
    from app.domains.hse.field import field_block
    from app.domains.hse.permits import permit_block

    blocked = permit_block(db, package, activity)
    if blocked:
        raise HTTPException(422, blocked)
    blocked = field_block(db, package, activity)
    if blocked:
        raise HTTPException(422, blocked)
    from app.domains.hse.holds import raise_hold_block

    raise_hold_block(db, package, activity, 422)
    if package.status in {"Physically Complete", "Handed Over"}:
        raise HTTPException(422, "This work package is in handover. Daily progress stays closed")
    if package.status != "In Progress" or package.release_state != "Released":
        raise HTTPException(422, "Start the released work package before recording daily progress")


def _assigned(db, project, package, person, activity, on_date, status_code=409):
    """With a Mandatory Manpower check, labour needs a confirmed assignment on that activity and date."""
    from app.domains.manpower.models import Assignment

    from .models import ReadinessCheck

    rule = (
        db.query(ReadinessCheck)
        .filter_by(package_id=package.id, check_type="Manpower", classification="Mandatory")
        .first()
    )
    if not rule:
        return
    found = (
        db.query(Assignment)
        .filter_by(
            project_id=project.id,
            activity_id=activity.id,
            personnel_id=person.id,
            work_date=on_date,
            state="Confirmed",
        )
        .first()
    )
    if not found:
        raise HTTPException(
            status_code,
            f"{person.code} has no confirmed Manpower assignment on {activity.code} for {on_date.isoformat()}",
        )


def _revision(db, project, revision_id):
    if not revision_id:
        return None
    revision = db.get(DrawingRevision, revision_id)
    drawing = db.get(Drawing, revision.drawing_id) if revision else None
    if not revision or not drawing or drawing.project_id != project.id:
        raise HTTPException(422, "Drawing revision is not on this project")
    return revision


def save_milestones(db, project, activity, data):
    package = db.get(WorkPackage, activity.package_id)
    if not package or package.project_id != project.id:
        raise HTTPException(404, "Activity not found")
    if activity.measurement_method != "Weighted milestones":
        raise HTTPException(422, "Milestones apply only to a weighted-milestone activity")
    if any(report.status in PIPELINE or report.status == "Returned for Correction" for _line, report in _activity_lines(db, activity) if _line.milestone_id):
        raise HTTPException(409, "Milestone weights stay fixed once a claim is in review or approved")
    weights = [_w(row.weight) for row in data.milestones]
    if sum(weights, Decimal("0.00")) != Decimal("100.00"):
        raise HTTPException(422, "Milestone weights must total 100%")
    names = [row.name.strip() for row in data.milestones]
    if any(not name for name in names) or len({name.casefold() for name in names}) != len(names):
        raise HTTPException(422, "Each milestone needs its own name")
    db.query(ActivityMilestone).filter_by(activity_id=activity.id).delete()
    db.flush()
    for position, row in enumerate(data.milestones, start=1):
        db.add(
            ActivityMilestone(
                activity_id=activity.id,
                name=row.name.strip(),
                name_key=row.name.strip().casefold(),
                weight=_w(row.weight),
                position=position,
            )
        )
    db.flush()


def _milestones(db, activity):
    return (
        db.query(ActivityMilestone)
        .filter_by(activity_id=activity.id)
        .order_by(ActivityMilestone.position, ActivityMilestone.id)
        .all()
    )


def _weight_total(rows):
    return sum((_w(row.weight) for row in rows), Decimal("0.00"))


def _count_line(line, report, pending):
    if line.rework or report.status == "Cancelled" or report.status == "Rejected":
        return False
    if report.status == "Approved":
        return True
    return pending and report.status == "Pending Review"


def _accepted_line(db, activity):
    from app.domains.quality.models import QualityOffer, QualityOfferLine

    offer = (
        db.query(QualityOfferLine)
        .join(QualityOffer, QualityOffer.id == QualityOfferLine.offer_id)
        .filter(QualityOfferLine.activity_id == activity.id, QualityOffer.status == "Approved")
        .order_by(QualityOfferLine.id.desc())
        .first()
    )
    if offer and (offer.accepted_quantity is not None or offer.accepted_percent is not None):
        return offer
    from app.domains.quality.requests import construction_acceptance

    return construction_acceptance(db, activity)


def activity_measures(db, activity):
    package = db.get(WorkPackage, activity.package_id)
    milestones = _milestones(db, activity)
    scope = _q(activity.quantity)
    reported = Decimal("0.000")
    verified = Decimal("0.000")
    rework = Decimal("0.000")
    reported_weight = Decimal("0.00")
    verified_weight = Decimal("0.00")
    for line, report in _activity_lines(db, activity):
        if line.rework and line.quantity:
            rework += _q(line.quantity)
        if activity.measurement_method == "Weighted milestones":
            milestone = db.get(ActivityMilestone, line.milestone_id) if line.milestone_id else None
            if not milestone or line.rework:
                continue
            sign = Decimal("-1") if line.reverses_line_id else Decimal("1")
            if _count_line(line, report, pending=False):
                verified_weight += sign * _w(milestone.weight)
            if _count_line(line, report, pending=True):
                reported_weight += sign * _w(milestone.weight)
            continue
        if not line.quantity:
            continue
        amount = _q(line.quantity)
        sign = Decimal("-1") if line.reverses_line_id else Decimal("1")
        if line.rework:
            continue
        if _count_line(line, report, pending=False):
            verified += sign * amount
        if _count_line(line, report, pending=True):
            reported += sign * amount
    weighted = activity.measurement_method == "Weighted milestones"
    ready = weighted and _weight_total(milestones) == Decimal("100.00")
    accepted = _accepted_line(db, activity)
    accepted_quantity = qty(accepted.accepted_quantity) if accepted and accepted.accepted_quantity is not None else None
    accepted_percent = format(accepted.accepted_percent, "f") if accepted and accepted.accepted_percent is not None else None
    if accepted_quantity:
        accepted_note = (
            f"Accepted {accepted_quantity} {activity.unit}. "
            "This quality decision does not certify the work for billing."
        )
    elif accepted_percent:
        accepted_note = (
            f"Accepted {accepted_percent}% of the milestone weight. "
            "This quality decision does not certify the work for billing."
        )
    else:
        accepted_note = ACCEPTED
    if weighted:
        reported_percent = format(reported_weight, "f") if ready else None
        verified_percent = format(verified_weight, "f") if ready else None
        note = (
            f"Verified {verified_percent}% from approved milestones. {accepted_note} {CERTIFIED}"
            if ready
            else f"Verified progress is N/A until milestone weights total 100%. {accepted_note}"
        )
    else:
        reported_percent = _pct(reported, scope)
        verified_percent = _pct(verified, scope)
        shown = verified_percent if verified_percent is not None else "N/A"
        note = (
            f"Scope {qty(scope)} {activity.unit}. Reported {qty(reported)}. "
            f"Verified {qty(verified)} ({shown}%). {accepted_note} {CERTIFIED}"
        )
    return {
        "activity_id": activity.id,
        "activity_code": activity.code,
        "package_id": activity.package_id,
        "package_code": package.code if package else "",
        "package_status": package.status if package else "",
        "discipline_id": package.discipline_id if package else None,
        "area_id": package.area_id if package else None,
        "company_id": activity.company_id,
        "method": activity.measurement_method,
        "scope_quantity": None if weighted else qty(scope),
        "unit": "" if weighted else activity.unit,
        "reported_quantity": None if weighted else qty(reported),
        "verified_quantity": None if weighted else qty(verified),
        "rework_quantity": qty(rework),
        "accepted_quantity": accepted_quantity,
        "certified_quantity": None,
        "reported_percent": reported_percent,
        "verified_percent": verified_percent,
        "accepted_note": accepted_note,
        "certified_note": CERTIFIED,
        "note": note,
        "items": [
            {"id": item.id, "identifier": item.identifier}
            for item in db.query(ConstructionItem).filter_by(activity_id=activity.id, active=True)
        ],
        "milestones": [
            {"id": row.id, "name": row.name, "weight": format(_w(row.weight), "f")}
            for row in milestones
        ],
    }


def _duplicate_warnings(db, project, report):
    warnings = []
    seen = set()
    for line in _lines(db, report):
        if line.rework or line.reverses_line_id:
            continue
        key = (line.activity_id, line.item_id, line.milestone_id)
        if key in seen:
            warnings.append("This report repeats a work line")
        seen.add(key)
        others = (
            db.query(ProgressLine, ProgressReport)
            .join(ProgressReport, ProgressReport.id == ProgressLine.report_id)
            .filter(
                ProgressReport.project_id == project.id,
                ProgressReport.id != report.id,
                ProgressReport.report_date == report.report_date,
                ProgressReport.shift == report.shift,
                ProgressReport.status.in_(tuple(HELD)),
                ProgressLine.activity_id == line.activity_id,
                ProgressLine.rework.is_(False),
                ProgressLine.reverses_line_id.is_(None),
            )
            .all()
        )
        for other, _other_report in others:
            if other.item_id == line.item_id and other.milestone_id == line.milestone_id:
                warnings.append("Another report already has this work line for the same date and shift")
                break
    return list(dict.fromkeys(warnings))


def _scope_problem(db, activity, report):
    if activity.measurement_method == "Weighted milestones":
        return None
    measures_scope = _q(activity.quantity)
    reported = Decimal("0.000")
    for line, owner in _activity_lines(db, activity):
        if line.rework or not line.quantity:
            continue
        if owner.id != report.id and owner.status not in PIPELINE:
            continue
        if owner.id == report.id and owner.status in {"Rejected", "Cancelled"}:
            continue
        sign = Decimal("-1") if line.reverses_line_id else Decimal("1")
        if owner.id == report.id or owner.status == "Approved" or (
            owner.status == "Pending Review" and report.status in EDITABLE
        ):
            reported += sign * _q(line.quantity)
    if reported > measures_scope:
        return "This quantity exceeds the approved scope"
    return None


def _claim_taken(db, milestone_id, report, include_self=True):
    rows = (
        db.query(ProgressLine, ProgressReport)
        .join(ProgressReport, ProgressReport.id == ProgressLine.report_id)
        .filter(
            ProgressLine.milestone_id == milestone_id,
            ProgressLine.rework.is_(False),
            ProgressReport.status.in_(tuple(HELD)),
        )
        .all()
    )
    earned = 0
    for line, owner in rows:
        if owner.id == report.id and not include_self:
            continue
        if line.reverses_line_id:
            if owner.status == "Approved":
                earned -= 1
            continue
        earned += 1
    return earned > 0


def add_line(db, user, project, report, data):
    _editable(report)
    activity = db.get(ConstructionActivity, data.activity_id)
    package = db.get(WorkPackage, activity.package_id) if activity else None
    if not activity or activity.project_id != project.id or not activity.active or not package:
        raise HTTPException(422, "Activity is not on this project")
    _started(db, package, activity)
    if package.discipline_id != report.discipline_id or package.area_id != report.area_id:
        raise HTTPException(422, "Activity is outside this report's discipline and area")
    if activity.company_id != report.company_id:
        raise HTTPException(422, "Activity company does not match the executing company")
    _revision(db, project, data.drawing_revision_id)
    source = None
    milestone = None
    item = None
    quantity = _q(data.quantity) if data.quantity is not None else None
    if data.reverses_line_id:
        source_line = db.get(ProgressLine, data.reverses_line_id)
        source = db.get(ProgressReport, source_line.report_id) if source_line else None
        if (
            not source_line
            or not source
            or source.project_id != project.id
            or source.status != "Approved"
            or source_line.reverses_line_id
            or source_line.activity_id != activity.id
        ):
            raise HTTPException(422, "Choose an approved progress line on this activity to correct")
        if data.rework:
            raise HTTPException(422, "A correction is not rework")
        activity = db.get(ConstructionActivity, source_line.activity_id)
    if activity.measurement_method == "Weighted milestones":
        if data.reverses_line_id:
            milestone = db.get(ActivityMilestone, source_line.milestone_id)
            if not milestone:
                raise HTTPException(422, "Choose an approved progress line on this activity to correct")
            quantity = None
        else:
            milestone = db.get(ActivityMilestone, data.milestone_id) if data.milestone_id else None
            if not milestone or milestone.activity_id != activity.id:
                raise HTTPException(422, "Choose a milestone of this activity")
            if len(data.evidence.strip()) < 3:
                raise HTTPException(422, "Record the evidence for this milestone")
            if not data.rework and _claim_taken(db, milestone.id, report):
                raise HTTPException(422, "This milestone is already claimed")
            quantity = None
        if _weight_total(_milestones(db, activity)) != Decimal("100.00"):
            raise HTTPException(422, "Milestone weights must total 100%")
    else:
        if data.milestone_id:
            raise HTTPException(422, "This activity is not measured by milestones")
        if quantity is None:
            raise HTTPException(422, "Enter the quantity executed on this report")
        if activity.measurement_method == "Item completion":
            item = db.get(ConstructionItem, data.item_id) if data.item_id else None
            if not item or item.activity_id != activity.id or item.project_id != project.id or not item.active:
                raise HTTPException(422, "Choose the work item this completion refers to")
            if data.reverses_line_id and source_line.item_id != item.id:
                raise HTTPException(422, "Correct the same work item")
        elif data.item_id:
            item = db.get(ConstructionItem, data.item_id)
            if not item or item.activity_id != activity.id or not item.active:
                raise HTTPException(422, "Work item is not on this activity")
    if data.reverses_line_id and activity.measurement_method != "Weighted milestones":
        removed = quantity
        for line, owner in _activity_lines(db, activity):
            if line.reverses_line_id == source_line.id and line.quantity and owner.status in HELD:
                removed += _q(line.quantity)
        if removed > _q(source_line.quantity):
            raise HTTPException(422, "A correction cannot remove more than the verified quantity")
    posting = linked_posting(db, project, data.stock_posting_id)
    row = ProgressLine(
        report_id=report.id,
        activity_id=activity.id,
        item_id=item.id if item else (source_line.item_id if data.reverses_line_id else None),
        milestone_id=milestone.id if milestone else None,
        reverses_line_id=data.reverses_line_id,
        quantity=quantity,
        unit="" if activity.measurement_method == "Weighted milestones" else activity.unit,
        drawing_revision_id=data.drawing_revision_id,
        crew_reference=data.crew_reference.strip(),
        equipment_hours=data.equipment_hours,
        material_reference=data.material_reference.strip(),
        stock_posting_id=posting.id if posting else None,
        delay_reason=data.delay_reason.strip(),
        evidence=data.evidence.strip(),
        rework=data.rework,
        source_note=LINKED if posting else MANUAL,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    problem = _scope_problem(db, activity, report)
    if problem:
        db.rollback()
        raise HTTPException(422, problem)
    return row


def _problems(db, report):
    lines = _lines(db, report)
    if not lines:
        return ["Add the work performed on this report"]
    problems = []
    seen = set()
    for line in lines:
        activity = db.get(ConstructionActivity, line.activity_id)
        if activity.id not in seen:
            seen.add(activity.id)
            problem = _scope_problem(db, activity, report)
            if problem:
                problems.append(problem)
        if line.milestone_id and not line.rework and not line.reverses_line_id:
            others = [row for row in lines if row.milestone_id == line.milestone_id and not row.rework and not row.reverses_line_id]
            if len(others) > 1 or _claim_taken(db, line.milestone_id, report):
                # _claim_taken includes this report's own line, so a single claim returns True.
                pass
    return problems


def _prepare(db, project, report):
    lines = _lines(db, report)
    if not lines:
        raise HTTPException(422, "Add the work performed on this report")
    checked = set()
    for line in lines:
        activity = db.get(ConstructionActivity, line.activity_id)
        package = db.get(WorkPackage, activity.package_id)
        _started(db, package, activity)
        if line.milestone_id and not line.rework and not line.reverses_line_id:
            if _claim_taken(db, line.milestone_id, report, include_self=False):
                raise HTTPException(422, "This milestone is already claimed")
        if activity.id in checked:
            continue
        checked.add(activity.id)
        problem = _scope_problem(db, activity, report)
        if problem:
            raise HTTPException(422, problem)
    from app.domains.workforce.credentials import assert_eligible
    from app.domains.workforce.models import Personnel

    for entry in db.query(ProgressLabour).filter_by(report_id=report.id):
        line = db.get(ProgressLine, entry.line_id)
        activity = db.get(ConstructionActivity, line.activity_id)
        person = db.get(Personnel, entry.personnel_id)
        assert_eligible(db, project, person, report.report_date, activity, 422)
        _assigned(db, project, db.get(WorkPackage, activity.package_id), person, activity, report.report_date, 422)
    policy = _policy(db, project, PROGRESS, report.company_id, report.discipline_id)
    if not policy:
        raise HTTPException(422, "Mandatory reviewer configuration is missing")
    _authority(db, project, policy)
    return policy


def report_view(db, user, project, report):
    engineer = db.get(User, report.site_engineer_id)
    from app.domains.identity_projects.models import Area, Company

    company = db.get(Company, report.company_id)
    discipline = db.get(Discipline, report.discipline_id)
    area = db.get(Area, report.area_id)
    instance = _latest_review(db, project, report)
    lines = []
    for line in _lines(db, report):
        activity = db.get(ConstructionActivity, line.activity_id)
        item = db.get(ConstructionItem, line.item_id) if line.item_id else None
        milestone = db.get(ActivityMilestone, line.milestone_id) if line.milestone_id else None
        posting = db.get(StockPosting, line.stock_posting_id) if line.stock_posting_id else None
        lines.append(
            {
                "id": line.id,
                "activity_id": line.activity_id,
                "activity_code": activity.code if activity else "",
                "item_id": line.item_id,
                "item_identifier": item.identifier if item else "",
                "milestone_id": line.milestone_id,
                "milestone_name": milestone.name if milestone else "",
                "reverses_line_id": line.reverses_line_id,
                "quantity": qty(line.quantity) if line.quantity is not None else None,
                "unit": line.unit,
                "drawing_revision_id": line.drawing_revision_id,
                "crew_reference": line.crew_reference,
                "equipment_hours": format(line.equipment_hours, "f") if line.equipment_hours is not None else None,
                "material_reference": line.material_reference,
                "stock_posting_id": line.stock_posting_id,
                "stores": posting_reference(db, posting),
                "delay_reason": line.delay_reason,
                "evidence": line.evidence,
                "rework": line.rework,
                "source_note": line.source_note,
                "labour": _labour(db, line),
            }
        )
    return {
        "id": report.id,
        "number": report.number,
        "report_date": day(report.report_date),
        "shift": report.shift,
        "discipline_id": report.discipline_id,
        "discipline_name": discipline.name if discipline else "",
        "area_id": report.area_id,
        "area_name": area.name if area else "",
        "company_id": report.company_id,
        "company_name": company.name if company else "",
        "site_engineer_id": report.site_engineer_id,
        "site_engineer_name": engineer.name if engineer else "",
        "weather": report.weather,
        "remarks": report.remarks,
        "status": report.status,
        "cancellation_reason": report.cancellation_reason,
        "version": report.version,
        "lines": lines,
        "warnings": _duplicate_warnings(db, project, report),
        "review": review_payload(db, user, instance) if instance else None,
    }


def board(db, user, project):
    reports = (
        db.query(ProgressReport)
        .filter_by(project_id=project.id)
        .filter(ProgressReport.status != "Cancelled")
        .order_by(ProgressReport.report_date.desc(), ProgressReport.id.desc())
        .all()
    )
    activities = (
        db.query(ConstructionActivity)
        .filter_by(project_id=project.id, active=True)
        .order_by(ConstructionActivity.code)
        .all()
    )
    return {
        "reports": [report_view(db, user, project, report) for report in reports],
        "activities": [activity_measures(db, activity) for activity in activities],
        "labour_people": _labour_people(db, project),
        "labour_note": LABOUR_NOTE,
    }


def add_report(db, user, project, data):
    _discipline(db, project, data.discipline_id)
    _area(db, project, data.area_id)
    _company(db, project, data.company_id)
    _member(db, project, data.site_engineer_id, "the site engineer")
    key = data.number.strip().casefold()
    if db.query(ProgressReport).filter_by(project_id=project.id, number_key=key).first():
        raise HTTPException(409, "Report number already exists on this project")
    report = ProgressReport(
        organization_id=project.organization_id,
        project_id=project.id,
        number=data.number.strip(),
        number_key=key,
        report_date=data.report_date,
        shift=data.shift,
        discipline_id=data.discipline_id,
        area_id=data.area_id,
        company_id=data.company_id,
        site_engineer_id=data.site_engineer_id,
        weather=data.weather.strip(),
        remarks=data.remarks.strip(),
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(report)
    db.flush()
    return report


def save_report(db, user, project, report, data):
    _editable(report)
    _discipline(db, project, data.discipline_id)
    _area(db, project, data.area_id)
    _company(db, project, data.company_id)
    _member(db, project, data.site_engineer_id, "the site engineer")
    key = data.number.strip().casefold()
    taken = db.query(ProgressReport).filter_by(project_id=project.id, number_key=key).first()
    if taken and taken.id != report.id:
        raise HTTPException(409, "Report number already exists on this project")
    if _lines(db, report) and (
        data.discipline_id != report.discipline_id
        or data.area_id != report.area_id
        or data.company_id != report.company_id
    ):
        raise HTTPException(409, "Remove the work lines before changing discipline, area, or company")
    _bump(
        db,
        report,
        data.version,
        {
            "number": data.number.strip(),
            "number_key": key,
            "report_date": data.report_date,
            "shift": data.shift,
            "discipline_id": data.discipline_id,
            "area_id": data.area_id,
            "company_id": data.company_id,
            "site_engineer_id": data.site_engineer_id,
            "weather": data.weather.strip(),
            "remarks": data.remarks.strip(),
            "modified_by": user.id,
        },
    )
    return report


def remove_line(db, report, line):
    _editable(report)
    if line.report_id != report.id:
        raise HTTPException(404, "Progress line not found")
    db.query(ProgressLabour).filter_by(line_id=line.id).delete()
    db.delete(line)
    db.flush()


def _hm(minutes):
    return f"{minutes // 60}:{minutes % 60:02d}"


def add_labour(db, user, project, report, line, data):
    from app.domains.workforce.attendance import _attending_deployment
    from app.domains.workforce.models import Personnel

    _editable(report)
    if line.report_id != report.id:
        raise HTTPException(404, "Progress line not found")
    if line.reverses_line_id:
        raise HTTPException(422, "A correction line does not carry labour hours")
    person = db.get(Personnel, data.personnel_id)
    if not person or person.organization_id != project.organization_id:
        raise HTTPException(422, "Choose a person from the HR register")
    if person.company_id != report.company_id:
        raise HTTPException(422, "Labour must be personnel of the executing company")
    _attending_deployment(db, project, person, report.report_date)
    from app.domains.workforce.credentials import assert_eligible

    activity = db.get(ConstructionActivity, line.activity_id)
    assert_eligible(db, project, person, report.report_date, activity)
    _assigned(db, project, db.get(WorkPackage, activity.package_id), person, activity, report.report_date)
    total = data.productive_minutes + data.idle_minutes
    if total <= 0:
        raise HTTPException(422, "Enter productive or idle hours")
    if data.idle_minutes and len(data.idle_reason.strip()) < 3:
        raise HTTPException(422, "Give the reason for idle hours")
    if db.query(ProgressLabour).filter_by(line_id=line.id, personnel_id=person.id).first():
        raise HTTPException(409, "This person already has hours on this line")
    booked = sum(
        row.productive_minutes + row.idle_minutes
        for row in db.query(ProgressLabour)
        .join(ProgressReport, ProgressReport.id == ProgressLabour.report_id)
        .filter(
            ProgressLabour.personnel_id == person.id,
            ProgressReport.report_date == report.report_date,
            ProgressReport.status.in_(tuple(HELD)),
        )
    )
    if booked + total > DAY_MINUTES:
        raise HTTPException(409, f"{person.code} already has {_hm(booked)} booked on {report.report_date.isoformat()}; this would exceed 24 hours")
    row = ProgressLabour(
        report_id=report.id,
        line_id=line.id,
        personnel_id=person.id,
        productive_minutes=data.productive_minutes,
        idle_minutes=data.idle_minutes,
        idle_reason=data.idle_reason.strip(),
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def remove_labour(db, report, entry):
    _editable(report)
    if entry.report_id != report.id:
        raise HTTPException(404, "Labour entry not found")
    db.delete(entry)
    db.flush()


def _labour(db, line):
    from app.domains.workforce.models import Personnel

    rows = []
    for entry in db.query(ProgressLabour).filter_by(line_id=line.id).order_by(ProgressLabour.id):
        person = db.get(Personnel, entry.personnel_id)
        rows.append(
            {
                "id": entry.id,
                "personnel_id": entry.personnel_id,
                "person": f"{person.code} · {person.full_name}" if person else "",
                "productive": _hm(entry.productive_minutes),
                "idle": _hm(entry.idle_minutes),
                "idle_reason": entry.idle_reason,
            }
        )
    return rows


def _labour_people(db, project):
    from app.domains.workforce.attendance import ATTENDING_DEPLOYMENTS
    from app.domains.workforce.models import Deployment, Personnel

    people = {}
    for deployment, person in (
        db.query(Deployment, Personnel)
        .join(Personnel, Personnel.id == Deployment.personnel_id)
        .filter(Deployment.project_id == project.id, Deployment.status.in_(tuple(ATTENDING_DEPLOYMENTS)))
    ):
        if not deployment.actual_start:
            continue
        entry = people.setdefault(
            person.id,
            {"id": person.id, "name": f"{person.code} · {person.full_name}", "company_id": person.company_id, "windows": []},
        )
        entry["windows"].append([deployment.actual_start.isoformat(), deployment.actual_end.isoformat() if deployment.actual_end else None])
    return sorted(people.values(), key=lambda row: row["name"])


def cancel_report(db, user, report, data):
    if report.status == "Pending Review":
        raise HTTPException(409, "This daily report is in review")
    if report.status not in EDITABLE:
        raise HTTPException(409, "Only a draft daily report can be cancelled here")
    _bump(
        db,
        report,
        data.version,
        {"status": "Cancelled", "cancellation_reason": data.reason.strip(), "modified_by": user.id},
    )


def _latest_review(db, project, report):
    from app.domains.coordination.models import ReviewInstance

    return (
        db.query(ReviewInstance)
        .filter_by(project_id=project.id, record_type=PROGRESS, record_id=report.id)
        .order_by(ReviewInstance.id.desc())
        .first()
    )


def submit_report(db, user, project, report, version):
    if report.status == "Returned for Correction":
        raise HTTPException(409, "A returned daily report is resubmitted, not submitted again")
    if report.status == "Pending Review":
        raise HTTPException(409, "This daily report is already in review")
    if report.status != "Draft":
        raise HTTPException(409, "Only a draft daily report can be submitted")
    policy = _prepare(db, project, report)
    warnings = _duplicate_warnings(db, project, report)
    _bump(db, report, version, {"status": "Pending Review", "modified_by": user.id})
    instance = submit_record(db, user, project, PROGRESS, report.id, report.version, policy)
    return instance, warnings


def apply_resubmit(db, user, instance, review_version):
    from app.domains.identity_projects.models import Project

    if instance.state != "Returned":
        raise HTTPException(409, "Only a returned review can be resubmitted")
    if user.id != instance.submitted_by and not user.organization_admin:
        raise HTTPException(403, "Only the submitter can resubmit")
    project = db.get(Project, instance.project_id)
    report = db.get(ProgressReport, instance.record_id)
    if not project or not report or report.project_id != project.id:
        raise HTTPException(404, "Daily report not found")
    permitted(db, user, project, "construction.edit")
    if report.status != "Returned for Correction":
        raise HTTPException(409, "Only a returned daily report can be resubmitted")
    policy = _prepare(db, project, report)
    _lock(db, instance, review_version)
    _close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    _bump(db, report, report.version, {"status": "Pending Review", "modified_by": user.id})
    instance.record_version = report.version
    instance.policy_id = policy.id
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def on_review_event(db, user, instance, project, action, stage=None):
    if instance.record_type != PROGRESS:
        return
    report = db.get(ProgressReport, instance.record_id)
    if not report or report.project_id != project.id:
        return
    if action == "advance":
        return
    if action == "return":
        status = "Returned for Correction"
    elif action == "reject":
        status = "Rejected"
    elif instance.state == "Approved":
        status = "Approved"
    else:
        return
    report.status = status
    report.version += 1
    report.modified_by = user.id
    report.modified_at = now()


def review_guard(db, user, instance, stage, action):
    if instance.record_type != PROGRESS or action != "approve":
        return
    from app.domains.identity_projects.models import Project

    project = db.get(Project, instance.project_id)
    report = db.get(ProgressReport, instance.record_id)
    if not project or not report or report.project_id != project.id or report.status != "Pending Review":
        raise HTTPException(409, "This daily report is not awaiting review")
    try:
        _prepare(db, project, report)
    except HTTPException as exc:
        raise HTTPException(409, exc.detail) from exc


if review_guard not in REVIEW_GUARDS:
    REVIEW_GUARDS.append(review_guard)
