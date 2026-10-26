"""Leave, temporary unavailability, and overtime.

Approved leave lowers availability and flags affected crew memberships,
allocations, and attendance. It never deletes an assignment or changes a
construction schedule. Requested, approved, attended, and payable overtime are
kept apart; payable here means approved and attended, not paid.
"""

from datetime import date, datetime

from fastapi import HTTPException

from app.domains.coordination.service import REVIEW_GUARDS
from app.domains.engineering_documents.workflow import submit_record
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import holds

from .attendance import MEMBER_DEPLOYMENTS, _open_period, _shift, _window
from .deployments import _bump, _overlaps, _person, _policy_for, _review_view
from .models import (
    AttendanceRecord,
    AttendanceSheet,
    Crew,
    CrewMember,
    Deployment,
    Leave,
    Overtime,
    Personnel,
    RequestLine,
    WorkforceMaster,
    WorkforceRequest,
    now,
)
from .service import sees_restricted

LEAVE = "hr.leave"
OVERTIME = "hr.overtime"
EDITABLE = {"Draft", "Returned"}
LIVE = {"Draft", "Pending Approval", "Approved", "Returned"}
LEAVE_NOTE = (
    "Approved leave lowers availability and flags affected crews, allocations, and attendance. "
    "It does not delete assignments or change schedules. Leave balances and entitlements are not tracked."
)
OVERTIME_NOTE = (
    "Requested, approved, attended, and payable overtime are separate. Attended comes from approved attendance. "
    "Payable is approved and attended; it is not a payment."
)


def _hm(minutes):
    return f"{minutes // 60}:{minutes % 60:02d}"


def _may_act_for(db, user, project, person):
    if holds(db, user, project, "hr.attendance") or holds(db, user, project, "hr.edit") or person.user_id == user.id:
        return
    raise HTTPException(403, "Only HR, attendance recorders, or the person can request leave")


# Leave


def _leave_type(db, project, type_id, current=None):
    row = db.get(WorkforceMaster, type_id)
    if not row or row.organization_id != project.organization_id or row.kind != "Leave type":
        raise HTTPException(422, "Choose a leave type from the workforce list")
    if not row.active and (current is None or current.leave_type_id != row.id):
        raise HTTPException(422, f"Leave type {row.name} is no longer active")
    return row


def _check_leave(db, project, person, data, current=None):
    _leave_type(db, project, data.leave_type_id, current)
    if data.end_date < data.start_date:
        raise HTTPException(422, "Leave end cannot be before its start")
    if (data.start_time is None) != (data.end_time is None):
        raise HTTPException(422, "Enter both start and end times, or neither for full days")
    if data.start_time is not None:
        if data.start_date != data.end_date:
            raise HTTPException(422, "Times are for part of a single day")
        if data.end_time <= data.start_time:
            raise HTTPException(422, "Leave end time must be after its start time")
    if data.start_date < person.start_date or (person.end_date and data.end_date > person.end_date):
        raise HTTPException(422, "Leave falls outside this person's employment")
    others = db.query(Leave).filter(Leave.personnel_id == person.id, Leave.status.in_(tuple(LIVE)))
    if current is not None:
        others = others.filter(Leave.id != current.id)
    for row in others:
        if _overlaps(data.start_date, data.end_date, row.start_date, row.end_date):
            raise HTTPException(409, f"This person already has leave from {row.start_date.isoformat()} to {row.end_date.isoformat()}")


def _leave_values(data):
    return {
        "leave_type_id": data.leave_type_id,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "start_time": data.start_time,
        "end_time": data.end_time,
        "reason": data.reason.strip(),
        "evidence": data.evidence.strip(),
    }


def add_leave(db, user, project, data):
    person = _person(db, project, data.personnel_id)
    _may_act_for(db, user, project, person)
    _check_leave(db, project, person, data)
    row = Leave(
        organization_id=project.organization_id,
        project_id=project.id,
        personnel_id=person.id,
        company_id=person.company_id,
        requested_by=user.id,
        created_by=user.id,
        modified_by=user.id,
        **_leave_values(data),
    )
    db.add(row)
    db.flush()
    return row


def _owner_or_hr(db, user, project, row, verb):
    if user.id != row.requested_by and not holds(db, user, project, "hr.edit"):
        raise HTTPException(403, f"Only the requester or HR can {verb} this")


def save_leave(db, user, project, row, data):
    if row.status not in EDITABLE:
        raise HTTPException(409, "Only draft or returned leave can be edited")
    _owner_or_hr(db, user, project, row, "edit")
    if data.personnel_id != row.personnel_id:
        raise HTTPException(422, "Leave stays with the same person")
    person = db.get(Personnel, row.personnel_id)
    _check_leave(db, project, person, data, current=row)
    _bump(db, Leave, row, data.version, {**_leave_values(data), "modified_by": user.id, "modified_at": now()})
    return row


def submit_leave(db, user, project, row, version):
    if row.status != "Draft":
        raise HTTPException(409, "Only draft leave can be submitted")
    _owner_or_hr(db, user, project, row, "submit")
    person = db.get(Personnel, row.personnel_id)
    policy = _policy_for(db, project, LEAVE, row.company_id, person.discipline_id)
    _bump(db, Leave, row, version, {"status": "Pending Approval", "modified_by": user.id, "modified_at": now()})
    return submit_record(db, user, project, LEAVE, row.id, row.version, policy)


def cancel_leave(db, user, project, row, data):
    if row.status not in {"Draft", "Returned", "Approved"}:
        raise HTTPException(409, "This leave cannot be cancelled now")
    _owner_or_hr(db, user, project, row, "cancel")
    _bump(
        db,
        Leave,
        row,
        data.version,
        {"status": "Cancelled", "status_reason": data.reason.strip(), "modified_by": user.id, "modified_at": now()},
    )
    return row


def leave_effects(db, project, row):
    """Assignments the leave touches. Nothing is changed; these are flags."""
    effects = []
    members = (
        db.query(CrewMember, Crew)
        .join(Crew, Crew.id == CrewMember.crew_id)
        .filter(Crew.project_id == project.id, CrewMember.personnel_id == row.personnel_id, CrewMember.active.is_(True))
        .all()
    )
    for member, crew in members:
        if _overlaps(row.start_date, row.end_date, member.start_date, member.end_date):
            effects.append(f"Crew {crew.code}")
    lines = (
        db.query(RequestLine, WorkforceRequest)
        .join(WorkforceRequest, WorkforceRequest.id == RequestLine.request_id)
        .filter(
            WorkforceRequest.project_id == project.id,
            RequestLine.personnel_id == row.personnel_id,
            RequestLine.state == "Allocated",
        )
        .all()
    )
    for _, request in lines:
        if _overlaps(row.start_date, row.end_date, request.start_date, request.end_date):
            effects.append(f"Allocated to request {request.number}")
    worked = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.project_id == project.id,
            AttendanceRecord.personnel_id == row.personnel_id,
            AttendanceRecord.attendance_date >= row.start_date,
            AttendanceRecord.attendance_date <= row.end_date,
            AttendanceRecord.status.in_(("Present", "Partial Attendance")),
        )
        .all()
    )
    for record in worked:
        effects.append(f"Attendance recorded present on {record.attendance_date.isoformat()}")
    return effects


def _notify_effects(db, project, row):
    from app.domains.coordination.jobs import notify

    effects = [text for text in leave_effects(db, project, row) if text.startswith("Crew") or text.startswith("Allocated")]
    if not effects:
        return
    person = db.get(Personnel, row.personnel_id)
    recipients = set()
    for deployment in db.query(Deployment).filter_by(project_id=project.id, personnel_id=person.id):
        boss = db.get(Personnel, deployment.supervisor_id) if deployment.supervisor_id else None
        if boss and boss.user_id:
            recipients.add(boss.user_id)
    for member, crew in (
        db.query(CrewMember, Crew)
        .join(Crew, Crew.id == CrewMember.crew_id)
        .filter(Crew.project_id == project.id, CrewMember.personnel_id == person.id)
    ):
        lead = db.get(Personnel, crew.lead_id) if crew.lead_id else None
        if lead and lead.user_id:
            recipients.add(lead.user_id)
    for user_id in recipients:
        target = db.get(User, user_id)
        if target and target.active:
            notify(
                db,
                target,
                "Leave affects an assignment",
                f"Approved leave for {person.code} from {row.start_date.isoformat()} to {row.end_date.isoformat()} affects: {', '.join(effects)}.",
                f"hr:leave:{row.id}:effects",
                project_id=project.id,
                link=f"/projects/{project.id}",
            )


def approved_leave(db, project, personnel_id, day):
    return (
        db.query(Leave)
        .filter(
            Leave.project_id == project.id,
            Leave.personnel_id == personnel_id,
            Leave.status == "Approved",
            Leave.start_date <= day,
            Leave.end_date >= day,
        )
        .first()
    )


# Overtime


def _targets(db, row):
    if row.personnel_id:
        return [row.personnel_id]
    return [
        member.personnel_id
        for member in db.query(CrewMember).filter_by(crew_id=row.crew_id, active=True)
        if _overlaps(row.work_date, row.work_date, member.start_date, member.end_date)
    ]


def _check_overtime(db, project, data, current=None):
    if (data.personnel_id is None) == (data.crew_id is None):
        raise HTTPException(422, "Choose one person or one crew")
    _open_period(db, project, data.work_date)
    _shift(db, project, data.shift_id, on=data.work_date)
    if data.package_id is not None:
        from app.domains.construction.models import WorkPackage

        package = db.get(WorkPackage, data.package_id)
        if not package or package.project_id != project.id:
            raise HTTPException(422, "Choose a work package on this project")
    if data.personnel_id is not None:
        person = _person(db, project, data.personnel_id)
        covered = False
        for deployment in db.query(Deployment).filter(
            Deployment.project_id == project.id,
            Deployment.personnel_id == person.id,
            Deployment.status.in_(tuple(MEMBER_DEPLOYMENTS)),
        ):
            start, end = _window(deployment)
            if start <= data.work_date and (end is None or data.work_date <= end):
                covered = True
        if not covered:
            raise HTTPException(422, "This person is not deployed on this project on that date")
        company_id = person.company_id
        clash = db.query(Overtime).filter(Overtime.personnel_id == person.id)
    else:
        crew = db.get(Crew, data.crew_id)
        if not crew or crew.project_id != project.id or not crew.active:
            raise HTTPException(422, "Choose an active crew on this project")
        probe = Overtime(crew_id=crew.id, work_date=data.work_date)
        if not _targets(db, probe):
            raise HTTPException(422, f"Crew {crew.code} has no members on that date")
        company_id = crew.company_id
        clash = db.query(Overtime).filter(Overtime.crew_id == crew.id)
    clash = clash.filter(
        Overtime.project_id == project.id,
        Overtime.work_date == data.work_date,
        Overtime.shift_id == data.shift_id,
        Overtime.status.in_(tuple(LIVE)),
    )
    if current is not None:
        clash = clash.filter(Overtime.id != current.id)
    if clash.first():
        raise HTTPException(409, "Overtime is already requested for that date and shift")
    return company_id


def add_overtime(db, user, project, data):
    company_id = _check_overtime(db, project, data)
    row = Overtime(
        organization_id=project.organization_id,
        project_id=project.id,
        personnel_id=data.personnel_id,
        crew_id=data.crew_id,
        company_id=company_id,
        work_date=data.work_date,
        shift_id=data.shift_id,
        package_id=data.package_id,
        requested_minutes=data.requested_minutes,
        reason=data.reason.strip(),
        requested_by=user.id,
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def _overtime_discipline(db, row):
    if row.crew_id:
        return db.get(Crew, row.crew_id).discipline_id
    return db.get(Personnel, row.personnel_id).discipline_id


def submit_overtime(db, user, project, row, version):
    if row.status != "Draft":
        raise HTTPException(409, "Only draft overtime can be submitted")
    _owner_or_hr(db, user, project, row, "submit")
    _open_period(db, project, row.work_date)
    policy = _policy_for(db, project, OVERTIME, row.company_id, _overtime_discipline(db, row))
    _bump(db, Overtime, row, version, {"status": "Pending Approval", "modified_by": user.id, "modified_at": now()})
    return submit_record(db, user, project, OVERTIME, row.id, row.version, policy)


def set_approved_minutes(db, user, project, row, data):
    if row.status != "Pending Approval":
        raise HTTPException(409, "Approved hours are set while the request is awaiting approval")
    review = _review_view(db, user, project, OVERTIME, row.id)
    if not review or "approve" not in review.get("actions", []):
        raise HTTPException(403, "Only the assigned approver can set approved hours")
    if data.approved_minutes > row.requested_minutes:
        raise HTTPException(422, "Approved hours cannot exceed requested hours")
    _bump(db, Overtime, row, data.version, {"approved_minutes": data.approved_minutes, "modified_by": user.id, "modified_at": now()})
    return row


def cancel_overtime(db, user, project, row, data):
    if row.status not in {"Draft", "Returned", "Approved"}:
        raise HTTPException(409, "This overtime cannot be cancelled now")
    _owner_or_hr(db, user, project, row, "cancel")
    _bump(
        db,
        Overtime,
        row,
        data.version,
        {"status": "Cancelled", "status_reason": data.reason.strip(), "modified_by": user.id, "modified_at": now()},
    )
    return row


def _attended(db, row, personnel_id):
    return sum(
        record.overtime_minutes
        for record in db.query(AttendanceRecord)
        .join(AttendanceSheet, AttendanceSheet.id == AttendanceRecord.sheet_id)
        .filter(
            AttendanceRecord.project_id == row.project_id,
            AttendanceRecord.personnel_id == personnel_id,
            AttendanceRecord.attendance_date == row.work_date,
            AttendanceRecord.shift_id == row.shift_id,
            AttendanceSheet.status == "Approved",
        )
    )


# Review engine hooks


def on_review_event(db, user, instance, project, action, stage=None):
    if action == "advance":
        return
    model = Leave if instance.record_type == LEAVE else Overtime
    row = db.get(model, instance.record_id)
    if not row or row.project_id != project.id:
        return
    if action == "return":
        row.status = "Returned"
    elif action == "reject":
        row.status = "Rejected"
    elif instance.state == "Approved":
        row.status = "Approved"
        if model is Overtime and row.approved_minutes is None:
            row.approved_minutes = row.requested_minutes
        if model is Leave:
            _notify_effects(db, project, row)
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
    model = Leave if instance.record_type == LEAVE else Overtime
    row = db.get(model, instance.record_id)
    if not row or row.status != "Returned":
        raise HTTPException(409, "Only a returned request can be resubmitted")
    if model is Leave:
        person = db.get(Personnel, row.personnel_id)
        policy = _policy_for(db, project, LEAVE, row.company_id, person.discipline_id)
    else:
        _open_period(db, project, row.work_date)
        policy = _policy_for(db, project, OVERTIME, row.company_id, _overtime_discipline(db, row))
    _lock(db, instance, review_version)
    close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    _bump(db, model, row, row.version, {"status": "Pending Approval", "modified_by": user.id, "modified_at": now()})
    instance.record_version = row.version
    instance.policy_id = policy.id
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def review_guard(db, user, instance, stage, action):
    if action != "approve" or instance.record_type not in {LEAVE, OVERTIME}:
        return
    if user.id == instance.submitted_by:
        raise HTTPException(403, "You cannot approve your own submission")
    if instance.record_type == LEAVE:
        row = db.get(Leave, instance.record_id)
        person = db.get(Personnel, row.personnel_id) if row else None
        if person and person.user_id == user.id:
            raise HTTPException(403, "You cannot approve your own leave")
        return
    row = db.get(Overtime, instance.record_id)
    if not row:
        return
    mine = db.query(Personnel).filter(Personnel.id.in_(_targets(db, row) or [-1]), Personnel.user_id == user.id).first()
    if mine:
        raise HTTPException(403, "You cannot approve overtime that includes you")


if review_guard not in REVIEW_GUARDS:
    REVIEW_GUARDS.append(review_guard)


# Views


def _duration(row):
    if row.start_time is not None:
        start = datetime.combine(row.start_date, row.start_time)
        end = datetime.combine(row.end_date, row.end_time)
        return f"{_hm(int((end - start).total_seconds() // 60))} h"
    days = (row.end_date - row.start_date).days + 1
    return f"{days} day" + ("" if days == 1 else "s")


def leave_view(db, user, project, row, names, people, users, restricted):
    person = db.get(Personnel, row.personnel_id)
    sees = restricted or row.requested_by == user.id or (person and person.user_id == user.id)
    return {
        "id": row.id,
        "personnel_id": row.personnel_id,
        "person": people.get(row.personnel_id, ""),
        "company_name": names["company"].get(row.company_id, ""),
        "leave_type_id": row.leave_type_id,
        "leave_type": names["master"].get(row.leave_type_id, ""),
        "start_date": row.start_date.isoformat(),
        "end_date": row.end_date.isoformat(),
        "start_time": row.start_time.strftime("%H:%M") if row.start_time else None,
        "end_time": row.end_time.strftime("%H:%M") if row.end_time else None,
        "duration": _duration(row),
        "reason": row.reason if sees else None,
        "evidence": row.evidence if sees else None,
        "requested_by": row.requested_by,
        "requester": users.get(row.requested_by, ""),
        "mine": row.requested_by == user.id,
        "status": row.status,
        "status_reason": row.status_reason,
        "effects": leave_effects(db, project, row) if row.status in {"Pending Approval", "Approved"} else [],
        "version": row.version,
        "review": _review_view(db, user, project, LEAVE, row.id),
    }


def overtime_view(db, user, project, row, people, users, shifts, packages):
    crew = db.get(Crew, row.crew_id) if row.crew_id else None
    approved = row.approved_minutes if row.status == "Approved" else None
    lines = []
    for personnel_id in _targets(db, row):
        attended = _attended(db, row, personnel_id)
        lines.append(
            {
                "personnel_id": personnel_id,
                "person": people.get(personnel_id, ""),
                "attended": _hm(attended),
                "payable": _hm(min(approved, attended)) if approved is not None else "0:00",
            }
        )
    review = _review_view(db, user, project, OVERTIME, row.id)
    return {
        "id": row.id,
        "target": f"Crew {crew.code}" if crew else people.get(row.personnel_id, ""),
        "crew_id": row.crew_id,
        "personnel_id": row.personnel_id,
        "work_date": row.work_date.isoformat(),
        "shift": shifts.get(row.shift_id, ""),
        "package": packages.get(row.package_id, "") if row.package_id else "",
        "requested": _hm(row.requested_minutes),
        "requested_minutes": row.requested_minutes,
        "approved": _hm(row.approved_minutes) if row.approved_minutes is not None else None,
        "approved_minutes": row.approved_minutes,
        "reason": row.reason,
        "requester": users.get(row.requested_by, ""),
        "mine": row.requested_by == user.id,
        "status": row.status,
        "status_reason": row.status_reason,
        "can_set_hours": row.status == "Pending Approval" and bool(review and "approve" in review.get("actions", [])),
        "lines": lines,
        "version": row.version,
        "review": review,
    }


def supplement(db, user, project, payload, names):
    from app.domains.construction.models import WorkPackage

    from .models import Shift

    today = date.today()
    people = {
        row.id: f"{row.code} · {row.full_name}"
        for row in db.query(Personnel).filter(Personnel.organization_id == project.organization_id)
    }
    users = {row.id: row.name for row in db.query(User).filter(User.organization_id == project.organization_id)}
    shifts = {row.id: row.code for row in db.query(Shift).filter_by(project_id=project.id)}
    packages = {row.id: row.code for row in db.query(WorkPackage).filter_by(project_id=project.id)}
    restricted = sees_restricted(db, user, project)
    leaves = db.query(Leave).filter_by(project_id=project.id).order_by(Leave.start_date.desc(), Leave.id.desc()).limit(80).all()
    overtime = db.query(Overtime).filter_by(project_id=project.id).order_by(Overtime.work_date.desc(), Overtime.id.desc()).limit(80).all()
    payload["leaves"] = [leave_view(db, user, project, row, names, people, users, restricted) for row in leaves]
    payload["overtime"] = [overtime_view(db, user, project, row, people, users, shifts, packages) for row in overtime]
    payload["leave_note"] = LEAVE_NOTE
    payload["overtime_note"] = OVERTIME_NOTE
    on_leave = {
        row.personnel_id
        for row in db.query(Leave).filter(
            Leave.project_id == project.id, Leave.status == "Approved", Leave.start_date <= today, Leave.end_date >= today
        )
    }
    payload["counts"].update(
        {
            "on_leave_today": len(on_leave),
            "pending_leave": sum(1 for row in leaves if row.status == "Pending Approval"),
            "pending_overtime": sum(1 for row in overtime if row.status == "Pending Approval"),
        }
    )
    from .reconcile import supplement as reconcile

    return reconcile(db, user, project, payload, people)
