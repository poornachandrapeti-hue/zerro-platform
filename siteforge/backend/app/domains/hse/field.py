"""Induction evidence, toolbox acknowledgments, and safety inspections.

A saved project rule decides when missing eligibility, a missing toolbox
acknowledgment, or an open finding blocks work. No rule means no block.
Medical detail is not stored. A verified HSE qualification kept in HR also
counts toward a category of the same name. A crew line is not attendance.
Closing a finding is not a safety-hold release.
"""

from datetime import datetime, timezone

from fastapi import HTTPException

from .models import (
    HseAssessment,
    HseDocument,
    HseEligibility,
    HseEligibilityRule,
    HseFinding,
    HseFindingRule,
    HseInspection,
    HseObservation,
    HsePermit,
    HseToolboxAck,
    HseToolboxRule,
    HseToolboxTalk,
    INSPECTION_TYPES,
    OBSERVATION_TYPES,
    SUGGESTED_ELIGIBILITY,
    now,
)
from .service import _bump

ELIGIBILITY_NOTE = (
    "This names a project member. Medical detail is not stored here. "
    "A verified HSE qualification kept in HR with the same name as the category also counts for a member whose login is linked to that HR person."
)
TOOLBOX_NOTE = "Attendance is an acknowledgment on this talk. A crew assignment is not attendance."
INSPECTION_NOTE = (
    "A finding blocks work only when a saved project rule names that severity. "
    "Closing the finding is not a safety-hold release."
)
OBSERVATION_NOTE = "An observation is a prompt report. It does not start an investigation."
FOLLOW_UP_NOTE = "Follow-up on this talk is not an action. Open Actions to record one."
ASSIGNED = {"Authorized", "Active", "Suspended"}


def _today():
    return datetime.now(timezone.utc).date()


def _aware(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _key(value):
    return value.strip().casefold()


def _scope_key(package_id, activity_id):
    return f"{package_id or 0}:{activity_id or 0}"


def _name(db, user_id):
    from app.domains.identity_projects.models import User

    person = db.get(User, user_id)
    return person.name if person else "This member"


def _helpers():
    from .service import _activity, _area, _company, _discipline, _member, _package

    return _company, _discipline, _area, _package, _activity, _member


def _scope(db, project, package_id, activity_id):
    _, _, _, package, activity, _member = _helpers()
    found = package(db, project, package_id)
    act = activity(db, found, activity_id)
    return found, act


def _matches(package_id, activity_id, package, activity):
    if package_id is None and activity_id is None:
        return True
    if package is None or package_id != package.id:
        return False
    if activity_id is None:
        return True
    return activity is not None and activity_id == activity.id


def refresh_eligibility(db, row):
    if row.status == "Verified" and row.expires_on and row.expires_on < _today():
        row.status = "Expired"
        row.modified_at = now()
        db.flush()
    return row


def _counts(row, on_date):
    if row.status == "Withdrawn" or not row.verified_by or not row.verified_at:
        return False
    if _aware(row.verified_at).date() > on_date:
        return False
    if row.expires_on and row.expires_on < on_date:
        return False
    return True


def eligible(db, project, member_id, category_key, on_date):
    rows = (
        db.query(HseEligibility)
        .filter_by(project_id=project.id, member_id=member_id, category_key=category_key)
        .all()
    )
    for row in rows:
        refresh_eligibility(db, row)
        if _counts(row, on_date):
            return True
    return hr_eligible(db, project, member_id, category_key, on_date)


def hr_eligible(db, project, member_id, category_key, on_date):
    from app.domains.workforce.credentials import hr_covers

    return hr_covers(db, project.organization_id, member_id, "HSE", on_date, category_key)


def _rules(db, project, package, activity):
    return [
        row
        for row in db.query(HseEligibilityRule).filter_by(project_id=project.id)
        if _matches(row.package_id, row.activity_id, package, activity)
    ]


def assert_assignment(db, project, package, activity, member_id, on_date):
    for rule in _rules(db, project, package, activity):
        if eligible(db, project, member_id, rule.category_key, on_date):
            continue
        raise HTTPException(
            409,
            f"{_name(db, member_id)} does not have verified {rule.category} evidence valid on {on_date.isoformat()}. This assignment stays blocked.",
        )


def _assigned_people(db, package, activity):
    people = []
    rows = db.query(HsePermit).filter_by(project_id=package.project_id, package_id=package.id).all()
    for row in rows:
        if row.status not in ASSIGNED:
            continue
        if activity is None and row.activity_id is not None:
            continue
        if activity is not None and row.activity_id not in {None, activity.id}:
            continue
        people.append(row.performing_authority_id)
    return people


def _toolbox_block(db, package, activity, on_date):
    rules = [
        row
        for row in db.query(HseToolboxRule).filter_by(project_id=package.project_id)
        if _matches(row.package_id, row.activity_id, package, activity)
    ]
    if not rules:
        return None
    talks = db.query(HseToolboxTalk).filter_by(project_id=package.project_id, status="Held", talk_on=on_date).all()
    for rule in rules:
        satisfied = False
        for talk in talks:
            if not db.query(HseToolboxAck).filter_by(talk_id=talk.id).first():
                continue
            if talk.package_id is None and talk.activity_id is None:
                satisfied = True
                break
            if rule.package_id is None and rule.activity_id is None:
                continue
            if talk.package_id != rule.package_id:
                continue
            if talk.activity_id is None or talk.activity_id == rule.activity_id:
                satisfied = True
                break
        if not satisfied:
            return (
                "Toolbox evidence is required before this work. Record a held talk for this date and an attendance acknowledgment. "
                "A crew assignment is not attendance."
            )
    return None


def _finding_block(db, package, activity):
    rules = {
        row.severity_key: row.severity
        for row in db.query(HseFindingRule).filter_by(project_id=package.project_id, blocks_work=True)
    }
    if not rules:
        return None
    inspections = db.query(HseInspection).filter_by(project_id=package.project_id, package_id=package.id).all()
    for inspection in inspections:
        if activity is None and inspection.activity_id is not None:
            continue
        if activity is not None and inspection.activity_id not in {None, activity.id}:
            continue
        findings = db.query(HseFinding).filter_by(inspection_id=inspection.id, status="Open").all()
        for finding in findings:
            if finding.severity_key not in rules:
                continue
            return (
                f"Finding on inspection {inspection.number} is open at severity {finding.severity}. "
                "The saved project rule blocks this work until that finding is closed. This is not a safety-hold record."
            )
    return None


def field_block(db, package, activity=None, on_date=None):
    on_date = on_date or _today()
    finding = _finding_block(db, package, activity)
    if finding:
        return finding
    toolbox = _toolbox_block(db, package, activity, on_date)
    if toolbox:
        return toolbox
    project = _project(db, package)
    for rule in _rules(db, project, package, activity):
        for member_id in _assigned_people(db, package, activity):
            if eligible(db, project, member_id, rule.category_key, on_date):
                continue
            return (
                f"{_name(db, member_id)} is assigned to this work without verified {rule.category} evidence valid on {on_date.isoformat()}."
            )
    return None


def _project(db, package):
    from app.domains.identity_projects.models import Project

    return db.get(Project, package.project_id)


def raise_field_block(db, package, activity=None, status_code=409):
    message = field_block(db, package, activity)
    if message:
        raise HTTPException(status_code, message)


def work_note(db, package):
    return {
        "field_block": field_block(db, package, None) or "",
        "field_note": f"{ELIGIBILITY_NOTE} {TOOLBOX_NOTE} {INSPECTION_NOTE}",
    }


def _rule_view(row):
    return {
        "id": row.id,
        "category": getattr(row, "category", ""),
        "severity": getattr(row, "severity", ""),
        "package_id": row.package_id,
        "activity_id": row.activity_id,
        "blocks_work": getattr(row, "blocks_work", False),
    }


def _eligibility_view(db, row):
    refresh_eligibility(db, row)
    return {
        "id": row.id,
        "member_id": row.member_id,
        "member_name": _name(db, row.member_id),
        "category": row.category,
        "evidence": row.evidence,
        "expires_on": row.expires_on.isoformat() if row.expires_on else None,
        "status": row.status,
        "version": row.version,
        "statement": ELIGIBILITY_NOTE,
    }


def _talk_view(db, row):
    acks = db.query(HseToolboxAck).filter_by(talk_id=row.id).all()
    return {
        "id": row.id,
        "number": row.number,
        "talk_on": row.talk_on.isoformat(),
        "shift": row.shift,
        "topic": row.topic,
        "status": row.status,
        "package_id": row.package_id,
        "activity_id": row.activity_id,
        "presenter_name": _name(db, row.presenter_id),
        "issues": row.issues,
        "follow_up": row.follow_up,
        "attachment_reference": row.attachment_reference,
        "version": row.version,
        "acknowledgments": [{"id": ack.id, "member_id": ack.member_id, "member_name": _name(db, ack.member_id), "evidence": ack.evidence} for ack in acks],
        "statement": TOOLBOX_NOTE,
        "follow_up_note": FOLLOW_UP_NOTE,
    }


def _finding_view(db, row):
    return {
        "id": row.id,
        "description": row.description,
        "severity": row.severity,
        "owner_name": _name(db, row.owner_id),
        "target_on": row.target_on.isoformat() if row.target_on else None,
        "action": row.action,
        "photo_reference": row.photo_reference,
        "status": row.status,
        "close_evidence": row.close_evidence,
        "version": row.version,
    }


def _inspection_view(db, row):
    findings = db.query(HseFinding).filter_by(inspection_id=row.id).order_by(HseFinding.id).all()
    return {
        "id": row.id,
        "number": row.number,
        "inspection_type": row.inspection_type,
        "inspector_name": _name(db, row.inspector_id),
        "inspected_on": row.inspected_on.isoformat(),
        "package_id": row.package_id,
        "activity_id": row.activity_id,
        "status": row.status,
        "version": row.version,
        "findings": [_finding_view(db, item) for item in findings],
        "statement": INSPECTION_NOTE,
    }


def _observation_view(db, row):
    return {
        "id": row.id,
        "number": row.number,
        "observation_type": row.observation_type,
        "description": row.description,
        "evidence": row.evidence,
        "reporter_name": _name(db, row.reporter_id),
        "status": row.status,
        "statement": OBSERVATION_NOTE,
    }


def _gaps(db, project):
    from app.domains.identity_projects.models import Membership, User

    members = []
    seen = set()
    for membership in db.query(Membership).filter_by(project_id=project.id, active=True):
        if membership.user_id in seen:
            continue
        person = db.get(User, membership.user_id)
        if person and person.active:
            seen.add(person.id)
            members.append(person)
    gaps = []
    rules = db.query(HseEligibilityRule).filter_by(project_id=project.id).all()
    for rule in rules:
        if rule.package_id is None and rule.activity_id is None:
            subjects = members
        else:
            from app.domains.construction.models import ConstructionActivity, WorkPackage

            package = db.get(WorkPackage, rule.package_id) if rule.package_id else None
            activity = db.get(ConstructionActivity, rule.activity_id) if rule.activity_id else None
            subjects = [db.get(User, member_id) for member_id in _assigned_people(db, package, activity)] if package else []
        for person in subjects:
            if not person:
                continue
            rows = db.query(HseEligibility).filter_by(project_id=project.id, member_id=person.id, category_key=rule.category_key).all()
            for row in rows:
                refresh_eligibility(db, row)
            if any(_counts(row, _today()) for row in rows) or hr_eligible(db, project, person.id, rule.category_key, _today()):
                continue
            reason = "Expired" if any(row.status == "Expired" for row in rows) else "Missing"
            gaps.append({"member_id": person.id, "member_name": person.name, "category": rule.category, "reason": reason})
    return gaps


def supplement(db, user, project, payload):
    for row in db.query(HseEligibility).filter_by(project_id=project.id):
        refresh_eligibility(db, row)
    eligibility = db.query(HseEligibility).filter_by(project_id=project.id).order_by(HseEligibility.id.desc()).all()
    talks = db.query(HseToolboxTalk).filter_by(project_id=project.id).order_by(HseToolboxTalk.id.desc()).all()
    inspections = db.query(HseInspection).filter_by(project_id=project.id).order_by(HseInspection.id.desc()).all()
    observations = db.query(HseObservation).filter_by(project_id=project.id).order_by(HseObservation.id.desc()).all()
    open_findings = 0
    for inspection in inspections:
        open_findings += db.query(HseFinding).filter_by(inspection_id=inspection.id, status="Open").count()
    gaps = _gaps(db, project)
    payload["eligibility_note"] = ELIGIBILITY_NOTE
    payload["toolbox_note"] = TOOLBOX_NOTE
    payload["inspection_note"] = INSPECTION_NOTE
    payload["observation_note"] = OBSERVATION_NOTE
    payload["follow_up_note"] = FOLLOW_UP_NOTE
    payload["suggested_eligibility"] = list(SUGGESTED_ELIGIBILITY)
    payload["inspection_types"] = list(INSPECTION_TYPES)
    payload["observation_types"] = list(OBSERVATION_TYPES)
    payload["eligibility_rules"] = [_rule_view(row) for row in db.query(HseEligibilityRule).filter_by(project_id=project.id)]
    payload["eligibility"] = [_eligibility_view(db, row) for row in eligibility]
    payload["gaps"] = gaps
    payload["toolbox_rules"] = [_rule_view(row) for row in db.query(HseToolboxRule).filter_by(project_id=project.id)]
    payload["talks"] = [_talk_view(db, row) for row in talks]
    payload["finding_rules"] = [_rule_view(row) for row in db.query(HseFindingRule).filter_by(project_id=project.id)]
    payload["inspections"] = [_inspection_view(db, row) for row in inspections]
    payload["observations"] = [_observation_view(db, row) for row in observations]
    payload["counts"]["eligibility_gaps"] = len(gaps)
    payload["counts"]["talks"] = len(talks)
    payload["counts"]["open_findings"] = open_findings
    payload["counts"]["observations"] = len(observations)
    return payload


def add_eligibility_rule(db, user, project, data):
    package, activity = _scope(db, project, data.package_id, data.activity_id)
    key = _key(data.category)
    scope = _scope_key(package.id if package else None, activity.id if activity else None)
    if db.query(HseEligibilityRule).filter_by(project_id=project.id, category_key=key, scope_key=scope).first():
        raise HTTPException(409, "That eligibility rule already exists")
    row = HseEligibilityRule(
        organization_id=project.organization_id,
        project_id=project.id,
        category=data.category.strip(),
        category_key=key,
        package_id=package.id if package else None,
        activity_id=activity.id if activity else None,
        scope_key=scope,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def add_eligibility(db, user, project, data):
    _, _, _, _, _, member = _helpers()
    member(db, project, data.member_id, "person")
    row = HseEligibility(
        organization_id=project.organization_id,
        project_id=project.id,
        member_id=data.member_id,
        category=data.category.strip(),
        category_key=_key(data.category),
        evidence=data.evidence.strip(),
        expires_on=data.expires_on,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def verify_eligibility(db, user, project, row, version):
    if row.project_id != project.id:
        raise HTTPException(404, "Eligibility record not found")
    if user.id == row.member_id:
        raise HTTPException(403, "You cannot verify your own eligibility")
    if row.status == "Withdrawn":
        raise HTTPException(409, "A withdrawn record stays on file")
    if row.status == "Verified":
        raise HTTPException(409, "This evidence is already verified")
    _bump(db, HseEligibility, row, version, {"status": "Verified", "verified_by": user.id, "verified_at": now()})
    refresh_eligibility(db, row)
    return row


def withdraw_eligibility(db, user, project, row, data):
    if row.status == "Withdrawn":
        raise HTTPException(409, "This evidence is already withdrawn")
    _bump(db, HseEligibility, row, data.version, {"status": "Withdrawn", "withdrawal_reason": data.reason.strip()})
    return row


def add_toolbox_rule(db, user, project, data):
    package, activity = _scope(db, project, data.package_id, data.activity_id)
    scope = _scope_key(package.id if package else None, activity.id if activity else None)
    if db.query(HseToolboxRule).filter_by(project_id=project.id, scope_key=scope).first():
        raise HTTPException(409, "That toolbox rule already exists")
    row = HseToolboxRule(
        organization_id=project.organization_id,
        project_id=project.id,
        package_id=package.id if package else None,
        activity_id=activity.id if activity else None,
        scope_key=scope,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def add_talk(db, user, project, data):
    company, _, area, package, activity, member = _helpers()
    company(db, project, data.company_id)
    area(db, project, data.area_id)
    found = package(db, project, data.package_id)
    activity(db, found, data.activity_id)
    member(db, project, data.presenter_id, "presenter")
    if data.assessment_id:
        assessment = db.get(HseAssessment, data.assessment_id)
        if not assessment or assessment.project_id != project.id:
            raise HTTPException(422, "Choose a risk assessment on this project")
    if data.permit_id:
        permit = db.get(HsePermit, data.permit_id)
        if not permit or permit.project_id != project.id:
            raise HTTPException(422, "Choose a permit on this project")
    number_key = _key(data.number)
    if db.query(HseToolboxTalk).filter_by(project_id=project.id, number_key=number_key).first():
        raise HTTPException(409, "That talk number already exists")
    row = HseToolboxTalk(
        organization_id=project.organization_id,
        project_id=project.id,
        number=data.number.strip(),
        number_key=number_key,
        talk_on=data.talk_on,
        shift=data.shift.strip(),
        company_id=data.company_id,
        area_id=data.area_id,
        package_id=data.package_id,
        activity_id=data.activity_id,
        topic=data.topic.strip(),
        assessment_id=data.assessment_id,
        permit_id=data.permit_id,
        presenter_id=data.presenter_id,
        issues=data.issues.strip(),
        follow_up=data.follow_up.strip(),
        attachment_reference=data.attachment_reference.strip(),
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def hold_talk(db, row, version):
    if row.status != "Draft":
        raise HTTPException(409, "Only a draft talk can be marked held")
    _bump(db, HseToolboxTalk, row, version, {"status": "Held"})
    return row


def acknowledge(db, project, row, data):
    _, _, _, _, _, member = _helpers()
    if row.status != "Held":
        raise HTTPException(409, "Acknowledge attendance after the talk is held")
    member(db, project, data.member_id, "attendee")
    if db.query(HseToolboxAck).filter_by(talk_id=row.id, member_id=data.member_id).first():
        raise HTTPException(409, "That person is already acknowledged on this talk")
    ack = HseToolboxAck(talk_id=row.id, member_id=data.member_id, evidence=data.evidence.strip())
    db.add(ack)
    db.flush()
    return ack


def add_finding_rule(db, user, project, data):
    key = _key(data.severity)
    if db.query(HseFindingRule).filter_by(project_id=project.id, severity_key=key).first():
        raise HTTPException(409, "That severity rule already exists")
    row = HseFindingRule(
        organization_id=project.organization_id,
        project_id=project.id,
        severity=data.severity.strip(),
        severity_key=key,
        blocks_work=data.blocks_work,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def _add_finding(db, project, inspection, data):
    _, _, _, _, _, member = _helpers()
    member(db, project, data.owner_id, "responsible owner")
    row = HseFinding(
        inspection_id=inspection.id,
        description=data.description.strip(),
        severity=data.severity.strip(),
        severity_key=_key(data.severity),
        owner_id=data.owner_id,
        target_on=data.target_on,
        action=data.action.strip(),
        photo_reference=data.photo_reference.strip(),
    )
    db.add(row)
    return row


def add_inspection(db, user, project, data):
    if data.inspection_type not in INSPECTION_TYPES:
        raise HTTPException(422, "Choose an inspection type")
    company, discipline, area, package, activity, member = _helpers()
    company(db, project, data.company_id)
    discipline(db, project, data.discipline_id)
    area(db, project, data.area_id)
    found = package(db, project, data.package_id)
    activity(db, found, data.activity_id)
    member(db, project, data.inspector_id, "inspector")
    if data.checklist_document_id:
        document = db.get(HseDocument, data.checklist_document_id)
        if not document or document.project_id != project.id or document.kind != "Inspection Checklist" or document.status != "Approved":
            raise HTTPException(422, "Choose an approved inspection checklist")
    number_key = _key(data.number)
    if db.query(HseInspection).filter_by(project_id=project.id, number_key=number_key).first():
        raise HTTPException(409, "That inspection number already exists")
    row = HseInspection(
        organization_id=project.organization_id,
        project_id=project.id,
        number=data.number.strip(),
        number_key=number_key,
        inspection_type=data.inspection_type,
        company_id=data.company_id,
        discipline_id=data.discipline_id,
        area_id=data.area_id,
        package_id=data.package_id,
        activity_id=data.activity_id,
        inspector_id=data.inspector_id,
        inspected_on=data.inspected_on,
        checklist_document_id=data.checklist_document_id,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    for finding in data.findings:
        _add_finding(db, project, row, finding)
    db.flush()
    return row


def close_finding(db, user, project, row, data):
    inspection = db.get(HseInspection, row.inspection_id)
    if not inspection or inspection.project_id != project.id:
        raise HTTPException(404, "Finding not found")
    if user.id == inspection.inspector_id:
        raise HTTPException(403, "Closing a finding is separate from recording it")
    if row.status != "Open":
        raise HTTPException(409, "This finding is already closed")
    _bump(db, HseFinding, row, data.version, {"status": "Closed", "close_evidence": data.evidence.strip(), "closed_by": user.id})
    return row


def add_observation(db, user, project, data):
    if data.observation_type not in OBSERVATION_TYPES:
        raise HTTPException(422, "Choose an observation type")
    _, _, area, package, activity, _member = _helpers()
    area(db, project, data.area_id)
    found = package(db, project, data.package_id)
    activity(db, found, data.activity_id)
    number_key = _key(data.number)
    if db.query(HseObservation).filter_by(project_id=project.id, number_key=number_key).first():
        raise HTTPException(409, "That observation number already exists")
    row = HseObservation(
        organization_id=project.organization_id,
        project_id=project.id,
        number=data.number.strip(),
        number_key=number_key,
        observation_type=data.observation_type,
        description=data.description.strip(),
        area_id=data.area_id,
        package_id=data.package_id,
        activity_id=data.activity_id,
        evidence=data.evidence.strip(),
        reporter_id=user.id,
    )
    db.add(row)
    db.flush()
    return row
