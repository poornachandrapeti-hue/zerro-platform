"""Safety holds and controlled restart.

A concern is a report. It does not stop work. A formal hold is issued only by a
person the project procedure saved. Release is a separate approval. A project
manager or an organization administrator does not release it by role. Releasing
the hold does not start the work.
"""

from fastapi import HTTPException

from app.domains.engineering_documents.workflow import submit_record

from .models import HOLD_SCOPES, HseHold, HseHoldEvent, HseHoldIssuer, HseHoldRule, now
from .service import _bump

HOLD = "hse.hold"
BLOCKING = {"Active", "Release Requested", "Returned"}
CONCERN_NOTE = (
    "Reporting this concern does not issue a formal hold. "
    "Urgent action in the field does not wait for this record."
)
HOLD_NOTE = (
    "This hold blocks start, resume, and daily progress for the work it names. "
    "A project manager or an organization administrator does not release it. "
    "Releasing it does not start the work. A quality hold release does not clear it."
)
EQUIPMENT_NOTE = "This names equipment. The equipment register is not open, so this hold does not stop a work package by itself."


def _key(value):
    return value.strip().casefold()


def _helpers():
    from .service import _activity, _area, _company, _member, _package, _policy_for, _tell, _watchers

    return _company, _area, _package, _activity, _member, _policy_for, _tell, _watchers


def _name(db, user_id):
    from app.domains.identity_projects.models import User

    if not user_id:
        return ""
    person = db.get(User, user_id)
    return person.name if person else ""


def _rule(db, project_id):
    return db.query(HseHoldRule).filter_by(project_id=project_id).first()


def _event(db, row, kind, actor_id, note=""):
    db.add(HseHoldEvent(hold_id=row.id, kind=kind, note=note.strip(), actor_id=actor_id))


def add_issuer(db, user, project, data):
    _, _, _, _, member, _, _, _ = _helpers()
    member(db, project, data.user_id, "hold issuer")
    if db.query(HseHoldIssuer).filter_by(project_id=project.id, user_id=data.user_id).first():
        raise HTTPException(409, "That hold issuer is already saved")
    row = HseHoldIssuer(
        organization_id=project.organization_id,
        project_id=project.id,
        user_id=data.user_id,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def save_rule(db, user, project, data):
    row = _rule(db, project.id)
    if row:
        row.separate_release = data.separate_release
        return row
    row = HseHoldRule(
        organization_id=project.organization_id,
        project_id=project.id,
        separate_release=data.separate_release,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def _issuer_ids(db, project):
    return {row.user_id for row in db.query(HseHoldIssuer).filter_by(project_id=project.id)}


def _scope(db, project, data):
    company, area, package, activity, _member, _, _, _ = _helpers()
    if data.scope_kind not in HOLD_SCOPES:
        raise HTTPException(422, "Choose what this hold covers")
    company(db, project, data.company_id)
    found = package(db, project, data.package_id)
    if data.scope_kind == "package":
        if not found or data.activity_id:
            raise HTTPException(422, "A package hold covers one whole work package")
    elif data.scope_kind == "activity":
        if not activity(db, found, data.activity_id):
            raise HTTPException(422, "Choose the activity this hold covers")
    elif data.scope_kind == "area":
        if not area(db, project, data.area_id):
            raise HTTPException(422, "Choose the location this hold covers")
    elif data.scope_kind == "equipment":
        if len(data.equipment_note.strip()) < 3:
            raise HTTPException(422, "Name the equipment this hold covers")
    elif data.scope_kind == "work":
        if not found or len(data.affected_work.strip()) < 3:
            raise HTTPException(422, "Name the affected work and its work package")
    return found


def add_concern(db, user, project, data):
    company, area, package, _, _, _, _, _ = _helpers()
    company(db, project, data.company_id)
    area(db, project, data.area_id)
    package(db, project, data.package_id)
    number_key = _key(data.number)
    if db.query(HseHold).filter_by(project_id=project.id, number_key=number_key).first():
        raise HTTPException(409, "That hold number already exists")
    row = HseHold(
        organization_id=project.organization_id,
        project_id=project.id,
        number=data.number.strip(),
        number_key=number_key,
        kind="Concern",
        reason=data.reason.strip(),
        source="Concern",
        severity=data.severity.strip(),
        package_id=data.package_id,
        area_id=data.area_id,
        company_id=data.company_id,
        status="Reported",
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    _event(db, row, "Reported", user.id, data.reason)
    return row


def add_hold(db, user, project, data):
    issuers = _issuer_ids(db, project)
    if not issuers:
        raise HTTPException(409, "Save who may issue a formal hold. The project procedure names that person.")
    if user.id not in issuers:
        raise HTTPException(403, "Only a saved hold issuer can place a formal hold")
    _, _, _, _, member, _, tell, watchers = _helpers()
    member(db, project, data.owner_id, "responsible owner")
    rule = _rule(db, project.id)
    if rule and rule.separate_release and data.owner_id == user.id:
        raise HTTPException(422, "The hold issuer cannot be the responsible owner")
    _scope(db, project, data)
    number_key = _key(data.number)
    if db.query(HseHold).filter_by(project_id=project.id, number_key=number_key).first():
        raise HTTPException(409, "That hold number already exists")
    row = HseHold(
        organization_id=project.organization_id,
        project_id=project.id,
        number=data.number.strip(),
        number_key=number_key,
        kind="Hold",
        reason=data.reason.strip(),
        source=data.source.strip(),
        severity=data.severity.strip(),
        scope_kind=data.scope_kind,
        package_id=data.package_id,
        activity_id=data.activity_id,
        area_id=data.area_id,
        equipment_note=data.equipment_note.strip(),
        affected_work=data.affected_work.strip(),
        restricted_actions=data.restricted_actions.strip(),
        immediate_controls=data.immediate_controls.strip(),
        release_conditions=data.release_conditions.strip(),
        company_id=data.company_id,
        owner_id=data.owner_id,
        issued_by=user.id,
        issued_at=now(),
        status="Active",
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    _event(db, row, "Issued", user.id, data.reason)
    tell(
        db,
        project,
        watchers(db, project),
        "A safety hold is active",
        f"Safety hold {row.number} stops the work it names. This record does not replace emergency action already required in the field.",
        f"hse.hold.{row.id}",
    )
    return row


def request_release(db, user, project, row, data):
    if row.kind != "Hold" or row.status != "Active":
        raise HTTPException(409, "Request release only for an active safety hold")
    if user.id != row.owner_id:
        raise HTTPException(403, "Only the responsible owner can request release")
    rule = _rule(db, project.id)
    if rule and rule.separate_release and user.id == row.issued_by:
        raise HTTPException(422, "The hold issuer cannot request this release")
    _, _, _, _, _, policy_for, _, _ = _helpers()
    policy = policy_for(db, project, HOLD, row.company_id, None)
    _bump(
        db,
        HseHold,
        row,
        data.version,
        {"status": "Release Requested", "evidence": data.evidence.strip(), "modified_by": user.id},
    )
    _event(db, row, "Release requested", user.id, data.evidence)
    return submit_record(db, user, project, HOLD, row.id, row.version, policy)


def apply_resubmit(db, user, instance, review_version):
    from app.domains.coordination.service import _close_tasks, _lock, _open_stage, current_stage
    from app.domains.identity_projects.models import Project

    if instance.state != "Returned":
        raise HTTPException(409, "Only a returned review can be resubmitted")
    if user.id != instance.submitted_by:
        raise HTTPException(403, "Only the owner who requested release can resubmit")
    project = db.get(Project, instance.project_id)
    row = db.get(HseHold, instance.record_id)
    if not project or not row or row.project_id != project.id or row.status != "Returned":
        raise HTTPException(409, "Only a returned safety hold can be resubmitted")
    rule = _rule(db, project.id)
    if rule and rule.separate_release and user.id == row.issued_by:
        raise HTTPException(422, "The hold issuer cannot request this release")
    _, _, _, _, _, policy_for, _, _ = _helpers()
    policy = policy_for(db, project, HOLD, row.company_id, None)
    _lock(db, instance, review_version)
    _close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    _bump(db, HseHold, row, row.version, {"status": "Release Requested", "modified_by": user.id})
    instance.record_version = row.version
    instance.policy_id = policy.id
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def on_review_event(db, user, instance, project, action, stage=None):
    row = db.get(HseHold, instance.record_id)
    if not row or row.project_id != project.id:
        return
    if action == "advance":
        return
    if action == "return":
        row.status = "Returned"
        _event(db, row, "Returned", user.id)
    elif action == "reject":
        row.status = "Active"
        _event(db, row, "Rejected", user.id)
    elif instance.state == "Approved":
        row.status = "Released"
        _event(db, row, "Released", user.id, row.evidence)
        _, _, _, _, _, _, tell, watchers = _helpers()
        tell(
            db,
            project,
            watchers(db, project),
            "Safety hold released",
            f"{row.number} is released. The work does not start until construction start or resume is accepted.",
            f"hse.hold.{row.id}.released",
        )
    else:
        return
    row.version += 1
    row.modified_by = user.id
    row.modified_at = now()


def release_guard(db, user, instance):
    row = db.get(HseHold, instance.record_id)
    rule = _rule(db, instance.project_id)
    if row and rule and rule.separate_release and user.id == row.issued_by:
        raise HTTPException(403, "The hold issuer cannot release this hold")


def _covers(row, package, activity):
    if row.kind != "Hold" or row.status not in BLOCKING:
        return False
    if row.scope_kind == "equipment":
        return False
    if row.scope_kind == "area":
        return bool(row.area_id and package.area_id == row.area_id)
    if row.scope_kind == "activity":
        return activity is not None and row.activity_id == activity.id
    if row.scope_kind in {"package", "work"} and row.package_id == package.id:
        if activity is None:
            return row.activity_id is None
        return row.activity_id is None or row.activity_id == activity.id
    return False


def hold_block(db, package, activity=None):
    rows = db.query(HseHold).filter_by(project_id=package.project_id).all()
    for row in rows:
        if _covers(row, package, activity):
            return (
                f"Safety hold {row.number} is active. Start and resume stay blocked for the work it covers. "
                "A quality hold release does not clear it."
            )
    return None


def raise_hold_block(db, package, activity=None, status_code=409):
    message = hold_block(db, package, activity)
    if message:
        raise HTTPException(status_code, message)


def hold_view(db, row):
    from app.domains.construction.models import WorkPackage

    package = db.get(WorkPackage, row.package_id) if row.package_id else None
    events = db.query(HseHoldEvent).filter_by(hold_id=row.id).order_by(HseHoldEvent.id).all()
    statement = CONCERN_NOTE if row.kind == "Concern" else HOLD_NOTE
    if row.scope_kind == "equipment":
        statement = f"{statement} {EQUIPMENT_NOTE}"
    return {
        "id": row.id,
        "number": row.number,
        "kind": row.kind,
        "status": row.status,
        "reason": row.reason,
        "source": row.source,
        "severity": row.severity,
        "scope_kind": row.scope_kind,
        "package_id": row.package_id,
        "package_status": package.status if package else "",
        "activity_id": row.activity_id,
        "area_id": row.area_id,
        "equipment_note": row.equipment_note,
        "affected_work": row.affected_work,
        "restricted_actions": row.restricted_actions,
        "immediate_controls": row.immediate_controls,
        "release_conditions": row.release_conditions,
        "owner_id": row.owner_id,
        "owner_name": _name(db, row.owner_id),
        "issued_by": row.issued_by,
        "issuer_name": _name(db, row.issued_by),
        "evidence": row.evidence,
        "version": row.version,
        "statement": statement,
        "events": [{"id": item.id, "kind": item.kind, "note": item.note} for item in events],
    }


def supplement(db, user, project, payload):
    rows = db.query(HseHold).filter_by(project_id=project.id).order_by(HseHold.id.desc()).all()
    rule = _rule(db, project.id)
    payload["hold_note"] = HOLD_NOTE
    payload["concern_note"] = CONCERN_NOTE
    payload["hold_scopes"] = list(HOLD_SCOPES)
    payload["hold_issuers"] = [
        {"id": row.id, "user_id": row.user_id, "name": _name(db, row.user_id)}
        for row in db.query(HseHoldIssuer).filter_by(project_id=project.id)
    ]
    payload["hold_rule"] = {"separate_release": bool(rule.separate_release) if rule else False}
    payload["holds"] = [hold_view(db, row) for row in rows]
    payload["counts"]["active_holds"] = sum(row.kind == "Hold" and row.status in BLOCKING for row in rows)
    return payload
