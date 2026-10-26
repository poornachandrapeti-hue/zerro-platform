"""Demobilization and offboarding.

A deployment leaves the project only through an approved offboarding: the last
working date, a checklist, and an `hr.offboarding` approval. Approval ends the
deployment, releases allocations, and ends crew memberships after the last
working date. It never removes a project membership or a login, and never
touches access on other projects; it asks an organization administrator to
review this project's access. Nothing is deleted.
"""

from datetime import date

from fastapi import HTTPException

from app.domains.coordination.service import REVIEW_GUARDS
from app.domains.engineering_documents.workflow import submit_record
from app.domains.identity_projects.models import Membership, User

from .deployments import _bump, _policy_for, _release_lines, _review_view
from .models import (
    OFFBOARDING_ITEMS,
    AttendanceCorrection,
    AttendanceRecord,
    AttendanceSheet,
    CrewMember,
    Deployment,
    Offboarding,
    OffboardingItem,
    Personnel,
    RequestLine,
    now,
)

OFFBOARDING = "hr.offboarding"
LIVE = {"Draft", "Pending Approval", "Returned"}
EDITABLE = {"Draft", "Returned"}
LEAVING = {"Mobilized", "Temporarily Unavailable"}
OPEN_TASK = "Open task reassignment"
TIMESHEET = "Outstanding timesheet review"
OFFBOARDING_NOTE = (
    "Demobilization needs the checklist and an approval. Approval ends the deployment, releases allocations, "
    "and ends crew memberships after the last working date. It does not remove a project membership or a login, "
    "and access on other projects is not touched. History is kept."
)


def _deployment(db, project, deployment_id):
    row = db.get(Deployment, deployment_id)
    if not row or row.project_id != project.id:
        raise HTTPException(422, "Choose a deployment on this project")
    return row


def _items(db, row):
    return db.query(OffboardingItem).filter_by(offboarding_id=row.id).order_by(OffboardingItem.id).all()


def open_tasks(db, project, person):
    from app.domains.coordination.models import Task

    if not person.user_id:
        return []
    return (
        db.query(Task)
        .filter(Task.project_id == project.id, Task.owner_id == person.user_id, Task.status.notin_(("Completed", "Cancelled")))
        .order_by(Task.id)
        .all()
    )


def pending_timesheets(db, project, person):
    records = (
        db.query(AttendanceRecord, AttendanceSheet)
        .join(AttendanceSheet, AttendanceSheet.id == AttendanceRecord.sheet_id)
        .filter(AttendanceRecord.project_id == project.id, AttendanceRecord.personnel_id == person.id)
        .all()
    )
    sheets = sorted({sheet.attendance_date.isoformat() for _, sheet in records if sheet.status in {"Draft", "Pending Review", "Returned"}})
    ids = [record.id for record, _ in records]
    corrections = (
        db.query(AttendanceCorrection)
        .filter(AttendanceCorrection.attendance_id.in_(ids or [-1]), AttendanceCorrection.status.in_(("Pending Review", "Returned")))
        .count()
    )
    return sheets, corrections


def findings(db, project, row):
    """What still ties this person to the project. Worked out live; nothing is changed."""
    person = db.get(Personnel, row.personnel_id)
    tasks = open_tasks(db, project, person)
    sheets, corrections = pending_timesheets(db, project, person)
    crews = (
        db.query(CrewMember)
        .filter(
            CrewMember.deployment_id == row.deployment_id,
            CrewMember.active.is_(True),
            (CrewMember.end_date.is_(None)) | (CrewMember.end_date > row.last_working_date),
        )
        .count()
    )
    from app.domains.manpower.models import Assignment

    allocations = db.query(RequestLine).filter_by(deployment_id=row.deployment_id, state="Allocated").count()
    allocations += (
        db.query(Assignment)
        .filter(
            Assignment.deployment_id == row.deployment_id,
            Assignment.state.in_(("Proposed", "Confirmed")),
            Assignment.work_date > row.last_working_date,
        )
        .count()
    )
    login = db.get(User, person.user_id) if person.user_id else None
    here = (
        db.query(Membership).filter_by(project_id=project.id, user_id=login.id, active=True).count() if login and login.active else 0
    )
    elsewhere = (
        db.query(Membership)
        .filter(Membership.user_id == login.id, Membership.active.is_(True), Membership.project_id != project.id)
        .count()
        if login and login.active
        else 0
    )
    after = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.project_id == project.id,
            AttendanceRecord.personnel_id == person.id,
            AttendanceRecord.attendance_date > row.last_working_date,
            AttendanceRecord.status.in_(("Present", "Partial Attendance")),
        )
        .count()
    )
    return {
        "open_tasks": [{"id": task.id, "title": task.title, "due_date": task.due_date.isoformat() if task.due_date else None} for task in tasks],
        "pending_sheets": sheets,
        "pending_corrections": corrections,
        "crew_memberships": crews,
        "allocations": allocations,
        "login_active": bool(login and login.active),
        "project_memberships": here,
        "other_project_memberships": elsewhere,
        "attendance_after_last_day": after,
    }


def _notify_open_tasks(db, project, row, person, count):
    if not count:
        return
    from app.domains.coordination.jobs import notify

    deployment = db.get(Deployment, row.deployment_id)
    boss = db.get(Personnel, deployment.supervisor_id) if deployment and deployment.supervisor_id else None
    for user_id in {person.user_id, boss.user_id if boss else None} - {None}:
        login = db.get(User, user_id)
        if login and login.active:
            notify(
                db,
                login,
                "Demobilization has open tasks",
                f"{person.code} is being demobilized and still owns {count} open task{'s' if count != 1 else ''} on this project. Reassign them.",
                f"hr:offboarding:{row.id}:open-tasks:{login.id}",
                project_id=project.id,
                link=f"/projects/{project.id}",
            )


def add_offboarding(db, user, project, data):
    deployment = _deployment(db, project, data.deployment_id)
    if deployment.status not in LEAVING:
        raise HTTPException(409, "Only a mobilized or temporarily unavailable deployment can be demobilized")
    if db.query(Offboarding).filter(Offboarding.deployment_id == deployment.id, Offboarding.status.in_(tuple(LIVE))).first():
        raise HTTPException(409, "This deployment already has an open offboarding")
    person = db.get(Personnel, deployment.personnel_id)
    if deployment.actual_start and data.last_working_date < deployment.actual_start:
        raise HTTPException(422, "The last working date is before mobilization")
    if person.end_date and data.last_working_date > person.end_date:
        raise HTTPException(422, "The last working date is after this person's employment end date")
    row = Offboarding(
        organization_id=project.organization_id,
        project_id=project.id,
        deployment_id=deployment.id,
        personnel_id=person.id,
        company_id=deployment.company_id,
        last_working_date=data.last_working_date,
        reason=data.reason.strip(),
        requested_by=user.id,
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(row)
    db.flush()
    for name in OFFBOARDING_ITEMS:
        db.add(OffboardingItem(offboarding_id=row.id, item=name))
    db.flush()
    _notify_open_tasks(db, project, row, person, len(open_tasks(db, project, person)))
    return row


def save_item(db, user, project, row, item, data):
    if item.offboarding_id != row.id:
        raise HTTPException(404, "Checklist item not found")
    if row.status not in EDITABLE:
        raise HTTPException(409, "The checklist is edited before submission")
    if data.status != "Pending" and len(data.note.strip()) < 3:
        raise HTTPException(422, "Record what was done or why it does not apply")
    person = db.get(Personnel, row.personnel_id)
    if data.status == "Done" and item.item == OPEN_TASK:
        count = len(open_tasks(db, project, person))
        if count:
            raise HTTPException(409, f"{count} open task{'s' if count != 1 else ''} still belong to this person on the project")
    if data.status == "Done" and item.item == TIMESHEET:
        sheets, corrections = pending_timesheets(db, project, person)
        if sheets or corrections:
            raise HTTPException(409, "Attendance sheets or corrections for this person are still waiting for review")
    _bump(
        db,
        OffboardingItem,
        item,
        data.version,
        {
            "status": data.status,
            "note": data.note.strip(),
            "done_by": user.id if data.status != "Pending" else None,
            "done_at": now() if data.status != "Pending" else None,
        },
    )
    return item


def _ready(db, project, row):
    pending = [item.item for item in _items(db, row) if item.status == "Pending"]
    if pending:
        raise HTTPException(409, "Complete the checklist first: " + ", ".join(pending))
    found = findings(db, project, row)
    if found["open_tasks"]:
        raise HTTPException(409, "Reassign this person's open tasks first")
    if found["pending_sheets"] or found["pending_corrections"]:
        raise HTTPException(409, "Attendance for this person is still waiting for review")
    if found["attendance_after_last_day"]:
        raise HTTPException(409, "Attendance is recorded after the last working date")
    if row.last_working_date > date.today():
        raise HTTPException(409, "Submit on or after the last working date")
    deployment = db.get(Deployment, row.deployment_id)
    if deployment.status not in LEAVING:
        raise HTTPException(409, "The deployment is no longer on site")
    person = db.get(Personnel, row.personnel_id)
    return _policy_for(db, project, OFFBOARDING, row.company_id, deployment.discipline_id or person.discipline_id)


def submit_offboarding(db, user, project, row, version):
    if row.status != "Draft":
        raise HTTPException(409, "Only a draft offboarding can be submitted")
    policy = _ready(db, project, row)
    _bump(db, Offboarding, row, version, {"status": "Pending Approval", "modified_by": user.id, "modified_at": now()})
    return submit_record(db, user, project, OFFBOARDING, row.id, row.version, policy)


def cancel_offboarding(db, user, project, row, data):
    if row.status not in EDITABLE:
        raise HTTPException(409, "Only a draft or returned offboarding can be cancelled")
    _bump(
        db,
        Offboarding,
        row,
        data.version,
        {"status": "Cancelled", "status_reason": data.reason.strip(), "modified_by": user.id, "modified_at": now()},
    )
    return row


def _complete(db, user, project, row):
    deployment = db.get(Deployment, row.deployment_id)
    deployment.status = "Demobilized"
    deployment.actual_end = row.last_working_date
    deployment.status_reason = "Demobilized through approved offboarding"
    deployment.version += 1
    deployment.modified_by = user.id
    deployment.modified_at = now()
    _release_lines(db, deployment, "Demobilized")
    from app.domains.manpower.allocation import release_after

    release_after(db, user, deployment, row.last_working_date, "Demobilized through approved offboarding")
    for member in db.query(CrewMember).filter(CrewMember.deployment_id == deployment.id, CrewMember.active.is_(True)):
        if member.end_date is None or member.end_date > row.last_working_date:
            member.end_date = max(row.last_working_date, member.start_date)
    person = db.get(Personnel, row.personnel_id)
    login = db.get(User, person.user_id) if person.user_id else None
    if not login or not login.active:
        return
    if not db.query(Membership).filter_by(project_id=project.id, user_id=login.id, active=True).first():
        return
    from app.domains.coordination.jobs import notify

    for admin in db.query(User).filter_by(organization_id=project.organization_id, organization_admin=True, active=True):
        notify(
            db,
            admin,
            "Project access review needed",
            f"{person.code} was demobilized and still has access to this project. Review it in People & access. Other projects are not affected.",
            f"hr:offboarding:{row.id}:access-review:{admin.id}",
            project_id=project.id,
            link=f"/projects/{project.id}",
        )


def on_review_event(db, user, instance, project, action, stage=None):
    if action == "advance":
        return
    row = db.get(Offboarding, instance.record_id)
    if not row or row.project_id != project.id:
        return
    if action == "return":
        row.status = "Returned"
    elif action == "reject":
        row.status = "Rejected"
    elif instance.state == "Approved":
        row.status = "Approved"
        row.approved_at = now()
        _complete(db, user, project, row)
    else:
        return
    row.version += 1
    row.modified_by = user.id
    row.modified_at = now()


def apply_resubmit(db, user, instance, review_version):
    from app.domains.coordination.service import _close_tasks as close_tasks
    from app.domains.coordination.service import _lock, _open_stage, current_stage
    from app.domains.identity_projects.models import Project

    if instance.state != "Returned":
        raise HTTPException(409, "Only a returned review can be resubmitted")
    if user.id != instance.submitted_by and not user.organization_admin:
        raise HTTPException(403, "Only the submitter can resubmit")
    project = db.get(Project, instance.project_id)
    row = db.get(Offboarding, instance.record_id)
    if not row or row.status != "Returned":
        raise HTTPException(409, "Only a returned offboarding can be resubmitted")
    policy = _ready(db, project, row)
    _lock(db, instance, review_version)
    close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    _bump(db, Offboarding, row, row.version, {"status": "Pending Approval", "modified_by": user.id, "modified_at": now()})
    instance.record_version = row.version
    instance.policy_id = policy.id
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def review_guard(db, user, instance, stage, action):
    if action != "approve" or instance.record_type != OFFBOARDING:
        return
    if user.id == instance.submitted_by:
        raise HTTPException(403, "You cannot approve your own submission")
    row = db.get(Offboarding, instance.record_id)
    person = db.get(Personnel, row.personnel_id) if row else None
    if person and person.user_id == user.id:
        raise HTTPException(403, "You cannot approve your own demobilization")
    deployment = db.get(Deployment, row.deployment_id) if row else None
    if not deployment or deployment.status not in LEAVING:
        raise HTTPException(409, "The deployment is no longer on site")


if review_guard not in REVIEW_GUARDS:
    REVIEW_GUARDS.append(review_guard)


def offboarding_view(db, user, project, row, users):
    person = db.get(Personnel, row.personnel_id)
    return {
        "id": row.id,
        "deployment_id": row.deployment_id,
        "personnel_id": row.personnel_id,
        "person": f"{person.code} · {person.full_name}" if person else "",
        "last_working_date": row.last_working_date.isoformat(),
        "reason": row.reason,
        "status": row.status,
        "status_reason": row.status_reason,
        "requester": users.get(row.requested_by, ""),
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "version": row.version,
        "items": [
            {
                "id": item.id,
                "item": item.item,
                "status": item.status,
                "note": item.note,
                "done_by": users.get(item.done_by, "") if item.done_by else "",
                "version": item.version,
            }
            for item in _items(db, row)
        ],
        "findings": findings(db, project, row) if row.status in LIVE else None,
        "review": _review_view(db, user, project, OFFBOARDING, row.id),
    }


def supplement(db, user, project, payload):
    users = {row.id: row.name for row in db.query(User).filter(User.organization_id == project.organization_id)}
    rows = db.query(Offboarding).filter_by(project_id=project.id).order_by(Offboarding.id.desc()).limit(80).all()
    payload["offboardings"] = [offboarding_view(db, user, project, row, users) for row in rows]
    payload["offboarding_note"] = OFFBOARDING_NOTE
    payload["counts"]["open_offboardings"] = sum(1 for row in rows if row.status in LIVE)
    return payload
