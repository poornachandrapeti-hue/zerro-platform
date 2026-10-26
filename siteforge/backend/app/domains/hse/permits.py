"""Permits, supporting controls, and workfront warnings.

Authorization and activation are separate. An approved risk assessment does not
authorize work. Original validity dates are not overwritten by an extension.
"""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import update

from app.domains.coordination.jobs import notify
from app.domains.engineering_documents.workflow import submit_record

from .models import (
    ISOLATION_KINDS,
    SUGGESTED_PERMIT_TYPES,
    HseAssessment,
    HseConflictRule,
    HseCoordination,
    HseIsolation,
    HsePermit,
    HsePermitCheck,
    HsePermitEvent,
    HsePermitIsolation,
    HsePermitType,
    now,
)

PERMIT = "hse.permit"
STATEMENT = (
    "Authorization of this permit does not activate it and does not cover unrelated work. "
    "An approved risk assessment does not authorize work."
)
SIMOPS_NOTE = "These warnings use the conflict rules saved on this project. They do not identify every hazard."
BLOCKING = {"Expired", "Suspended", "Authorized"}
OCCUPIED = {"Authorized", "Active", "Suspended"}
DEPENDENT = {"Authorized", "Active", "Suspended"}


def _aware(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _bump(db, model, row, version, values):
    changed = db.execute(
        update(model).where(model.id == row.id, model.version == version).values(version=version + 1, modified_at=now(), **values)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This record changed. Reload it and try again")
    db.refresh(row)


def _helpers():
    from .service import _activity, _area, _company, _discipline, _member, _package, _policy_for

    return _company, _discipline, _area, _package, _activity, _member, _policy_for


def _event(db, row, kind, actor_id, note="", valid_until=None):
    db.add(HsePermitEvent(permit_id=row.id, kind=kind, note=note, valid_until=valid_until, actor_id=actor_id))


def effective_until(db, row):
    end = _aware(row.valid_until)
    for event in db.query(HsePermitEvent).filter_by(permit_id=row.id, kind="Extension"):
        candidate = _aware(event.valid_until)
        if candidate and end and candidate > end:
            end = candidate
    return end


def refresh_permit(db, row):
    if row.status not in {"Authorized", "Active"}:
        return row
    end = effective_until(db, row)
    if end and end < now():
        row.status = "Expired"
        row.modified_at = now()
        db.flush()
    return row


def _covers(permit, package, activity):
    if permit.package_id != package.id:
        return False
    if activity is None:
        return permit.activity_id is None
    return permit.activity_id is None or permit.activity_id == activity.id


def permit_block(db, package, activity=None):
    rows = db.query(HsePermit).filter_by(project_id=package.project_id, package_id=package.id).all()
    for row in rows:
        refresh_permit(db, row)
        if not _covers(row, package, activity) or row.status not in BLOCKING:
            continue
        if row.status == "Expired":
            return f"Permit {row.number} is expired. Start and resume stay blocked for the work it covers."
        if row.status == "Suspended":
            return f"Permit {row.number} is suspended. Start and resume stay blocked for the work it covers."
        return f"Permit {row.number} is authorized and not active. Activate it before this work starts."
    return None


def _raise_block(db, package, activity=None):
    message = permit_block(db, package, activity)
    if message:
        raise HTTPException(409, message)


def _name(db, user_id):
    from app.domains.identity_projects.models import User

    person = db.get(User, user_id)
    return person.name if person else ""


def permit_view(db, user, project, row):
    from app.domains.coordination.service import review_payload
    from app.domains.construction.models import ConstructionActivity, WorkPackage

    from .service import _latest

    refresh_permit(db, row)
    kind = db.get(HsePermitType, row.type_id)
    package = db.get(WorkPackage, row.package_id) if row.package_id else None
    activity = db.get(ConstructionActivity, row.activity_id) if row.activity_id else None
    checks = db.query(HsePermitCheck).filter_by(permit_id=row.id).all()
    events = db.query(HsePermitEvent).filter_by(permit_id=row.id).order_by(HsePermitEvent.id).all()
    links = db.query(HsePermitIsolation).filter_by(permit_id=row.id).all()
    instance = _latest(db, project, PERMIT, row.id)
    return {
        "id": row.id,
        "number": row.number,
        "type_id": row.type_id,
        "type_name": kind.name if kind else "",
        "physical_required": bool(kind.physical_required) if kind else False,
        "company_id": row.company_id,
        "discipline_id": row.discipline_id,
        "area_id": row.area_id,
        "package_id": row.package_id,
        "package_code": package.code if package else "",
        "package_status": package.status if package else "",
        "activity_id": row.activity_id,
        "activity_code": activity.code if activity else "",
        "assessment_id": row.assessment_id,
        "task_description": row.task_description,
        "applicant_id": row.applicant_id,
        "applicant_name": _name(db, row.applicant_id),
        "performing_authority_id": row.performing_authority_id,
        "performing_authority_name": _name(db, row.performing_authority_id),
        "area_owner_id": row.area_owner_id,
        "area_owner_name": _name(db, row.area_owner_id),
        "issuer_id": row.issuer_id,
        "issuer_name": _name(db, row.issuer_id),
        "crew_note": row.crew_note,
        "equipment_note": row.equipment_note,
        "conditions": row.conditions,
        "valid_from": _aware(row.valid_from).isoformat() if row.valid_from else None,
        "valid_until": _aware(row.valid_until).isoformat() if row.valid_until else None,
        "effective_until": effective_until(db, row).isoformat() if effective_until(db, row) else None,
        "status": row.status,
        "external_reference": row.external_reference,
        "external_evidence": row.external_evidence,
        "work_status": row.work_status,
        "site_condition": row.site_condition,
        "statement": row.statement or STATEMENT,
        "version": row.version,
        "checks": [
            {
                "id": item.id,
                "name": item.name,
                "required": item.required,
                "evidence": item.evidence,
                "acknowledged": item.acknowledged,
                "verified_by": item.verified_by,
            }
            for item in checks
        ],
        "events": [
            {
                "id": item.id,
                "kind": item.kind,
                "note": item.note,
                "valid_until": _aware(item.valid_until).isoformat() if item.valid_until else None,
                "actor_name": _name(db, item.actor_id),
            }
            for item in events
        ],
        "isolation_ids": [link.isolation_id for link in links],
        "review": review_payload(db, user, instance) if instance and instance.state in {"In Review", "Returned"} else None,
    }


def _type_view(row):
    return {
        "id": row.id,
        "name": row.name,
        "physical_required": row.physical_required,
        "handover_required": row.handover_required,
        "active": row.active,
    }


def isolation_view(db, row):
    links = db.query(HsePermitIsolation).filter_by(isolation_id=row.id).all()
    return {
        "id": row.id,
        "kind": row.kind,
        "number": row.number,
        "area_id": row.area_id,
        "authority_id": row.authority_id,
        "authority_name": _name(db, row.authority_id),
        "status": row.status,
        "evidence": row.evidence,
        "removal_reason": row.removal_reason,
        "allow_removal_with_active_permit": row.allow_removal_with_active_permit,
        "version": row.version,
        "permit_ids": [link.permit_id for link in links],
    }


def coordination_view(db, row):
    permit = db.get(HsePermit, row.permit_id)
    other = db.get(HsePermit, row.other_permit_id)
    rule = db.get(HseConflictRule, row.rule_id)
    return {
        "id": row.id,
        "permit_id": row.permit_id,
        "permit_number": permit.number if permit else "",
        "other_permit_id": row.other_permit_id,
        "other_number": other.number if other else "",
        "require_decision": bool(rule.require_decision) if rule else True,
        "decision": row.decision,
        "controls": row.controls,
        "status": row.status,
    }


def supplement(db, user, project, payload):
    for row in db.query(HsePermit).filter_by(project_id=project.id):
        refresh_permit(db, row)
    permits = db.query(HsePermit).filter_by(project_id=project.id).order_by(HsePermit.id.desc()).all()
    isolations = db.query(HseIsolation).filter_by(project_id=project.id).order_by(HseIsolation.id.desc()).all()
    rules = db.query(HseConflictRule).filter_by(project_id=project.id).all()
    conflicts = db.query(HseCoordination).filter_by(project_id=project.id).order_by(HseCoordination.id.desc()).all()
    payload["permit_statement"] = STATEMENT
    payload["simops_note"] = SIMOPS_NOTE
    payload["suggested_permit_types"] = list(SUGGESTED_PERMIT_TYPES)
    payload["isolation_kinds"] = list(ISOLATION_KINDS)
    payload["permit_types"] = [_type_view(row) for row in db.query(HsePermitType).filter_by(project_id=project.id, active=True)]
    payload["permits"] = [permit_view(db, user, project, row) for row in permits]
    payload["isolations"] = [isolation_view(db, row) for row in isolations]
    payload["conflict_rules"] = [
        {
            "id": row.id,
            "type_a_id": row.type_a_id,
            "type_b_id": row.type_b_id,
            "same_area": row.same_area,
            "require_decision": row.require_decision,
            "note": row.note,
        }
        for row in rules
    ]
    payload["conflicts"] = [coordination_view(db, row) for row in conflicts]
    payload["counts"]["permits"] = len(permits)
    payload["counts"]["active_permits"] = sum(row.status == "Active" for row in permits)
    payload["counts"]["pending_permits"] = sum(row.status == "Pending Review" for row in permits)
    payload["counts"]["expired_permits"] = sum(row.status == "Expired" for row in permits)
    payload["counts"]["suspended_permits"] = sum(row.status == "Suspended" for row in permits)
    return payload


def work_permits(db, project, package):
    rows = db.query(HsePermit).filter_by(project_id=project.id, package_id=package.id).order_by(HsePermit.id.desc()).all()
    for row in rows:
        refresh_permit(db, row)
    return {
        "permits": [{"id": row.id, "number": row.number, "status": row.status, "activity_id": row.activity_id} for row in rows],
        "permit_block": permit_block(db, package, None) or "",
    }


def add_type(db, user, project, data):
    key = data.name.strip().casefold()
    if db.query(HsePermitType).filter_by(project_id=project.id, name_key=key).first():
        raise HTTPException(409, "That permit type already exists")
    row = HsePermitType(
        organization_id=project.organization_id,
        project_id=project.id,
        name=data.name.strip(),
        name_key=key,
        physical_required=data.physical_required,
        handover_required=data.handover_required,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def add_permit(db, user, project, data):
    company, discipline, area, package, activity, member, _policy = _helpers()
    kind = db.get(HsePermitType, data.type_id)
    if not kind or kind.project_id != project.id or not kind.active:
        raise HTTPException(422, "Choose a permit type saved on this project")
    if _aware(data.valid_until) <= _aware(data.valid_from):
        raise HTTPException(422, "The permit end is not after the start")
    company(db, project, data.company_id)
    discipline(db, project, data.discipline_id)
    area(db, project, data.area_id)
    found = package(db, project, data.package_id)
    act = activity(db, found, data.activity_id)
    for label, user_id in (
        ("applicant", data.applicant_id),
        ("performing authority", data.performing_authority_id),
        ("area owner", data.area_owner_id),
        ("permit issuer", data.issuer_id),
    ):
        member(db, project, user_id, label)
    if data.assessment_id:
        assessment = db.get(HseAssessment, data.assessment_id)
        if not assessment or assessment.project_id != project.id or assessment.status != "Approved":
            raise HTTPException(422, "Choose an approved risk assessment")
    from .field import assert_assignment

    assert_assignment(db, project, found, act, data.performing_authority_id, _aware(data.valid_from).date())
    number_key = data.number.strip().casefold()
    if db.query(HsePermit).filter_by(project_id=project.id, number_key=number_key).first():
        raise HTTPException(409, "That permit number already exists")
    row = HsePermit(
        organization_id=project.organization_id,
        project_id=project.id,
        type_id=kind.id,
        number=data.number.strip(),
        number_key=number_key,
        company_id=data.company_id,
        discipline_id=data.discipline_id,
        area_id=data.area_id,
        package_id=data.package_id,
        activity_id=data.activity_id,
        assessment_id=data.assessment_id,
        task_description=data.task_description.strip(),
        applicant_id=data.applicant_id,
        performing_authority_id=data.performing_authority_id,
        area_owner_id=data.area_owner_id,
        issuer_id=data.issuer_id,
        crew_note=data.crew_note.strip(),
        equipment_note=data.equipment_note.strip(),
        conditions=data.conditions.strip(),
        valid_from=data.valid_from,
        valid_until=data.valid_until,
        external_reference=data.external_reference.strip(),
        external_evidence=data.external_evidence.strip(),
        statement=STATEMENT,
        payload={},
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    for name in data.checks:
        cleaned = name.strip()
        if cleaned:
            db.add(HsePermitCheck(permit_id=row.id, name=cleaned[:120], required=True))
    db.flush()
    return row


def _snapshot(db, row):
    return {
        "number": row.number,
        "type_id": row.type_id,
        "package_id": row.package_id,
        "activity_id": row.activity_id,
        "assessment_id": row.assessment_id,
        "task_description": row.task_description,
        "valid_from": _aware(row.valid_from).isoformat(),
        "valid_until": _aware(row.valid_until).isoformat(),
        "conditions": row.conditions,
        "issuer_id": row.issuer_id,
        "statement": STATEMENT,
        "checks": [item.name for item in db.query(HsePermitCheck).filter_by(permit_id=row.id)],
    }


def submit_permit(db, user, project, row, version):
    if row.status == "Returned for Correction":
        raise HTTPException(409, "A returned permit is resubmitted, not submitted again")
    if row.status != "Draft":
        raise HTTPException(409, "Only a draft permit can be submitted")
    _, _, _, _, _, _, policy_for = _helpers()
    policy = policy_for(db, project, PERMIT, row.company_id, row.discipline_id)
    _bump(db, HsePermit, row, version, {"status": "Pending Review", "payload": _snapshot(db, row), "modified_by": user.id})
    return submit_record(db, user, project, PERMIT, row.id, row.version, policy)


def apply_resubmit(db, user, instance, review_version):
    from app.domains.coordination.service import _close_tasks, _lock, _open_stage, current_stage
    from app.domains.identity_projects.models import Project
    from app.domains.identity_projects.security import holds, permitted

    if instance.state != "Returned":
        raise HTTPException(409, "Only a returned review can be resubmitted")
    if user.id != instance.submitted_by and not user.organization_admin:
        raise HTTPException(403, "Only the submitter can resubmit")
    project = db.get(Project, instance.project_id)
    row = db.get(HsePermit, instance.record_id)
    if not project or not row or row.project_id != project.id or row.status != "Returned for Correction":
        raise HTTPException(409, "Only a returned permit can be resubmitted")
    if not (holds(db, user, project, "hse.plan") or holds(db, user, project, "hse.edit")):
        permitted(db, user, project, "hse.edit")
    _, _, _, _, _, _, policy_for = _helpers()
    policy = policy_for(db, project, PERMIT, row.company_id, row.discipline_id)
    _lock(db, instance, review_version)
    _close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    _bump(db, HsePermit, row, row.version, {"status": "Pending Review", "payload": _snapshot(db, row), "modified_by": user.id})
    instance.record_version = row.version
    instance.policy_id = policy.id
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def on_review_event(db, user, instance, project, action, stage=None):
    if instance.record_type != PERMIT:
        return
    row = db.get(HsePermit, instance.record_id)
    if not row or row.project_id != project.id:
        return
    if action == "advance":
        return
    if action == "return":
        row.status = "Returned for Correction"
    elif action == "reject":
        row.status = "Rejected"
    elif instance.state == "Approved":
        row.status = "Authorized"
        from .service import _tell, _watchers

        _tell(
            db,
            project,
            _watchers(db, project),
            "Permit authorized",
            f"{row.number} is authorized. It is not active until the assigned issuer completes the field checks.",
            f"hse.permit.{row.id}",
        )
    else:
        return
    row.version += 1
    row.modified_by = user.id
    row.modified_at = now()


def verify_check(db, user, project, row, check, data):
    if row.project_id != project.id or check.permit_id != row.id:
        raise HTTPException(404, "Permit check not found")
    if row.status not in {"Draft", "Authorized", "Suspended", "Returned for Correction"}:
        raise HTTPException(409, "Checks are recorded before the permit is active")
    check.evidence = data.evidence.strip()
    check.acknowledged = data.acknowledged
    check.verified_by = user.id
    check.verified_at = now()
    return check


def _issuer_only(user, row):
    if user.id != row.issuer_id:
        raise HTTPException(403, "Only the assigned permit issuer can activate this permit")


def _ranges_overlap(db, left, right):
    start = max(_aware(left.valid_from), _aware(right.valid_from))
    end = min(effective_until(db, left), effective_until(db, right))
    return start < end


def _types_match(rule, left_type, right_type):
    pair = {rule.type_a_id, rule.type_b_id}
    return {left_type, right_type} == pair or (rule.type_a_id == rule.type_b_id and left_type == rule.type_a_id and right_type == rule.type_a_id)


def sync_conflicts(db, user, project, row):
    from app.domains.coordination.models import Task
    from app.domains.coordination.service import _task

    rules = db.query(HseConflictRule).filter_by(project_id=project.id).all()
    others = db.query(HsePermit).filter_by(project_id=project.id).all()
    for other in others:
        if other.id == row.id or other.status not in OCCUPIED:
            continue
        if not row.area_id or not other.area_id:
            continue
        if not _ranges_overlap(db, row, other):
            continue
        for rule in rules:
            if rule.same_area and row.area_id != other.area_id:
                continue
            if not _types_match(rule, row.type_id, other.type_id):
                continue
            found = (
                db.query(HseCoordination)
                .filter_by(permit_id=row.id, other_permit_id=other.id, rule_id=rule.id)
                .first()
            )
            if not found:
                found = HseCoordination(
                    project_id=project.id,
                    permit_id=row.id,
                    other_permit_id=other.id,
                    rule_id=rule.id,
                )
                db.add(found)
                db.flush()
            open_task = (
                db.query(Task)
                .filter_by(project_id=project.id, source_type="hse.coordination", source_id=found.id, status="Open")
                .first()
            )
            if not open_task and found.status == "Open":
                _task(
                    db,
                    user,
                    project,
                    row.area_owner_id,
                    f"Coordinate permit {row.number} with {other.number}",
                    "hse.coordination",
                    found.id,
                )
                person = db.get(type(user), row.area_owner_id)
                if person:
                    notify(
                        db,
                        person,
                        "Conflicting work needs a decision",
                        f"{row.number} overlaps {other.number}. This warning uses a saved rule and does not list every hazard.",
                        f"hse.coordination.{found.id}",
                        project_id=project.id,
                        link=f"/projects/{project.id}",
                    )


def activate(db, user, project, row, version):
    _issuer_only(user, row)
    refresh_permit(db, row)
    if row.status not in {"Authorized", "Suspended"}:
        raise HTTPException(409, "Activate an authorized or suspended permit")
    if row.status == "Expired" or (_aware(row.valid_from) > now()) or (effective_until(db, row) < now()):
        raise HTTPException(409, "This permit is outside its validity window")
    kind = db.get(HsePermitType, row.type_id)
    if kind and kind.physical_required and not (row.external_reference.strip() and row.external_evidence.strip()):
        raise HTTPException(409, "Record the verified paper or external permit reference before activation")
    for check in db.query(HsePermitCheck).filter_by(permit_id=row.id, required=True):
        if not check.acknowledged or not check.verified_by or not check.evidence.strip():
            raise HTTPException(409, f"Complete and acknowledge {check.name} before activation")
    for link in db.query(HsePermitIsolation).filter_by(permit_id=row.id):
        isolation = db.get(HseIsolation, link.isolation_id)
        if not isolation or isolation.status != "In Force":
            raise HTTPException(409, "A linked isolation or supporting control is not in force")
    if row.assessment_id:
        assessment = db.get(HseAssessment, row.assessment_id)
        if not assessment or assessment.status != "Approved":
            raise HTTPException(422, "The linked risk assessment is no longer approved")
    sync_conflicts(db, user, project, row)
    for item in db.query(HseCoordination).filter_by(permit_id=row.id, status="Open"):
        rule = db.get(HseConflictRule, item.rule_id)
        if rule and rule.require_decision:
            raise HTTPException(409, "Record the coordination decision before activation")
    _bump(db, HsePermit, row, version, {"status": "Active", "modified_by": user.id})
    _event(db, row, "Activation", user.id, "Field checks accepted. This activation covers only the approved scope.")
    return row


def suspend(db, user, project, row, data):
    from app.domains.identity_projects.security import holds

    if user.id != row.issuer_id and not holds(db, user, project, "hse.plan"):
        raise HTTPException(403, "Only the assigned issuer or HSE can suspend this permit")
    if row.status != "Active":
        raise HTTPException(409, "Only an active permit can be suspended")
    _bump(db, HsePermit, row, data.version, {"status": "Suspended", "modified_by": user.id})
    _event(db, row, "Suspension", user.id, data.reason.strip())
    return row


def extend_permit(db, user, project, row, data):
    from app.domains.identity_projects.security import holds

    if user.id != row.issuer_id and not holds(db, user, project, "hse.plan"):
        raise HTTPException(403, "Only the assigned issuer or HSE can extend this permit")
    refresh_permit(db, row)
    if row.status not in {"Authorized", "Active", "Expired", "Suspended"}:
        raise HTTPException(409, "This permit cannot be extended")
    new_end = _aware(data.valid_until)
    if new_end <= _aware(row.valid_until):
        raise HTTPException(422, "An extension must be later than the original end")
    values = {"modified_by": user.id}
    if row.status == "Expired" and new_end > now():
        values["status"] = "Authorized"
    _bump(db, HsePermit, row, data.version, values)
    _event(db, row, "Extension", user.id, data.reason.strip(), valid_until=data.valid_until)
    return row


def handover(db, user, project, row, data):
    from app.domains.construction.models import ConstructionActivity, WorkPackage

    from .field import assert_assignment

    _, _, _, _, _, member, _policy = _helpers()
    member(db, project, data.performing_authority_id, "performing authority")
    package = db.get(WorkPackage, row.package_id) if row.package_id else None
    activity = db.get(ConstructionActivity, row.activity_id) if row.activity_id else None
    assert_assignment(db, project, package, activity, data.performing_authority_id, now().date())
    if row.status not in {"Authorized", "Active", "Suspended"}:
        raise HTTPException(409, "Record handover on an authorized permit")
    _bump(
        db,
        HsePermit,
        row,
        data.version,
        {"performing_authority_id": data.performing_authority_id, "modified_by": user.id},
    )
    _event(db, row, "Handover", user.id, data.reason.strip())
    return row


def condition_change(db, user, project, row, data):
    if row.status != "Active":
        raise HTTPException(409, "A condition change applies to an active permit")
    _bump(db, HsePermit, row, data.version, {"status": "Suspended", "modified_by": user.id})
    _event(db, row, "Condition change", user.id, data.reason.strip())
    return row


def close_permit(db, user, project, row, data):
    if row.status not in {"Active", "Suspended", "Expired"}:
        raise HTTPException(409, "Close an active, suspended, or expired permit")
    _bump(
        db,
        HsePermit,
        row,
        data.version,
        {"status": "Closed", "work_status": data.work_status.strip(), "site_condition": data.site_condition.strip(), "modified_by": user.id},
    )
    _event(db, row, "Closure", user.id, f"{data.work_status.strip()} {data.site_condition.strip()}")
    return row


def cancel_permit(db, user, project, row, data):
    if row.status not in {"Draft", "Pending Review", "Returned for Correction", "Authorized"}:
        raise HTTPException(409, "An active permit is suspended or closed, not cancelled")
    _bump(db, HsePermit, row, data.version, {"status": "Cancelled", "modified_by": user.id})
    _event(db, row, "Cancellation", user.id, data.reason.strip())
    return row


def add_isolation(db, user, project, data):
    _, _, area, _, _, member, _policy = _helpers()
    if data.kind not in ISOLATION_KINDS:
        raise HTTPException(422, "Choose a supporting control kind")
    area(db, project, data.area_id)
    member(db, project, data.authority_id, "authority")
    key = data.number.strip().casefold()
    if db.query(HseIsolation).filter_by(project_id=project.id, number_key=key).first():
        raise HTTPException(409, "That isolation number already exists")
    row = HseIsolation(
        organization_id=project.organization_id,
        project_id=project.id,
        kind=data.kind,
        number=data.number.strip(),
        number_key=key,
        area_id=data.area_id,
        authority_id=data.authority_id,
        evidence=data.evidence.strip(),
        allow_removal_with_active_permit=data.allow_removal_with_active_permit,
        valid_from=data.valid_from,
        valid_until=data.valid_until,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def approve_isolation(db, user, project, row, version):
    if row.project_id != project.id:
        raise HTTPException(404, "Isolation not found")
    if row.status != "Draft":
        raise HTTPException(409, "Only a draft isolation can be approved")
    _bump(db, HseIsolation, row, version, {"status": "In Force", "approved_by": user.id})
    return row


def remove_isolation(db, user, project, row, data):
    if row.project_id != project.id:
        raise HTTPException(404, "Isolation not found")
    if row.status != "In Force":
        raise HTTPException(409, "Only an in-force isolation can be removed")
    if user.id == row.approved_by:
        raise HTTPException(403, "Isolation removal is a separate action from its approval")
    links = db.query(HsePermitIsolation).filter_by(isolation_id=row.id).all()
    for link in links:
        permit = db.get(HsePermit, link.permit_id)
        if permit and permit.status in DEPENDENT and not row.allow_removal_with_active_permit:
            raise HTTPException(409, f"Permit {permit.number} still depends on this isolation")
    _bump(db, HseIsolation, row, data.version, {"status": "Removed", "removal_reason": data.reason.strip(), "removed_by": user.id})
    return row


def link_isolation(db, project, permit, isolation):
    if permit.project_id != project.id or isolation.project_id != project.id:
        raise HTTPException(404, "Record not found")
    if permit.status in {"Closed", "Cancelled", "Rejected"}:
        raise HTTPException(409, "This permit can no longer take a supporting control")
    if db.query(HsePermitIsolation).filter_by(permit_id=permit.id, isolation_id=isolation.id).first():
        return isolation
    db.add(HsePermitIsolation(permit_id=permit.id, isolation_id=isolation.id))
    db.flush()
    return isolation


def add_rule(db, user, project, data):
    left = db.get(HsePermitType, data.type_a_id)
    right = db.get(HsePermitType, data.type_b_id)
    if not left or not right or left.project_id != project.id or right.project_id != project.id:
        raise HTTPException(422, "Choose permit types on this project")
    row = HseConflictRule(
        organization_id=project.organization_id,
        project_id=project.id,
        type_a_id=left.id,
        type_b_id=right.id,
        same_area=data.same_area,
        require_decision=data.require_decision,
        note=data.note.strip(),
    )
    db.add(row)
    db.flush()
    return row


def decide_conflict(db, user, project, permit, data):
    from app.domains.coordination.models import Task

    other = db.get(HsePermit, data.other_permit_id)
    if not other or other.project_id != project.id:
        raise HTTPException(422, "Choose the overlapping permit")
    sync_conflicts(db, user, project, permit)
    row = (
        db.query(HseCoordination)
        .filter_by(project_id=project.id, permit_id=permit.id, other_permit_id=other.id, status="Open")
        .first()
    )
    if not row:
        raise HTTPException(409, "No open coordination warning matches those permits")
    row.decision = data.decision.strip()
    row.controls = data.controls.strip()
    row.status = "Decided"
    row.decided_by = user.id
    row.decided_at = now()
    for task in db.query(Task).filter_by(project_id=project.id, source_type="hse.coordination", source_id=row.id, status="Open"):
        task.status = "Completed"
    return row
