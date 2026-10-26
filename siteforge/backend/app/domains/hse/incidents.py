"""Incident reports and corrective actions.

A report can be short. The investigation is a later update and does not rewrite
the first report. Medical detail is not stored. Recording an incident does not
start the emergency response and does not hold work. Submitting action evidence
does not close the action.
"""

from fastapi import HTTPException

from app.domains.coordination.jobs import notify
from app.domains.coordination.models import Task
from app.domains.coordination.service import _close_tasks, _task
from app.domains.engineering_documents.workflow import submit_record

from .models import (
    ACTION_SOURCES,
    SUGGESTED_INCIDENT_CATEGORIES,
    HseAction,
    HseActionRule,
    HseIncident,
    HseIncidentCategory,
    HseIncidentMember,
    HseIncidentRule,
    HseInspection,
    HseObservation,
    HseToolboxTalk,
    now,
)
from .service import _bump

INCIDENT = "hse.incident"
INCIDENT_NOTE = (
    "This record does not start or replace the emergency response. Medical detail is not stored here. "
    "Closing it does not hold or release work."
)
ACTION_NOTE = "Submitting evidence does not close this action. The named verifier closes it."
RATE_NOTE = "Incident counts come from recorded reports. A rate stays N/A until an approved definition and exposure hours exist."
CLOSURE_FROM = {"Reported", "Under Investigation", "Returned for Correction"}


def _key(value):
    return value.strip().casefold()


def _name(db, user_id):
    from app.domains.identity_projects.models import User

    person = db.get(User, user_id)
    return person.name if person else "This member"


def _helpers():
    from .service import _activity, _area, _company, _member, _package, _policy_for

    return _company, _area, _package, _activity, _member, _policy_for


def _source(db, project, source_type, source_id):
    if source_type not in ACTION_SOURCES:
        raise HTTPException(422, "Choose an HSE source for this action")
    if not source_type:
        return
    model = {
        "hse.incident": HseIncident,
        "hse.observation": HseObservation,
        "hse.inspection": HseInspection,
        "hse.talk": HseToolboxTalk,
    }[source_type]
    row = db.get(model, source_id) if source_id else None
    if not row or row.project_id != project.id:
        raise HTTPException(422, "Choose a source record on this project")


def add_category(db, user, project, data):
    key = _key(data.name)
    if db.query(HseIncidentCategory).filter_by(project_id=project.id, name_key=key).first():
        raise HTTPException(409, "That incident category already exists")
    row = HseIncidentCategory(
        organization_id=project.organization_id,
        project_id=project.id,
        name=data.name.strip(),
        name_key=key,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def add_rule(db, user, project, data):
    key = _key(data.severity)
    if db.query(HseIncidentRule).filter_by(project_id=project.id, severity_key=key).first():
        raise HTTPException(409, "That severity rule already exists")
    row = HseIncidentRule(
        organization_id=project.organization_id,
        project_id=project.id,
        severity=data.severity.strip(),
        severity_key=key,
        requires_investigation=data.requires_investigation,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def save_action_rule(db, user, project, data):
    row = db.query(HseActionRule).filter_by(project_id=project.id).first()
    if row:
        row.effectiveness_required = data.effectiveness_required
        return row
    row = HseActionRule(
        organization_id=project.organization_id,
        project_id=project.id,
        effectiveness_required=data.effectiveness_required,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def add_incident(db, user, project, data):
    if data.event_at.tzinfo is None:
        raise HTTPException(422, "Include the timezone on the event time")
    company, area, package, activity, _member, _policy = _helpers()
    category = db.get(HseIncidentCategory, data.category_id)
    if not category or category.project_id != project.id:
        raise HTTPException(422, "Choose an incident category saved on this project")
    company(db, project, data.company_id)
    area(db, project, data.area_id)
    found = package(db, project, data.package_id)
    activity(db, found, data.activity_id)
    number_key = _key(data.number)
    if db.query(HseIncident).filter_by(project_id=project.id, number_key=number_key).first():
        raise HTTPException(409, "That incident number already exists")
    row = HseIncident(
        organization_id=project.organization_id,
        project_id=project.id,
        category_id=category.id,
        number=data.number.strip(),
        number_key=number_key,
        event_at=data.event_at,
        timezone_name=data.timezone_name.strip(),
        reported_at=now(),
        area_id=data.area_id,
        location=data.location.strip(),
        company_id=data.company_id,
        package_id=data.package_id,
        activity_id=data.activity_id,
        involved=data.involved.strip(),
        description=data.description.strip(),
        immediate_actions=data.immediate_actions.strip(),
        emergency_requested=data.emergency_requested,
        initial_severity=data.initial_severity.strip(),
        evidence=data.evidence.strip(),
        reporter_id=user.id,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def _needs_investigation(db, row):
    if not row.initial_severity.strip():
        return False
    rule = db.query(HseIncidentRule).filter_by(project_id=row.project_id, severity_key=_key(row.initial_severity)).first()
    return bool(rule and rule.requires_investigation and not row.verified_classification.strip())


def investigate(db, user, project, row, data):
    if row.status not in {"Reported", "Under Investigation", "Returned for Correction"}:
        raise HTTPException(409, "The investigation is recorded before closure")
    _, _, _, _, member, _policy = _helpers()
    for user_id in data.team_ids:
        member(db, project, user_id, "investigation team member")
    status = "Under Investigation" if row.status == "Reported" else row.status
    _bump(
        db,
        HseIncident,
        row,
        data.version,
        {
            "status": status,
            "verified_classification": data.verified_classification.strip(),
            "contributing_factors": data.contributing_factors.strip(),
            "root_causes": data.root_causes.strip(),
            "lessons": data.lessons.strip(),
            "modified_by": user.id,
        },
    )
    db.query(HseIncidentMember).filter_by(incident_id=row.id).delete()
    for user_id in dict.fromkeys(data.team_ids):
        db.add(HseIncidentMember(incident_id=row.id, user_id=user_id))
    db.flush()
    return row


def submit_incident(db, user, project, row, version):
    if row.status not in CLOSURE_FROM:
        raise HTTPException(409, "This incident is not waiting for closure")
    if _needs_investigation(db, row):
        raise HTTPException(409, "Record the investigation before closure. The saved project rule requires it.")
    _, _, _, _, _, policy_for = _helpers()
    policy = policy_for(db, project, INCIDENT, row.company_id, None)
    _bump(db, HseIncident, row, version, {"status": "Pending Closure", "modified_by": user.id})
    return submit_record(db, user, project, INCIDENT, row.id, row.version, policy)


def apply_resubmit(db, user, instance, review_version):
    from app.domains.coordination.service import _close_tasks as close_tasks
    from app.domains.coordination.service import _lock, _open_stage, current_stage
    from app.domains.identity_projects.models import Project
    from app.domains.identity_projects.security import holds, permitted

    if instance.state != "Returned":
        raise HTTPException(409, "Only a returned review can be resubmitted")
    if user.id != instance.submitted_by and not user.organization_admin:
        raise HTTPException(403, "Only the submitter can resubmit")
    project = db.get(Project, instance.project_id)
    row = db.get(HseIncident, instance.record_id)
    if not project or not row or row.project_id != project.id or row.status != "Returned for Correction":
        raise HTTPException(409, "Only a returned incident can be resubmitted")
    if not holds(db, user, project, "hse.plan"):
        permitted(db, user, project, "hse.plan")
    if _needs_investigation(db, row):
        raise HTTPException(409, "Record the investigation before closure. The saved project rule requires it.")
    _, _, _, _, _, policy_for = _helpers()
    policy = policy_for(db, project, INCIDENT, row.company_id, None)
    _lock(db, instance, review_version)
    close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    _bump(db, HseIncident, row, row.version, {"status": "Pending Closure", "modified_by": user.id})
    instance.record_version = row.version
    instance.policy_id = policy.id
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def on_review_event(db, user, instance, project, action, stage=None):
    row = db.get(HseIncident, instance.record_id)
    if not row or row.project_id != project.id:
        return
    if action == "advance":
        return
    if action == "return":
        row.status = "Returned for Correction"
    elif action == "reject":
        row.status = "Rejected"
    elif instance.state == "Approved":
        row.status = "Closed"
    else:
        return
    row.version += 1
    row.modified_by = user.id
    row.modified_at = now()


def cancel_incident(db, user, project, row, data):
    if row.status not in {"Reported", "Under Investigation", "Returned for Correction"}:
        raise HTTPException(409, "This incident can no longer be cancelled")
    _bump(db, HseIncident, row, data.version, {"status": "Cancelled", "modified_by": user.id})
    return row


def _category_name(db, row):
    category = db.get(HseIncidentCategory, row.category_id)
    return category.name if category else ""


def incident_view(db, row):
    from app.domains.construction.models import WorkPackage

    package = db.get(WorkPackage, row.package_id) if row.package_id else None
    team = db.query(HseIncidentMember).filter_by(incident_id=row.id).all()
    return {
        "id": row.id,
        "number": row.number,
        "category": _category_name(db, row),
        "status": row.status,
        "event_at": row.event_at.isoformat() if row.event_at else None,
        "timezone_name": row.timezone_name,
        "reported_at": row.reported_at.isoformat() if row.reported_at else None,
        "description": row.description,
        "immediate_actions": row.immediate_actions,
        "emergency_requested": row.emergency_requested,
        "initial_severity": row.initial_severity,
        "evidence": row.evidence,
        "reporter_name": _name(db, row.reporter_id),
        "verified_classification": row.verified_classification,
        "contributing_factors": row.contributing_factors,
        "root_causes": row.root_causes,
        "lessons": row.lessons,
        "package_id": row.package_id,
        "package_status": package.status if package else "",
        "team": [{"id": item.user_id, "name": _name(db, item.user_id)} for item in team],
        "version": row.version,
        "statement": INCIDENT_NOTE,
    }


def add_action(db, user, project, data):
    company, _, _, _, member, _policy = _helpers()
    company(db, project, data.company_id)
    member(db, project, data.owner_id, "action owner")
    member(db, project, data.verifier_id, "verifier")
    if data.owner_id == data.verifier_id:
        raise HTTPException(422, "The action owner cannot be the verifier")
    _source(db, project, data.source_type, data.source_id)
    number_key = _key(data.number)
    if db.query(HseAction).filter_by(project_id=project.id, number_key=number_key).first():
        raise HTTPException(409, "That action number already exists")
    row = HseAction(
        organization_id=project.organization_id,
        project_id=project.id,
        number=data.number.strip(),
        number_key=number_key,
        source_type=data.source_type,
        source_id=data.source_id,
        description=data.description.strip(),
        severity=data.severity.strip(),
        company_id=data.company_id,
        owner_id=data.owner_id,
        verifier_id=data.verifier_id,
        due_on=data.due_on,
        interim_controls=data.interim_controls.strip(),
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    task = _task(db, user, project, data.owner_id, f"HSE action {row.number}", "hse.action", row.id, due_date=data.due_on)
    row.task_id = task.id
    db.flush()
    return row


def start_action(db, user, project, row, version):
    from app.domains.identity_projects.security import holds

    if user.id != row.owner_id and not holds(db, user, project, "hse.edit") and not holds(db, user, project, "hse.plan"):
        raise HTTPException(403, "Only the action owner can start this action")
    if row.status != "Open":
        raise HTTPException(409, "Only an open action can be started")
    _bump(db, HseAction, row, version, {"status": "In Progress", "modified_by": user.id})
    return row


def submit_evidence(db, user, project, row, data):
    if user.id != row.owner_id:
        raise HTTPException(403, "Only the action owner can submit evidence")
    if row.status not in {"Open", "In Progress", "Pending Verification"}:
        raise HTTPException(409, "This action is not open for evidence")
    _bump(
        db,
        HseAction,
        row,
        data.version,
        {"status": "Pending Verification", "evidence": data.evidence.strip(), "modified_by": user.id},
    )
    task = db.get(Task, row.task_id) if row.task_id else None
    if task and task.status not in {"Completed", "Cancelled"}:
        task.evidence = data.evidence.strip()
    from app.domains.identity_projects.models import User

    verifier = db.get(User, row.verifier_id)
    if verifier:
        notify(
            db,
            verifier,
            "Action evidence is ready",
            f"{row.number} is waiting for verification. The evidence does not close it.",
            f"hse.action.{row.id}.evidence",
            project_id=project.id,
            link=f"/projects/{project.id}",
        )
    return row


def close_action(db, user, project, row, data):
    if user.id != row.verifier_id:
        raise HTTPException(403, "Only the named verifier can close this action")
    if row.status != "Pending Verification":
        raise HTTPException(409, "Close an action after its evidence is submitted")
    rule = db.query(HseActionRule).filter_by(project_id=project.id).first()
    effectiveness = data.effectiveness.strip()
    if rule and rule.effectiveness_required and len(effectiveness) < 3:
        raise HTTPException(422, "Record the effectiveness review before closure")
    _bump(
        db,
        HseAction,
        row,
        data.version,
        {"status": "Closed", "effectiveness": effectiveness, "modified_by": user.id},
    )
    _close_tasks(db, project.id, "hse.action", row.id, "Completed", row.evidence)
    return row


def cancel_action(db, user, project, row, data):
    if row.status in {"Closed", "Cancelled"}:
        raise HTTPException(409, "This action is already finished")
    _bump(db, HseAction, row, data.version, {"status": "Cancelled", "modified_by": user.id})
    _close_tasks(db, project.id, "hse.action", row.id, "Cancelled", data.reason.strip())
    return row


def action_view(db, row):
    task = db.get(Task, row.task_id) if row.task_id else None
    return {
        "id": row.id,
        "number": row.number,
        "description": row.description,
        "severity": row.severity,
        "status": row.status,
        "owner_id": row.owner_id,
        "owner_name": _name(db, row.owner_id),
        "verifier_id": row.verifier_id,
        "verifier_name": _name(db, row.verifier_id),
        "due_on": row.due_on.isoformat() if row.due_on else None,
        "interim_controls": row.interim_controls,
        "evidence": row.evidence,
        "effectiveness": row.effectiveness,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "task_id": row.task_id,
        "task_status": task.status if task else "",
        "version": row.version,
        "statement": ACTION_NOTE,
    }


def supplement(db, user, project, payload):
    incidents = db.query(HseIncident).filter_by(project_id=project.id).order_by(HseIncident.id.desc()).all()
    actions = db.query(HseAction).filter_by(project_id=project.id).order_by(HseAction.id.desc()).all()
    rule = db.query(HseActionRule).filter_by(project_id=project.id).first()
    payload["incident_note"] = RATE_NOTE
    payload["incident_statement"] = INCIDENT_NOTE
    payload["action_note"] = ACTION_NOTE
    payload["suggested_incident_categories"] = list(SUGGESTED_INCIDENT_CATEGORIES)
    payload["incident_categories"] = [
        {"id": row.id, "name": row.name}
        for row in db.query(HseIncidentCategory).filter_by(project_id=project.id).order_by(HseIncidentCategory.name)
    ]
    payload["incident_rules"] = [
        {"id": row.id, "severity": row.severity, "requires_investigation": row.requires_investigation}
        for row in db.query(HseIncidentRule).filter_by(project_id=project.id)
    ]
    payload["incidents"] = [incident_view(db, row) for row in incidents]
    payload["action_rule"] = {"effectiveness_required": bool(rule.effectiveness_required) if rule else False}
    payload["actions"] = [action_view(db, row) for row in actions]
    payload["counts"]["incidents"] = len(incidents)
    payload["counts"]["open_incidents"] = sum(row.status not in {"Closed", "Cancelled", "Rejected"} for row in incidents)
    payload["counts"]["open_actions"] = sum(row.status not in {"Closed", "Cancelled"} for row in actions)
    return payload


def work_line():
    return {"incident_note": "An incident report does not hold work and does not replace the emergency response."}
