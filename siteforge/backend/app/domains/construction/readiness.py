"""Readiness checks and work-package release.

Drawing, material, manpower, permit, and quality-hold checks read the owning
module each time and return Ready, Blocked, or Pending. A typed note does not
satisfy them. Other checks record manual evidence, and only those can be marked
Not Applicable.
"""

from datetime import date
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
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import permitted
from app.domains.supply_chain.models import MaterialRequirement, ProcurementItem, RequirementLine
from app.domains.supply_chain.service import _amount, _authority, _policy
from app.domains.supply_chain.stock import package_stock

from .models import (
    ConstructionActivity,
    ConstructionPredecessor,
    ConstructionTemplate,
    ReadinessCheck,
    ReleaseSnapshot,
    WorkPackage,
    WorkPackageDrawing,
    WorkPackageRequirement,
    now,
)
from .service import _draft_package, _member, day, qty

RELEASE = "construction.release"
MANUAL = (
    "Manual evidence only. No inspection, permit, or schedule record was created."
)
OPEN_RELEASE = {"Not Submitted", "Rejected"}
MATERIAL_PENDING = (
    "No material requirement is linked. This check stays Pending until a requirement is linked. "
    "A typed note does not make material ready."
)
MATERIAL_CLOSED = {"Cancelled", "Rejected"}
CREW_PENDING = (
    "No active activity is due on this date. This check stays Pending until an activity is due "
    "and Manpower has confirmed people on it."
)
LIVE_TYPES = {"Drawing", "Material", "Material issue", "Manpower", "Permit", "Quality hold"}
STATE = {"ready": "Ready", "released": "Ready", "blocked": "Blocked", "pending": "Pending", "missing": "Pending"}


def validate_construction_policy(db, project, data):
    for stage in data.stages:
        ids = stage.reviewer_ids or [row.user_id for row in stage.reviewers]
        if not ids:
            raise HTTPException(422, "Mandatory reviewer configuration is missing")
        for user_id in ids:
            person = db.get(User, user_id)
            if not person or not person.active or person.organization_id != project.organization_id:
                raise HTTPException(422, "Choose an active project member as reviewer")
            from app.domains.identity_projects.models import Membership

            member = (
                db.query(Membership)
                .filter_by(project_id=project.id, user_id=user_id, active=True)
                .first()
            )
            if not member:
                raise HTTPException(422, f"{person.name} is not an active member of this project")


def drawing_gate(db, project, package):
    labels = []
    blocked = False
    for link in db.query(WorkPackageDrawing).filter_by(package_id=package.id):
        revision = db.get(DrawingRevision, link.revision_id)
        drawing = db.get(Drawing, revision.drawing_id) if revision else None
        if (
            not revision
            or not drawing
            or drawing.project_id != project.id
            or drawing.organization_id != project.organization_id
        ):
            blocked = True
            labels.append({"id": link.revision_id, "label": "Missing revision", "release_state": "Missing"})
            continue
        labels.append(
            {
                "id": revision.id,
                "label": f"{drawing.number} rev {revision.code}",
                "release_state": revision.release_state,
            }
        )
        if revision.release_state != "Released":
            blocked = True
    if not labels:
        return "missing", labels
    if blocked:
        return "blocked", labels
    return "released", labels


def material_gate(db, project, package, require_issue=False):
    links = db.query(WorkPackageRequirement).filter_by(package_id=package.id).all()
    if not links:
        return "pending", MATERIAL_PENDING, []
    from app.domains.quality.findings import issue_blocked

    reasons = []
    sources = []
    needed = {}
    ready = True
    for link in links:
        requirement = db.get(MaterialRequirement, link.requirement_id)
        if (
            not requirement
            or requirement.project_id != project.id
            or requirement.organization_id != project.organization_id
        ):
            ready = False
            reasons.append("A linked material requirement is not on this project.")
            continue
        if requirement.status in MATERIAL_CLOSED:
            ready = False
            reasons.append(f"{requirement.number} is {requirement.status}.")
            sources.append({"id": requirement.id, "number": requirement.number, "note": reasons[-1]})
            continue
        lines = (
            db.query(RequirementLine)
            .filter_by(requirement_id=requirement.id)
            .order_by(RequirementLine.position)
            .all()
        )
        if not lines:
            ready = False
            reasons.append(f"{requirement.number} has no required quantity.")
            sources.append({"id": requirement.id, "number": requirement.number, "note": reasons[-1]})
            continue
        for line in lines:
            item = db.get(ProcurementItem, line.item_id)
            code = item.code if item else "Item"
            needed[line.item_id] = needed.get(line.item_id, Decimal("0")) + _amount(line.quantity)
            required = needed[line.item_id]
            reserved, issued = package_stock(db, project.id, package.id, line.item_id)
            covered = reserved + issued
            short = covered < required or (require_issue and issued < required)
            hold = issue_blocked(db, project.id, line.item_id)
            if hold:
                note = f"{code} on {requirement.number} is under quality hold {hold.number}."
            elif covered < required:
                note = (
                    f"{code} on {requirement.number} needs {qty(required)} {line.unit} for {package.code}. "
                    f"Stores has {qty(reserved)} reserved and {qty(issued)} issued for this package. "
                    "Stock reserved for the project without a package is not counted."
                )
            elif require_issue and issued < required:
                note = (
                    f"{code} on {requirement.number} needs {qty(required)} {line.unit} issued before start. "
                    f"Stores has issued {qty(issued)} for {package.code}."
                )
            else:
                note = (
                    f"{code} on {requirement.number} has {qty(required)} {line.unit} "
                    f"{'issued' if require_issue else 'reserved or issued'} for {package.code}. "
                    "Quarantined and rejected stock is not counted. This check did not create a reservation."
                )
            if hold or short:
                ready = False
                reasons.append(note)
            sources.append(
                {
                    "id": requirement.id,
                    "number": requirement.number,
                    "item_code": code,
                    "required": qty(required),
                    "reserved": qty(reserved),
                    "issued": qty(issued),
                    "note": note,
                }
            )
    if ready:
        return "ready", " ".join(row["note"] for row in sources), sources
    return "blocked", " ".join(reasons), sources


def _due(activity, on_date):
    if activity.target_start and on_date < activity.target_start:
        return False
    if activity.target_finish and on_date > activity.target_finish:
        return False
    return True


def crew_date(package, on_date=None):
    today = date.today()
    return on_date or max(today, package.planned_start or today)


def crew_gate(db, project, package, on_date=None):
    """Confirmed Manpower assignments on each activity due on the date, rechecked now."""
    from app.domains.manpower.allocation import check
    from app.domains.manpower.models import Assignment
    from app.domains.workforce.models import Personnel, Shift

    on_date = crew_date(package, on_date)
    activities = [
        row
        for row in db.query(ConstructionActivity).filter_by(package_id=package.id, active=True)
        if _due(row, on_date)
    ]
    if not activities:
        return "pending", CREW_PENDING, []
    reasons, notes, sources = [], [], []
    for activity in activities:
        good = 0
        rows = db.query(Assignment).filter_by(
            project_id=project.id, activity_id=activity.id, work_date=on_date, state="Confirmed"
        )
        for row in rows:
            person = db.get(Personnel, row.personnel_id)
            shift = db.get(Shift, row.shift_id)
            problems, _deployment = check(
                db, project, person, activity, shift, on_date, row.planned_minutes, confirm=True, exclude_id=row.id
            )
            if problems:
                notes.append(f"{activity.code}: {person.code} {', '.join(problems)}.")
            else:
                good += 1
        if not good:
            reasons.append(f"{activity.code} has no confirmed, eligible people on {on_date.isoformat()}.")
        sources.append(
            {"activity_id": activity.id, "code": activity.code, "confirmed": good, "date": on_date.isoformat()}
        )
    if reasons:
        return "blocked", " ".join(reasons + notes), sources
    text = f"Every activity due on {on_date.isoformat()} has confirmed, eligible people from Manpower."
    return "ready", " ".join([text] + notes), sources


def _permit_live(db, package):
    from app.domains.hse.field import field_block
    from app.domains.hse.holds import hold_block
    from app.domains.hse.models import HsePermit
    from app.domains.hse.permits import permit_block, refresh_permit

    for message in (permit_block(db, package), field_block(db, package), hold_block(db, package)):
        if message:
            return "Blocked", message
    active = []
    for row in db.query(HsePermit).filter_by(project_id=package.project_id, package_id=package.id, activity_id=None):
        refresh_permit(db, row)
        if row.status == "Active":
            active.append(row.number)
    if active:
        return "Ready", (
            f"Active permit {', '.join(active)} covers this package. Field rules and safety holds were checked now."
        )
    return "Pending", (
        "No active permit covers the whole package. An activity permit does not cover the rest of the package."
    )


def _quality_live(db, package):
    from app.domains.quality.findings import release_blocked, work_blocked

    hold = work_blocked(db, package, None) or release_blocked(db, package)
    if hold:
        return "Blocked", f"Quality hold {hold.number} blocks this work."
    return "Ready", "No open quality hold blocks release or work on this package."


def live_result(db, project, package, row, on_date=None):
    """Current Ready, Blocked, Pending, or Not Applicable for one check, with its reason and owner."""
    if row.check_type == "Drawing":
        state, labels = drawing_gate(db, project, package)
        reason = _source_label(db, project, package, "Drawing")
        return {"state": STATE[state], "reason": reason, "owner": "Engineering", "sources": labels}
    if row.check_type in {"Material", "Material issue"}:
        state, reason, sources = material_gate(
            db, project, package, require_issue=row.check_type == "Material issue"
        )
        return {"state": STATE[state], "reason": reason, "owner": "Stores / Procurement", "sources": sources}
    if row.check_type == "Manpower":
        state, reason, sources = crew_gate(db, project, package, on_date)
        return {"state": STATE[state], "reason": reason, "owner": "Manpower", "sources": sources}
    if row.check_type == "Permit":
        state, reason = _permit_live(db, package)
        return {"state": state, "reason": reason, "owner": "HSE", "sources": []}
    if row.check_type == "Quality hold":
        state, reason = _quality_live(db, package)
        return {"state": state, "reason": reason, "owner": "QA/QC", "sources": []}
    owner = db.get(User, row.owner_user_id) if row.owner_user_id else None
    manual = {"Satisfied": "Ready", "Blocked": "Blocked", "Not Applicable": "Not Applicable"}
    return {
        "state": manual.get(row.status, "Pending"),
        "reason": row.evidence or MANUAL,
        "owner": owner.name if owner else "Check owner",
        "sources": [],
    }


def _source_label(db, project, package, check_type):
    if check_type == "Drawing":
        state, labels = drawing_gate(db, project, package)
        if state == "missing":
            return "No drawing revision is linked. This check cannot be satisfied until a released revision is linked."
        text = ", ".join(f"{row['label']} ({row['release_state']})" for row in labels)
        if state == "blocked":
            return f"{text}. A drawing that is not released cannot be marked satisfied."
        return text
    if check_type in {"Material", "Material issue"}:
        _state, reason, _sources = material_gate(
            db, project, package, require_issue=check_type == "Material issue"
        )
        return reason
    if check_type == "Manpower":
        _state, reason, _sources = crew_gate(db, project, package)
        return reason
    if check_type == "Permit":
        return _permit_live(db, package)[1]
    if check_type == "Quality hold":
        return _quality_live(db, package)[1]
    if check_type == "Predecessor":
        codes = []
        activities = db.query(ConstructionActivity).filter_by(package_id=package.id, active=True)
        for activity in activities:
            for link in db.query(ConstructionPredecessor).filter_by(activity_id=activity.id):
                earlier = db.get(ConstructionActivity, link.predecessor_id)
                if earlier:
                    codes.append(earlier.code)
        prefix = (
            f"Predecessor activities: {', '.join(codes)}. Accepted is not a status here. "
            if codes
            else "No predecessor is stored. "
        )
        return prefix + MANUAL
    return MANUAL


def _checks(db, package):
    return (
        db.query(ReadinessCheck)
        .filter_by(package_id=package.id)
        .order_by(ReadinessCheck.id)
        .all()
    )


def _check_row(db, project, package, row):
    owner = db.get(User, row.owner_user_id) if row.owner_user_id else None
    verifier = db.get(User, row.verified_by) if row.verified_by else None
    live = None
    live_material = None
    live_crew = None
    material_sources = []
    crew_sources = []
    label = row.source_label
    if row.check_type == "Drawing":
        state, _labels = drawing_gate(db, project, package)
        live = state
    if row.check_type in {"Material", "Material issue"}:
        live_material, label, material_sources = material_gate(
            db, project, package, require_issue=row.check_type == "Material issue"
        )
    if row.check_type == "Manpower":
        live_crew, label, crew_sources = crew_gate(db, project, package)
    current = live_result(db, project, package, row)
    if row.check_type in {"Permit", "Quality hold"}:
        label = current["reason"]
    return {
        "id": row.id,
        "check_type": row.check_type,
        "classification": row.classification,
        "source_label": label,
        "evidence": row.evidence,
        "owner_user_id": row.owner_user_id,
        "owner_name": owner.name if owner else "",
        "required_date": day(row.required_date),
        "status": row.status,
        "live_drawing": live,
        "live_material": live_material,
        "material_sources": material_sources,
        "live_crew": live_crew,
        "crew_sources": crew_sources,
        "live_state": current["state"],
        "live_reason": current["reason"],
        "live_owner": current["owner"],
        "verified_by": verifier.name if verifier else "",
        "verified_at": row.verified_at.isoformat() if row.verified_at else None,
        "version": row.version,
        "manual": row.check_type not in LIVE_TYPES,
    }


def _warnings(db, project, package, rows):
    out = []
    for row in rows:
        if row.classification != "Advisory":
            continue
        if row.check_type in LIVE_TYPES:
            result = live_result(db, project, package, row)
            if result["state"] != "Ready":
                out.append(f"{row.check_type} is {result['state']}: {result['reason']}")
        elif row.status not in {"Satisfied", "Not Applicable"}:
            out.append(f"{row.check_type} is {row.status}")
    return out


def _release_problems(db, project, package, rows, on_date=None):
    if not rows:
        return ["Add the applicable readiness checks"]
    if not package.responsible_user_id:
        return ["Choose the responsible engineer before release"]
    if not package.planned_start or not package.planned_finish:
        return ["Planned start and finish are required before release"]
    if package.planned_finish < package.planned_start:
        return ["Planned finish is before the start"]
    state, _labels = drawing_gate(db, project, package)
    if state == "blocked":
        return ["A linked drawing is no longer released"]
    material_state, material_reason, _sources = material_gate(db, project, package)
    if material_state == "blocked":
        return [material_reason]
    if material_state == "pending" and any(
        row.check_type == "Material" and row.classification == "Mandatory" for row in rows
    ):
        return [material_reason]
    for row in rows:
        if row.check_type == "Drawing" and row.status == "Satisfied" and state != "released":
            return ["A drawing check can be satisfied only when every linked revision is still Released"]
        if row.classification != "Mandatory":
            continue
        if row.check_type in LIVE_TYPES:
            result = live_result(db, project, package, row, on_date)
            if result["state"] != "Ready":
                return [f"{row.check_type}: {result['reason']}"]
        elif row.status not in {"Satisfied", "Not Applicable"}:
            return [f"{row.check_type} is mandatory and is not satisfied"]
    return []


def _snapshot(db, project, package, rows, warnings):
    _state, drawings = drawing_gate(db, project, package)
    _material_state, material_reason, requirements = material_gate(db, project, package)
    if not requirements and _material_state == "pending":
        requirements = [{"id": None, "number": "", "note": material_reason}]
    activities = []
    for activity in db.query(ConstructionActivity).filter_by(package_id=package.id, active=True):
        template = db.get(ConstructionTemplate, activity.template_id) if activity.template_id else None
        predecessors = []
        for link in db.query(ConstructionPredecessor).filter_by(activity_id=activity.id):
            earlier = db.get(ConstructionActivity, link.predecessor_id)
            if earlier:
                predecessors.append(earlier.code)
        activities.append(
            {
                "id": activity.id,
                "code": activity.code,
                "baseline_quantity": qty(activity.baseline_quantity),
                "quantity": qty(activity.quantity),
                "unit": activity.unit,
                "inspection_points": list(template.checkpoints) if template else [],
                "predecessor_codes": predecessors,
            }
        )
    engineer = db.get(User, package.responsible_user_id) if package.responsible_user_id else None
    return {
        "package_code": package.code,
        "package_version": package.version,
        "engineer_id": package.responsible_user_id,
        "engineer_name": engineer.name if engineer else "",
        "company_id": package.company_id,
        "planned_start": day(package.planned_start),
        "planned_finish": day(package.planned_finish),
        "drawings": drawings,
        "requirements": requirements,
        "activities": activities,
        "checks": [
            {
                "check_type": row.check_type,
                "classification": row.classification,
                "status": row.status,
                "evidence": row.evidence,
                "source_label": row.source_label,
                "live": live_result(db, project, package, row),
            }
            for row in rows
        ],
        "warnings": warnings,
        "manual_note": MANUAL,
    }


def _bump(db, package, version, values):
    changed = db.execute(
        update(WorkPackage)
        .where(WorkPackage.id == package.id, WorkPackage.version == version)
        .values(version=version + 1, modified_at=now(), **values)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This work package changed. Reload it and try again")
    db.refresh(package)


def _latest_review(db, project, package):
    from app.domains.coordination.models import ReviewInstance

    return (
        db.query(ReviewInstance)
        .filter_by(project_id=project.id, record_type=RELEASE, record_id=package.id)
        .order_by(ReviewInstance.id.desc())
        .first()
    )


def board(db, user, project):
    packages = (
        db.query(WorkPackage)
        .filter_by(project_id=project.id)
        .filter(WorkPackage.status != "Cancelled")
        .order_by(WorkPackage.code)
        .all()
    )
    return [package_view(db, user, project, package) for package in packages]


def package_view(db, user, project, package):
    from . import impact
    from .service import _package_row

    rows = _checks(db, package)
    instance = _latest_review(db, project, package)
    snapshot = (
        db.query(ReleaseSnapshot)
        .filter_by(package_id=package.id)
        .order_by(ReleaseSnapshot.id.desc())
        .first()
    )
    return {
        "package": _package_row(db, package),
        "checks": [_check_row(db, project, package, row) for row in rows],
        "warnings": _warnings(db, project, package, rows),
        "impact_choices": impact.choices(db, package),
        "problems": _release_problems(db, project, package, rows)
        if package.status == "Draft"
        else [],
        "review": review_payload(db, user, instance) if instance else None,
        "snapshot": snapshot.payload if snapshot else None,
    }


def add_check(db, user, project, package, data):
    _draft_package(package)
    if db.query(ReadinessCheck).filter_by(package_id=package.id, check_type=data.check_type).first():
        raise HTTPException(409, "That readiness check is already on this package")
    if data.owner_user_id:
        _member(db, project, data.owner_user_id, "the check owner")
    row = ReadinessCheck(
        package_id=package.id,
        check_type=data.check_type,
        classification=data.classification,
        source_label=_source_label(db, project, package, data.check_type),
        owner_user_id=data.owner_user_id,
        required_date=data.required_date,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def update_check(db, user, project, package, row, data):
    _draft_package(package)
    if row.package_id != package.id:
        raise HTTPException(404, "Readiness check not found")
    evidence = data.evidence.strip()
    if data.status == "Satisfied" and row.check_type == "Drawing":
        state, labels = drawing_gate(db, project, package)
        if state != "released":
            raise HTTPException(
                422,
                "A drawing check can be satisfied only when every linked revision is still Released",
            )
        row.source_label = ", ".join(row["label"] for row in labels)
    elif data.status == "Satisfied" and row.check_type in LIVE_TYPES:
        result = live_result(db, project, package, row)
        if result["state"] != "Ready":
            raise HTTPException(422, result["reason"])
        row.source_label = result["reason"]
    elif data.status == "Not Applicable":
        if row.check_type in LIVE_TYPES:
            raise HTTPException(422, "A check read from its owning module cannot be marked Not Applicable")
        if len(evidence) < 10:
            raise HTTPException(422, "Record who decided this check does not apply, and why")
    elif data.status == "Satisfied":
        if len(evidence) < 3:
            raise HTTPException(422, "Record the evidence before marking this check satisfied")
        row.source_label = _source_label(db, project, package, row.check_type)
    elif data.status == "Blocked" and len(evidence) < 3:
        raise HTTPException(422, "Record why this check is blocked")
    verified = data.status in {"Satisfied", "Blocked", "Not Applicable"}
    changed = db.execute(
        update(ReadinessCheck)
        .where(ReadinessCheck.id == row.id, ReadinessCheck.version == data.version)
        .values(
            status=data.status,
            evidence=evidence,
            source_label=row.source_label,
            verified_by=user.id if verified else None,
            verified_at=now() if verified else None,
            version=data.version + 1,
        )
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This readiness check changed. Reload it and try again")
    db.refresh(row)
    return row


def _open_release(db, user, project, package, policy, warnings, rows):
    instance = submit_record(db, user, project, RELEASE, package.id, package.version, policy)
    db.add(
        ReleaseSnapshot(
            package_id=package.id,
            review_id=instance.id,
            payload=_snapshot(db, project, package, rows, warnings),
            created_by=user.id,
        )
    )
    db.flush()
    return instance


def submit_release(db, user, project, package, version):
    from app.domains.quality.findings import release_blocked

    if release_blocked(db, package):
        raise HTTPException(409, "A quality hold blocks work release.")
    if package.release_state == "Returned":
        raise HTTPException(409, "A returned release is resubmitted, not submitted again")
    if package.release_state == "In Review":
        raise HTTPException(409, "This work package is already in release review")
    if package.status != "Draft" or package.release_state not in OPEN_RELEASE:
        raise HTTPException(409, "Only a draft work package can be submitted")
    rows = _checks(db, package)
    problems = _release_problems(db, project, package, rows)
    if problems:
        raise HTTPException(422, problems[0])
    policy = _policy(db, project, RELEASE, package.company_id, package.discipline_id)
    if not policy:
        raise HTTPException(422, "Mandatory reviewer configuration is missing")
    _authority(db, project, policy)
    warnings = _warnings(db, project, package, rows)
    _bump(db, package, version, {"release_state": "In Review", "modified_by": user.id})
    instance = _open_release(db, user, project, package, policy, warnings, rows)
    return instance, warnings


def apply_resubmit(db, user, instance, review_version):
    from app.domains.identity_projects.models import Project

    if instance.state != "Returned":
        raise HTTPException(409, "Only a returned review can be resubmitted")
    if user.id != instance.submitted_by and not user.organization_admin:
        raise HTTPException(403, "Only the submitter can resubmit")
    project = db.get(Project, instance.project_id)
    package = db.get(WorkPackage, instance.record_id)
    if not project or not package or package.project_id != project.id:
        raise HTTPException(404, "Work package not found")
    permitted(db, user, project, "construction.edit")
    if package.status != "Draft" or package.release_state != "Returned":
        raise HTTPException(409, "Only a returned draft can be resubmitted")
    rows = _checks(db, package)
    problems = _release_problems(db, project, package, rows)
    if problems:
        raise HTTPException(422, problems[0])
    policy = _policy(db, project, RELEASE, package.company_id, package.discipline_id)
    if not policy:
        raise HTTPException(422, "Mandatory reviewer configuration is missing")
    _authority(db, project, policy)
    warnings = _warnings(db, project, package, rows)
    _lock(db, instance, review_version)
    _close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    _bump(db, package, package.version, {"release_state": "In Review", "modified_by": user.id})
    instance.record_version = package.version
    _open_stage(db, user, project, instance, current_stage(db, instance))
    db.add(
        ReleaseSnapshot(
            package_id=package.id,
            review_id=instance.id,
            payload=_snapshot(db, project, package, rows, warnings),
            created_by=user.id,
        )
    )
    db.flush()
    return instance


def start_work(db, user, project, package, version):
    from app.domains.quality.findings import work_blocked

    if work_blocked(db, package, None):
        raise HTTPException(409, "A quality hold blocks this work.")
    from app.domains.hse.field import raise_field_block
    from app.domains.hse.permits import _raise_block

    _raise_block(db, package, None)
    raise_field_block(db, package, None)
    from app.domains.hse.holds import raise_hold_block

    raise_hold_block(db, package, None)
    if package.status != "Ready" or package.release_state != "Released":
        raise HTTPException(409, "Work can start only after the package is released")
    rows = _checks(db, package)
    problems = _release_problems(db, project, package, rows, date.today())
    if problems:
        raise HTTPException(409, problems[0])
    _bump(db, package, version, {"status": "In Progress", "modified_by": user.id})
    return package


def on_review_event(db, user, instance, project, action, stage=None):
    if instance.record_type != RELEASE:
        return
    package = db.get(WorkPackage, instance.record_id)
    if not package or package.project_id != project.id:
        return
    if action == "advance":
        return
    if action == "return":
        release_state = "Returned"
        status = package.status
    elif action == "reject":
        release_state = "Rejected"
        status = package.status
    elif instance.state == "Approved":
        release_state = "Released"
        status = "Ready"
    else:
        return
    package.status = status
    package.release_state = release_state
    package.version += 1
    package.modified_by = user.id
    package.modified_at = now()


def review_guard(db, user, instance, stage, action):
    if instance.record_type != RELEASE or action != "approve":
        return
    from app.domains.identity_projects.models import Project

    project = db.get(Project, instance.project_id)
    package = db.get(WorkPackage, instance.record_id)
    if not project or not package or package.project_id != project.id or package.release_state != "In Review":
        raise HTTPException(409, "This work package is not awaiting release")
    problems = _release_problems(db, project, package, _checks(db, package))
    if problems:
        raise HTTPException(409, problems[0])


if review_guard not in REVIEW_GUARDS:
    REVIEW_GUARDS.append(review_guard)
