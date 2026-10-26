"""Qualifications and calibration kept by Quality.

These records name the person or the instrument directly. A verified QA/QC
qualification kept in HR also covers an inspector whose login is linked to
that HR person. A saved reviewer verifies the evidence. Withdrawing a record
later does not rewrite an inspection outcome.
"""

from fastapi import HTTPException
from sqlalchemy import update

from app.domains.construction.models import ConstructionActivity, WorkPackage
from app.domains.coordination.service import REVIEW_GUARDS, review_payload
from app.domains.engineering_documents.workflow import submit_record
from app.domains.identity_projects.models import Membership, User
from app.domains.identity_projects.security import holds
from app.domains.supply_chain.service import _authority, _policy, _project_member

from .models import Calibration, ConstructionRequest, Qualification, now

QUALIFICATION = "quality.qualification"
CALIBRATION = "quality.calibration"
EDITABLE = {"Draft", "Returned for Correction"}
QUALIFICATION_STATEMENT = (
    "Quality keeps this qualification. HR is not the source. "
    "Approval verifies the evidence for the dates shown. It does not accept work or certify billing."
)
CALIBRATION_STATEMENT = (
    "Quality keeps this calibration. Equipment management is not the source. "
    "Approval verifies the certificate. It does not accept work or certify billing."
)
QUALIFICATION_NOTE = (
    "A qualification names a project member, the certificate, and the dates it covers. "
    "A saved reviewer verifies it. A verified QA/QC qualification kept in HR also counts for a member whose login is linked to that HR person. "
    "This does not accept work or certify billing."
)
CALIBRATION_NOTE = (
    "A calibration names the instrument, the certificate, and the due date. "
    "A saved reviewer verifies it. Equipment management is not the source. "
    "This does not accept work or certify billing."
)


def _bump(db, model, row, version, values):
    changed = db.execute(
        update(model).where(model.id == row.id, model.version == version).values(version=version + 1, modified_at=now(), **values)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This record changed. Reload it and try again")
    db.refresh(row)


def _member(db, project, user_id):
    person = db.get(User, user_id)
    if not _project_member(db, project, person):
        raise HTTPException(422, "Choose an active project member")
    return person


def _policy_for(db, project, record_type):
    policy = _policy(db, project, record_type, None, None)
    if not policy:
        raise HTTPException(422, "Mandatory reviewer configuration is missing")
    _authority(db, project, policy)
    return policy


def _latest(db, project, record_type, record_id):
    from app.domains.coordination.models import ReviewInstance

    return (
        db.query(ReviewInstance)
        .filter_by(project_id=project.id, record_type=record_type, record_id=record_id)
        .order_by(ReviewInstance.id.desc())
        .first()
    )


def _people(db, project):
    people = []
    seen = set()
    for member in db.query(Membership).filter_by(project_id=project.id, active=True):
        if member.user_id in seen:
            continue
        person = db.get(User, member.user_id)
        if person and person.active:
            seen.add(person.id)
            people.append({"id": person.id, "name": person.name})
    return people


def _records_for(db, project, person_id):
    return (
        db.query(Qualification)
        .filter(
            Qualification.project_id == project.id,
            Qualification.person_id == person_id,
            Qualification.status.in_(("Approved", "Withdrawn")),
        )
        .all()
    )


def _hr_covers(db, project, person_id, on_date):
    from app.domains.workforce.credentials import hr_covers

    return hr_covers(db, project.organization_id, person_id, "QA/QC", on_date)


def _on_record(db, project, person_id):
    from app.domains.workforce.credentials import hr_has_any

    return bool(_records_for(db, project, person_id)) or hr_has_any(db, project.organization_id, person_id, "QA/QC")


def covers(db, project, person_id, on_date):
    return any(
        row.status == "Approved" and row.valid_from <= on_date <= row.valid_to
        for row in _records_for(db, project, person_id)
    ) or _hr_covers(db, project, person_id, on_date)


def assert_inspector(db, project, person_id, on_date):
    if not _on_record(db, project, person_id):
        return
    if not covers(db, project, person_id, on_date):
        raise HTTPException(422, "The inspector has no qualification valid on the inspection date")


def coverage_note(db, project, person_id, on_date):
    if not _on_record(db, project, person_id):
        return "No qualification was on record in Quality or in HR."
    if covers(db, project, person_id, on_date):
        return "A qualification was valid on the inspection date."
    return "The inspector has no qualification valid on the inspection date."


def _affected(db, row):
    requests = (
        db.query(ConstructionRequest)
        .filter(
            ConstructionRequest.project_id == row.project_id,
            ConstructionRequest.inspector_id == row.person_id,
            ConstructionRequest.requested_on >= row.valid_from,
            ConstructionRequest.requested_on <= row.valid_to,
            ConstructionRequest.status != "Cancelled",
        )
        .order_by(ConstructionRequest.id)
        .all()
    )
    found = []
    for request in requests:
        activity = db.get(ConstructionActivity, request.activity_id)
        package = db.get(WorkPackage, request.package_id)
        found.append(
            {
                "number": request.number,
                "status": request.status,
                "outcome": request.outcome,
                "activity_code": activity.code if activity else "",
                "package_status": package.status if package else "",
            }
        )
    return found


def qualification_view(db, user, project, row):
    person = db.get(User, row.person_id)
    instance = _latest(db, project, QUALIFICATION, row.id)
    return {
        "id": row.id,
        "number": row.number,
        "person_id": row.person_id,
        "person_name": person.name if person else "",
        "status": row.status,
        "qualification_type": row.qualification_type,
        "applicable_activities": row.applicable_activities,
        "issuer": row.issuer,
        "certificate_number": row.certificate_number,
        "valid_from": row.valid_from.isoformat(),
        "valid_to": row.valid_to.isoformat(),
        "evidence": row.evidence,
        "statement": row.statement,
        "withdrawal_reason": row.withdrawal_reason,
        "affected": _affected(db, row),
        "version": row.version,
        "review": review_payload(db, user, instance) if instance else None,
    }


def calibration_view(db, user, project, row):
    instance = _latest(db, project, CALIBRATION, row.id)
    return {
        "id": row.id,
        "number": row.number,
        "status": row.status,
        "equipment_code": row.equipment_code,
        "description": row.description,
        "serial_number": row.serial_number,
        "certificate_reference": row.certificate_reference,
        "calibrated_on": row.calibrated_on.isoformat(),
        "due_on": row.due_on.isoformat(),
        "use_range": row.use_range,
        "evidence": row.evidence,
        "statement": row.statement,
        "withdrawal_reason": row.withdrawal_reason,
        "affected_note": "No inspection names this instrument. Equipment management is not open. Outcomes were not changed.",
        "version": row.version,
        "review": review_payload(db, user, instance) if instance else None,
    }


def qualification_register(db, user, project):
    rows = (
        db.query(Qualification)
        .filter_by(project_id=project.id)
        .filter(Qualification.status != "Cancelled")
        .order_by(Qualification.id.desc())
        .all()
    )
    return {
        "note": QUALIFICATION_NOTE,
        "members": _people(db, project),
        "qualifications": [qualification_view(db, user, project, row) for row in rows],
    }


def calibration_register(db, user, project):
    rows = (
        db.query(Calibration)
        .filter_by(project_id=project.id)
        .filter(Calibration.status != "Cancelled")
        .order_by(Calibration.id.desc())
        .all()
    )
    return {"note": CALIBRATION_NOTE, "calibrations": [calibration_view(db, user, project, row) for row in rows]}


def add_qualification(db, user, project, data):
    if data.valid_to < data.valid_from:
        raise HTTPException(422, "The valid-to date cannot be earlier than the valid-from date")
    person = _member(db, project, data.person_id)
    key = data.number.strip().casefold()
    if db.query(Qualification).filter_by(project_id=project.id, number_key=key).first():
        raise HTTPException(409, "Qualification number already exists on this project")
    row = Qualification(
        organization_id=project.organization_id,
        project_id=project.id,
        person_id=person.id,
        number=data.number.strip(),
        number_key=key,
        qualification_type=data.qualification_type.strip(),
        applicable_activities=data.applicable_activities.strip(),
        issuer=data.issuer.strip(),
        certificate_number=data.certificate_number.strip(),
        valid_from=data.valid_from,
        valid_to=data.valid_to,
        evidence=data.evidence.strip(),
        statement=QUALIFICATION_STATEMENT,
        payload={},
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def add_calibration(db, user, project, data):
    if data.due_on < data.calibrated_on:
        raise HTTPException(422, "The due date cannot be earlier than the calibration date")
    key = data.number.strip().casefold()
    if db.query(Calibration).filter_by(project_id=project.id, number_key=key).first():
        raise HTTPException(409, "Calibration number already exists on this project")
    row = Calibration(
        organization_id=project.organization_id,
        project_id=project.id,
        number=data.number.strip(),
        number_key=key,
        equipment_code=data.equipment_code.strip(),
        description=data.description.strip(),
        serial_number=data.serial_number.strip(),
        certificate_reference=data.certificate_reference.strip(),
        calibrated_on=data.calibrated_on,
        due_on=data.due_on,
        use_range=data.use_range.strip(),
        evidence=data.evidence.strip(),
        statement=CALIBRATION_STATEMENT,
        payload={},
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def _submit(db, user, project, model, row, record_type, version):
    if row.status not in EDITABLE:
        raise HTTPException(409, "Only a draft record can be submitted")
    policy = _policy_for(db, project, record_type)
    _bump(db, model, row, version, {"status": "Pending Review", "modified_by": user.id})
    return submit_record(db, user, project, record_type, row.id, row.version, policy)


def submit_qualification(db, user, project, row, version):
    return _submit(db, user, project, Qualification, row, QUALIFICATION, version)


def submit_calibration(db, user, project, row, version):
    return _submit(db, user, project, Calibration, row, CALIBRATION, version)


def withdraw(db, user, model, row, data):
    if row.status != "Approved":
        raise HTTPException(409, "Only an approved record can be withdrawn")
    _bump(
        db,
        model,
        row,
        data.version,
        {"status": "Withdrawn", "withdrawal_reason": data.reason.strip(), "modified_by": user.id},
    )


def apply_resubmit(db, user, instance, review_version):
    from app.domains.coordination.service import _close_tasks, _lock, _open_stage, current_stage
    from app.domains.identity_projects.models import Project

    if instance.record_type not in {QUALIFICATION, CALIBRATION}:
        return
    if instance.state != "Returned":
        raise HTTPException(409, "Only a returned review can be resubmitted")
    if user.id != instance.submitted_by and not user.organization_admin:
        raise HTTPException(403, "Only the submitter can resubmit")
    project = db.get(Project, instance.project_id)
    model = Qualification if instance.record_type == QUALIFICATION else Calibration
    row = db.get(model, instance.record_id)
    if not project or not row or row.project_id != project.id:
        raise HTTPException(404, "Record not found")
    if not holds(db, user, project, "quality.plan"):
        raise HTTPException(403, "Insufficient project permission")
    if row.status != "Returned for Correction":
        raise HTTPException(409, "Only a returned record can be resubmitted")
    policy = _policy_for(db, project, instance.record_type)
    _lock(db, instance, review_version)
    _close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    _bump(db, model, row, row.version, {"status": "Pending Review", "modified_by": user.id})
    instance.record_version = row.version
    instance.policy_id = policy.id
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def on_review_event(db, user, instance, project, action, stage=None):
    if instance.record_type not in {QUALIFICATION, CALIBRATION}:
        return
    if action == "advance":
        return
    model = Qualification if instance.record_type == QUALIFICATION else Calibration
    row = db.get(model, instance.record_id)
    if not row or row.project_id != project.id:
        return
    if action == "return":
        row.status = "Returned for Correction"
    elif action == "reject":
        row.status = "Rejected"
    elif instance.state == "Approved":
        row.status = "Approved"
    else:
        return
    row.version += 1
    row.modified_by = user.id
    row.modified_at = now()


def review_guard(db, user, instance, stage, action):
    if action != "approve" or instance.record_type not in {QUALIFICATION, CALIBRATION}:
        return
    from app.domains.identity_projects.models import Project

    project = db.get(Project, instance.project_id)
    model = Qualification if instance.record_type == QUALIFICATION else Calibration
    row = db.get(model, instance.record_id)
    if not project or not row or row.project_id != project.id or row.status != "Pending Review":
        raise HTTPException(409, "This record is not awaiting review")


if review_guard not in REVIEW_GUARDS:
    REVIEW_GUARDS.append(review_guard)
