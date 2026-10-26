"""Shifts, crews, attendance, corrections, and period locks.

Crew membership is not attendance. Attendance hours are not Construction
activity hours. Proposed overtime is not approved or payable overtime.
Approved attendance changes only through an approved correction, and the
correction keeps the original values.
"""

from datetime import date, datetime, timedelta

from fastapi import HTTPException

from app.domains.coordination.service import REVIEW_GUARDS
from app.domains.engineering_documents.workflow import submit_record
from app.domains.identity_projects.models import Membership, User
from app.domains.identity_projects.security import holds

from .deployments import _area, _bump, _discipline, _overlaps, _person, _policy_for, _review_view
from .models import (
    ATTENDANCE_STATUSES,
    ATTRIBUTIONS,
    CORRECTION_KINDS,
    AttendanceCorrection,
    AttendanceLock,
    AttendanceRecord,
    AttendanceSegment,
    AttendanceSheet,
    Crew,
    CrewMember,
    Deployment,
    Personnel,
    Shift,
    WorkforceMaster,
    now,
)
from .service import _company_ids

SHEET = "hr.attendance"
CORRECTION = "hr.correction"
WORKED = {"Present", "Partial Attendance"}
MEMBER_DEPLOYMENTS = {"Approved for Mobilization", "Mobilized", "Temporarily Unavailable"}
ATTENDING_DEPLOYMENTS = {"Mobilized", "Temporarily Unavailable", "Demobilized"}
SHEET_EDITABLE = {"Draft", "Returned"}
OPEN_SHEETS = {"Draft", "Pending Review", "Returned"}
OPEN_CORRECTIONS = {"Pending Review", "Returned"}
LATE_DAYS = 2
CREW_NOTE = "Crew membership does not prove attendance or toolbox-talk participation. A person belongs to one crew at a time."
ATTENDANCE_NOTE = (
    "Attendance hours are separate from Construction activity hours. Proposed overtime is not approved or payable overtime. "
    "One segment has the shift break deducted; with several segments the gaps are the break."
)


# Shifts


def _shift_minutes(shift):
    start = shift.start_time.hour * 60 + shift.start_time.minute
    end = shift.end_time.hour * 60 + shift.end_time.minute
    length = (end - start) % 1440
    return length or 1440


def _check_shift(db, project, data, current=None):
    if data.attribution not in ATTRIBUTIONS:
        raise HTTPException(422, "Choose Start day or End day for attendance-day attribution")
    if data.effective_to and data.effective_to < data.effective_from:
        raise HTTPException(422, "Effective to cannot be before effective from")
    probe = Shift(start_time=data.start_time, end_time=data.end_time)
    if data.break_minutes >= _shift_minutes(probe):
        raise HTTPException(422, "The break is longer than the shift")
    key = data.code.strip().casefold()
    clash = db.query(Shift).filter(Shift.project_id == project.id, Shift.code_key == key)
    if current is not None:
        clash = clash.filter(Shift.id != current.id)
    if clash.first():
        raise HTTPException(409, f"Shift {data.code} already exists on this project")
    return key


def _shift_values(data):
    return {
        "code": data.code.strip(),
        "name": data.name.strip(),
        "start_time": data.start_time,
        "end_time": data.end_time,
        "break_minutes": data.break_minutes,
        "attribution": data.attribution,
        "calendar": data.calendar.strip(),
        "effective_from": data.effective_from,
        "effective_to": data.effective_to,
    }


def add_shift(db, user, project, data):
    key = _check_shift(db, project, data)
    row = Shift(
        organization_id=project.organization_id,
        project_id=project.id,
        code_key=key,
        created_by=user.id,
        modified_by=user.id,
        **_shift_values(data),
    )
    db.add(row)
    db.flush()
    return row


def save_shift(db, user, project, row, data):
    key = _check_shift(db, project, data, current=row)
    _bump(
        db,
        Shift,
        row,
        data.version,
        {**_shift_values(data), "code_key": key, "active": data.active, "modified_by": user.id, "modified_at": now()},
    )
    return row


def _shift(db, project, shift_id, on=None):
    row = db.get(Shift, shift_id) if shift_id else None
    if not row or row.project_id != project.id:
        raise HTTPException(422, "Choose a shift on this project")
    if on is not None:
        if not row.active or on < row.effective_from or (row.effective_to and on > row.effective_to):
            raise HTTPException(422, f"Shift {row.code} is not in effect on {on.isoformat()}")
    return row


# Crews


def _window(deployment):
    return deployment.actual_start or deployment.planned_start, deployment.actual_end or deployment.planned_end


def _check_crew(db, project, data, current=None):
    if data.company_id not in _company_ids(db, project):
        raise HTTPException(422, "The crew company is not active on this project")
    _discipline(db, project, data.discipline_id)
    if data.shift_id is not None:
        _shift(db, project, data.shift_id)
    if data.effective_to and data.effective_to < data.effective_from:
        raise HTTPException(422, "Effective to cannot be before effective from")
    if data.lead_id is not None:
        lead = _person(db, project, data.lead_id)
        if lead.company_id != data.company_id:
            raise HTTPException(422, "The crew lead must be employed by the crew company")
    _area(db, project, data.area_id)
    if data.trade_id is not None:
        trade = db.get(WorkforceMaster, data.trade_id)
        if not trade or trade.organization_id != project.organization_id or trade.kind != "Trade" or not trade.active:
            raise HTTPException(422, "Choose a trade from the workforce list")
    if data.supervisor_id is not None:
        member = db.query(Membership).filter_by(project_id=project.id, user_id=data.supervisor_id, active=True).first()
        target = db.get(User, data.supervisor_id)
        if not member or not target or not target.active:
            raise HTTPException(422, "The crew supervisor must be an active member of this project")
    key = data.code.strip().casefold()
    clash = db.query(Crew).filter(Crew.project_id == project.id, Crew.code_key == key)
    if current is not None:
        clash = clash.filter(Crew.id != current.id)
    if clash.first():
        raise HTTPException(409, f"Crew {data.code} already exists on this project")
    return key


def _crew_values(data, row=None):
    values = {
        "code": data.code.strip(),
        "company_id": data.company_id,
        "discipline_id": data.discipline_id,
        "lead_id": data.lead_id,
        "shift_id": data.shift_id,
        "effective_from": data.effective_from,
        "effective_to": data.effective_to,
    }
    # Older callers that do not send the Manpower fields keep what is stored.
    for field in ("name", "trade_id", "area_id", "supervisor_id"):
        if row is None or field in data.model_fields_set:
            value = getattr(data, field)
            values[field] = value.strip() if isinstance(value, str) else value
    return values


def add_crew(db, user, project, data):
    key = _check_crew(db, project, data)
    row = Crew(
        organization_id=project.organization_id,
        project_id=project.id,
        code_key=key,
        created_by=user.id,
        modified_by=user.id,
        **_crew_values(data),
    )
    db.add(row)
    db.flush()
    return row


def save_crew(db, user, project, row, data):
    key = _check_crew(db, project, data, current=row)
    if data.company_id != row.company_id and _members(db, row):
        raise HTTPException(409, "Remove the members before changing the crew company")
    _bump(
        db,
        Crew,
        row,
        data.version,
        {**_crew_values(data, row), "code_key": key, "active": data.active, "modified_by": user.id, "modified_at": now()},
    )
    return row


def _members(db, crew):
    return db.query(CrewMember).filter_by(crew_id=crew.id, active=True).order_by(CrewMember.start_date, CrewMember.id).all()


def add_member(db, user, project, crew, data):
    if not crew.active:
        raise HTTPException(409, "This crew is inactive")
    person = _person(db, project, data.personnel_id)
    if person.status != "Active":
        raise HTTPException(422, "Only an active person can join a crew")
    if person.company_id != crew.company_id:
        raise HTTPException(422, "Crew members must be employed by the crew company")
    if data.end_date and data.end_date < data.start_date:
        raise HTTPException(422, "Membership end cannot be before its start")
    if data.start_date < crew.effective_from or (crew.effective_to and (data.end_date is None or data.end_date > crew.effective_to)):
        raise HTTPException(422, "Membership dates must fall within the crew's effective dates")
    deployment = None
    for row in db.query(Deployment).filter(
        Deployment.project_id == project.id,
        Deployment.personnel_id == person.id,
        Deployment.status.in_(tuple(MEMBER_DEPLOYMENTS)),
    ):
        start, end = _window(row)
        if data.start_date >= start and (end is None or (data.end_date is not None and data.end_date <= end)):
            deployment = row
            break
    if deployment is None:
        raise HTTPException(422, "Membership dates must fall within an approved or mobilized deployment on this project")
    busy = (
        db.query(CrewMember)
        .join(Crew, Crew.id == CrewMember.crew_id)
        .filter(Crew.project_id == project.id, CrewMember.personnel_id == person.id, CrewMember.active.is_(True))
        .all()
    )
    for other in busy:
        if _overlaps(data.start_date, data.end_date, other.start_date, other.end_date):
            code = db.get(Crew, other.crew_id).code
            raise HTTPException(409, f"This person is already in crew {code} for those dates")
    _bump(db, Crew, crew, data.version, {"modified_by": user.id, "modified_at": now()})
    member = CrewMember(
        crew_id=crew.id,
        personnel_id=person.id,
        deployment_id=deployment.id,
        start_date=data.start_date,
        end_date=data.end_date,
        created_by=user.id,
    )
    db.add(member)
    db.flush()
    return member


def end_member(db, user, project, crew, member, data):
    if member.crew_id != crew.id or not member.active:
        raise HTTPException(404, "Crew member not found")
    if data.end_date < member.start_date:
        raise HTTPException(422, "Membership end cannot be before its start")
    if member.end_date and data.end_date > member.end_date:
        raise HTTPException(422, "Use a new membership to extend beyond the recorded end")
    _bump(db, Crew, crew, data.version, {"modified_by": user.id, "modified_at": now()})
    member.end_date = data.end_date
    member.removed_by = user.id
    member.removed_at = now()
    return member


# Attendance


def _locked(db, project, day):
    return (
        db.query(AttendanceLock)
        .filter(
            AttendanceLock.project_id == project.id,
            AttendanceLock.reopened_at.is_(None),
            AttendanceLock.period_start <= day,
            AttendanceLock.period_end >= day,
        )
        .first()
    )


def _open_period(db, project, day):
    lock = _locked(db, project, day)
    if lock:
        raise HTTPException(409, f"Attendance from {lock.period_start.isoformat()} to {lock.period_end.isoformat()} is locked")


def add_sheet(db, user, project, data):
    if data.attendance_date > date.today():
        raise HTTPException(422, "Attendance cannot be recorded for a future date")
    _open_period(db, project, data.attendance_date)
    shift = _shift(db, project, data.shift_id, on=data.attendance_date)
    crew = None
    if data.crew_id is not None:
        crew = db.get(Crew, data.crew_id)
        if not crew or crew.project_id != project.id or not crew.active:
            raise HTTPException(422, "Choose an active crew on this project")
        if data.attendance_date < crew.effective_from or (crew.effective_to and data.attendance_date > crew.effective_to):
            raise HTTPException(422, f"Crew {crew.code} is not in effect on that date")
        if crew.shift_id and crew.shift_id != shift.id:
            raise HTTPException(422, f"Crew {crew.code} works another shift")
    clash = db.query(AttendanceSheet).filter_by(
        project_id=project.id, attendance_date=data.attendance_date, shift_id=shift.id, crew_id=data.crew_id
    )
    if clash.filter(AttendanceSheet.status != "Rejected").first():
        raise HTTPException(409, "A sheet for that date, shift, and crew already exists")
    row = AttendanceSheet(
        organization_id=project.organization_id,
        project_id=project.id,
        shift_id=shift.id,
        crew_id=data.crew_id,
        attendance_date=data.attendance_date,
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def _naive(value):
    return value.replace(tzinfo=None) if value.tzinfo else value


def _clean_segments(shift, day, status, segments):
    if status not in ATTENDANCE_STATUSES:
        raise HTTPException(422, "Choose an attendance status from the list")
    pairs = sorted(((_naive(s.check_in), _naive(s.check_out)) for s in segments), key=lambda pair: pair[0])
    if status in WORKED and not pairs:
        raise HTTPException(422, f"{status} needs at least one check-in and check-out")
    if status not in WORKED and pairs:
        raise HTTPException(422, f"{status} cannot have check-in or check-out times")
    if not pairs:
        return pairs
    for start, end in pairs:
        if end <= start:
            raise HTTPException(422, "Check-out must be after check-in")
    for (_, prev_end), (next_start, _) in zip(pairs, pairs[1:]):
        if next_start < prev_end:
            raise HTTPException(422, "Work segments overlap each other")
    if pairs[-1][1] - pairs[0][0] > timedelta(hours=24):
        raise HTTPException(422, "One attendance record cannot span more than 24 hours")
    anchor = pairs[0][0].date() if shift.attribution == "Start day" else pairs[-1][1].date()
    if anchor != day:
        side = "check-in" if shift.attribution == "Start day" else "check-out"
        raise HTTPException(422, f"Shift {shift.code} counts the day of the {side}. It must be {day.isoformat()}")
    return pairs


def _hours(shift, pairs):
    total = sum(int((end - start).total_seconds() // 60) for start, end in pairs)
    worked = max(0, total - shift.break_minutes) if len(pairs) == 1 else total
    scheduled = _shift_minutes(shift) - shift.break_minutes
    regular = min(worked, scheduled)
    return worked, regular, worked - regular


def _conflicts(db, project, personnel_id, pairs, skip_id=None):
    if not pairs:
        return
    first, last = pairs[0][0], pairs[-1][1]
    rows = (
        db.query(AttendanceSegment, AttendanceRecord)
        .join(AttendanceRecord, AttendanceRecord.id == AttendanceSegment.attendance_id)
        .filter(
            AttendanceRecord.project_id == project.id,
            AttendanceRecord.personnel_id == personnel_id,
            AttendanceSegment.check_in < last,
            AttendanceSegment.check_out > first,
        )
    )
    if skip_id:
        rows = rows.filter(AttendanceRecord.id != skip_id)
    for segment, record in rows:
        for start, end in pairs:
            if segment.check_in < end and segment.check_out > start:
                raise HTTPException(409, f"These times overlap attendance already recorded on {record.attendance_date.isoformat()}")


def _attending_deployment(db, project, person, day):
    for row in db.query(Deployment).filter(
        Deployment.project_id == project.id,
        Deployment.personnel_id == person.id,
        Deployment.status.in_(tuple(ATTENDING_DEPLOYMENTS)),
    ):
        if row.actual_start and row.actual_start <= day and (row.actual_end is None or day <= row.actual_end):
            return row
    raise HTTPException(422, "This person was not mobilized on this project on that date")


def _replace_segments(db, record, pairs):
    db.query(AttendanceSegment).filter_by(attendance_id=record.id).delete()
    for start, end in pairs:
        db.add(AttendanceSegment(attendance_id=record.id, check_in=start, check_out=end))


def put_record(db, user, project, sheet, data):
    if sheet.status not in SHEET_EDITABLE:
        raise HTTPException(409, "Only a draft or returned sheet can be changed. Use a correction for approved attendance")
    _open_period(db, project, sheet.attendance_date)
    person = _person(db, project, data.personnel_id)
    if sheet.crew_id:
        member = (
            db.query(CrewMember)
            .filter(CrewMember.crew_id == sheet.crew_id, CrewMember.personnel_id == person.id, CrewMember.active.is_(True))
            .all()
        )
        if not any(_overlaps(sheet.attendance_date, sheet.attendance_date, m.start_date, m.end_date) for m in member):
            raise HTTPException(422, "This person is not in the crew on that date")
    deployment = _attending_deployment(db, project, person, sheet.attendance_date)
    shift = db.get(Shift, sheet.shift_id)
    pairs = _clean_segments(shift, sheet.attendance_date, data.status, data.segments)
    record = (
        db.query(AttendanceRecord)
        .filter_by(project_id=project.id, personnel_id=person.id, attendance_date=sheet.attendance_date, shift_id=shift.id)
        .first()
    )
    if record and record.sheet_id != sheet.id:
        raise HTTPException(409, "This person already has attendance for that date and shift on another sheet")
    _conflicts(db, project, person.id, pairs, skip_id=record.id if record else None)
    worked, regular, overtime = _hours(shift, pairs)
    _bump(db, AttendanceSheet, sheet, data.version, {"modified_by": user.id, "modified_at": now()})
    if record is None:
        record = AttendanceRecord(
            sheet_id=sheet.id,
            project_id=project.id,
            personnel_id=person.id,
            shift_id=shift.id,
            attendance_date=sheet.attendance_date,
            created_by=user.id,
        )
        db.add(record)
    record.deployment_id = deployment.id
    record.status = data.status
    record.worked_minutes = worked
    record.regular_minutes = regular
    record.overtime_minutes = overtime
    record.remarks = data.remarks.strip()
    record.modified_by = user.id
    record.modified_at = now()
    db.flush()
    _replace_segments(db, record, pairs)
    db.flush()
    return record


def remove_record(db, user, project, sheet, data):
    if sheet.status not in SHEET_EDITABLE:
        raise HTTPException(409, "Only a draft or returned sheet can be changed")
    record = db.query(AttendanceRecord).filter_by(sheet_id=sheet.id, personnel_id=data.personnel_id).first()
    if not record:
        raise HTTPException(404, "This person is not on the sheet")
    _bump(db, AttendanceSheet, sheet, data.version, {"modified_by": user.id, "modified_at": now()})
    db.query(AttendanceSegment).filter_by(attendance_id=record.id).delete()
    db.delete(record)
    db.flush()


def _sheet_company(db, sheet):
    crew = db.get(Crew, sheet.crew_id) if sheet.crew_id else None
    return (crew.company_id, crew.discipline_id) if crew else (None, None)


def submit_sheet(db, user, project, sheet, version):
    if sheet.status != "Draft":
        raise HTTPException(409, "Only a draft sheet can be submitted")
    _open_period(db, project, sheet.attendance_date)
    if not db.query(AttendanceRecord).filter_by(sheet_id=sheet.id).count():
        raise HTTPException(422, "Add attendance for at least one person first")
    company_id, discipline_id = _sheet_company(db, sheet)
    policy = _policy_for(db, project, SHEET, company_id, discipline_id)
    late = (date.today() - sheet.attendance_date).days > LATE_DAYS
    _bump(
        db,
        AttendanceSheet,
        sheet,
        version,
        {"status": "Pending Review", "late": late, "submitted_by": user.id, "modified_by": user.id, "modified_at": now()},
    )
    return submit_record(db, user, project, SHEET, sheet.id, sheet.version, policy)


# Corrections


def _snapshot(db, record):
    segments = db.query(AttendanceSegment).filter_by(attendance_id=record.id).order_by(AttendanceSegment.check_in).all()
    return {
        "status": record.status,
        "segments": [[s.check_in.isoformat(timespec="minutes"), s.check_out.isoformat(timespec="minutes")] for s in segments],
        "worked_minutes": record.worked_minutes,
        "regular_minutes": record.regular_minutes,
        "overtime_minutes": record.overtime_minutes,
    }


def _proposal(db, project, record, status, segments):
    shift = db.get(Shift, record.shift_id)
    pairs = _clean_segments(shift, record.attendance_date, status, segments)
    _conflicts(db, project, record.personnel_id, pairs, skip_id=record.id)
    worked, regular, overtime = _hours(shift, pairs)
    return pairs, {
        "status": status,
        "segments": [[a.isoformat(timespec="minutes"), b.isoformat(timespec="minutes")] for a, b in pairs],
        "worked_minutes": worked,
        "regular_minutes": regular,
        "overtime_minutes": overtime,
    }


def request_correction(db, user, project, record, data):
    sheet = db.get(AttendanceSheet, record.sheet_id)
    if sheet.status != "Approved":
        raise HTTPException(409, "Edit the sheet directly until it is approved")
    person = db.get(Personnel, record.personnel_id)
    if not holds(db, user, project, "hr.attendance") and person.user_id != user.id:
        raise HTTPException(403, "Only attendance recorders or the person can request a correction")
    if data.kind not in CORRECTION_KINDS:
        raise HTTPException(422, "Choose a correction type from the list")
    _open_period(db, project, record.attendance_date)
    if (
        db.query(AttendanceCorrection)
        .filter(AttendanceCorrection.attendance_id == record.id, AttendanceCorrection.status.in_(tuple(OPEN_CORRECTIONS)))
        .first()
    ):
        raise HTTPException(409, "A correction for this attendance is already open")
    _, proposed = _proposal(db, project, record, data.status, data.segments)
    original = _snapshot(db, record)
    if proposed["status"] == original["status"] and proposed["segments"] == original["segments"]:
        raise HTTPException(422, "The proposed values match the recorded attendance")
    deployment = db.get(Deployment, record.deployment_id)
    policy = _policy_for(db, project, CORRECTION, deployment.company_id, deployment.discipline_id)
    row = AttendanceCorrection(
        organization_id=project.organization_id,
        project_id=project.id,
        attendance_id=record.id,
        kind=data.kind,
        original=original,
        proposed=proposed,
        reason=data.reason.strip(),
        evidence=data.evidence.strip(),
        requested_by=user.id,
    )
    db.add(row)
    db.flush()
    submit_record(db, user, project, CORRECTION, row.id, row.version, policy)
    return row


def _apply_correction(db, user, project, row):
    record = db.get(AttendanceRecord, row.attendance_id)
    _open_period(db, project, record.attendance_date)

    class Pair:
        def __init__(self, pair):
            self.check_in = datetime.fromisoformat(pair[0])
            self.check_out = datetime.fromisoformat(pair[1])

    pairs, proposed = _proposal(db, project, record, row.proposed["status"], [Pair(p) for p in row.proposed["segments"]])
    record.status = proposed["status"]
    record.worked_minutes = proposed["worked_minutes"]
    record.regular_minutes = proposed["regular_minutes"]
    record.overtime_minutes = proposed["overtime_minutes"]
    record.version += 1
    record.modified_by = user.id
    record.modified_at = now()
    _replace_segments(db, record, pairs)
    row.status = "Approved"
    row.applied_at = now()


# Locks


def lock_period(db, user, project, data):
    if data.period_end < data.period_start:
        raise HTTPException(422, "Period end cannot be before its start")
    for lock in db.query(AttendanceLock).filter_by(project_id=project.id).filter(AttendanceLock.reopened_at.is_(None)):
        if _overlaps(data.period_start, data.period_end, lock.period_start, lock.period_end):
            raise HTTPException(409, "Part of that period is already locked")
    within = (
        AttendanceSheet.project_id == project.id,
        AttendanceSheet.attendance_date >= data.period_start,
        AttendanceSheet.attendance_date <= data.period_end,
    )
    waiting = db.query(AttendanceSheet).filter(*within, AttendanceSheet.status.in_(tuple(OPEN_SHEETS))).count()
    if waiting:
        raise HTTPException(409, f"{waiting} attendance sheet(s) in that period are not decided yet")
    open_corrections = (
        db.query(AttendanceCorrection)
        .join(AttendanceRecord, AttendanceRecord.id == AttendanceCorrection.attendance_id)
        .filter(
            AttendanceCorrection.project_id == project.id,
            AttendanceCorrection.status.in_(tuple(OPEN_CORRECTIONS)),
            AttendanceRecord.attendance_date >= data.period_start,
            AttendanceRecord.attendance_date <= data.period_end,
        )
        .count()
    )
    if open_corrections:
        raise HTTPException(409, f"{open_corrections} correction(s) in that period are still open")
    row = AttendanceLock(
        project_id=project.id,
        period_start=data.period_start,
        period_end=data.period_end,
        reason=data.reason.strip(),
        locked_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def reopen_period(db, user, project, row, data):
    if row.reopened_at is not None:
        raise HTTPException(409, "This period is already reopened")
    row.reopened_by = user.id
    row.reopened_at = now()
    row.reopen_reason = data.reason.strip()
    return row


# Review engine hooks


def on_review_event(db, user, instance, project, action, stage=None):
    if action == "advance":
        return
    if instance.record_type == SHEET:
        row = db.get(AttendanceSheet, instance.record_id)
        if not row or row.project_id != project.id:
            return
        if action == "return":
            row.status = "Returned"
        elif action == "reject":
            row.status = "Rejected"
        elif instance.state == "Approved":
            row.status = "Approved"
        else:
            return
        row.version += 1
        row.modified_by = user.id
        row.modified_at = now()
        return
    row = db.get(AttendanceCorrection, instance.record_id)
    if not row or row.project_id != project.id:
        return
    if action == "return":
        row.status = "Returned"
    elif action == "reject":
        row.status = "Rejected"
    elif instance.state == "Approved":
        _apply_correction(db, user, project, row)
    else:
        return
    row.version += 1
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
    if instance.record_type == SHEET:
        row = db.get(AttendanceSheet, instance.record_id)
        if not row or row.status != "Returned":
            raise HTTPException(409, "Only a returned sheet can be resubmitted")
        _open_period(db, project, row.attendance_date)
        if not db.query(AttendanceRecord).filter_by(sheet_id=row.id).count():
            raise HTTPException(422, "Add attendance for at least one person first")
        company_id, discipline_id = _sheet_company(db, row)
        policy = _policy_for(db, project, SHEET, company_id, discipline_id)
        _bump(db, AttendanceSheet, row, row.version, {"status": "Pending Review", "modified_by": user.id, "modified_at": now()})
    else:
        row = db.get(AttendanceCorrection, instance.record_id)
        if not row or row.status != "Returned":
            raise HTTPException(409, "Only a returned correction can be resubmitted")
        record = db.get(AttendanceRecord, row.attendance_id)
        _open_period(db, project, record.attendance_date)
        deployment = db.get(Deployment, record.deployment_id)
        policy = _policy_for(db, project, CORRECTION, deployment.company_id, deployment.discipline_id)
        _bump(db, AttendanceCorrection, row, row.version, {"status": "Pending Review", "modified_at": now()})
    _lock(db, instance, review_version)
    close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    instance.record_version = row.version
    instance.policy_id = policy.id
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def review_guard(db, user, instance, stage, action):
    if action != "approve" or instance.record_type not in {SHEET, CORRECTION}:
        return
    if user.id == instance.submitted_by:
        raise HTTPException(403, "You cannot approve your own submission")
    if instance.record_type == SHEET:
        own = (
            db.query(AttendanceRecord)
            .join(Personnel, Personnel.id == AttendanceRecord.personnel_id)
            .filter(AttendanceRecord.sheet_id == instance.record_id, Personnel.user_id == user.id)
            .first()
        )
        if own:
            raise HTTPException(403, "You cannot approve a sheet that holds your own attendance")
        return
    row = db.get(AttendanceCorrection, instance.record_id)
    record = db.get(AttendanceRecord, row.attendance_id) if row else None
    person = db.get(Personnel, record.personnel_id) if record else None
    if person and person.user_id == user.id:
        raise HTTPException(403, "You cannot approve a correction to your own attendance")


if review_guard not in REVIEW_GUARDS:
    REVIEW_GUARDS.append(review_guard)


# Views


def _hm(minutes):
    return f"{minutes // 60}:{minutes % 60:02d}"


def shift_view(row):
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "start_time": row.start_time.strftime("%H:%M"),
        "end_time": row.end_time.strftime("%H:%M"),
        "break_minutes": row.break_minutes,
        "overnight": row.end_time <= row.start_time,
        "scheduled": _hm(_shift_minutes(row) - row.break_minutes),
        "attribution": row.attribution,
        "calendar": row.calendar,
        "effective_from": row.effective_from.isoformat(),
        "effective_to": row.effective_to.isoformat() if row.effective_to else None,
        "active": row.active,
        "version": row.version,
    }


def crew_view(db, row, names, people):
    from app.domains.identity_projects.models import Area

    shift = db.get(Shift, row.shift_id) if row.shift_id else None
    area = db.get(Area, row.area_id) if row.area_id else None
    supervisor = db.get(User, row.supervisor_id) if row.supervisor_id else None
    members = db.query(CrewMember).filter_by(crew_id=row.id).order_by(CrewMember.start_date, CrewMember.id).all()
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "company_id": row.company_id,
        "company_name": names["company"].get(row.company_id, ""),
        "discipline_id": row.discipline_id,
        "discipline": names["discipline"].get(row.discipline_id, "") if row.discipline_id else "",
        "trade_id": row.trade_id,
        "trade": names.get("master", {}).get(row.trade_id, "") if row.trade_id else "",
        "area_id": row.area_id,
        "area": f"{area.code} · {area.name}" if area else "",
        "supervisor_id": row.supervisor_id,
        "supervisor": supervisor.name if supervisor else "",
        "lead_id": row.lead_id,
        "lead": people.get(row.lead_id, ""),
        "shift_id": row.shift_id,
        "shift": shift.code if shift else "",
        "effective_from": row.effective_from.isoformat(),
        "effective_to": row.effective_to.isoformat() if row.effective_to else None,
        "active": row.active,
        "version": row.version,
        "members": [
            {
                "id": m.id,
                "personnel_id": m.personnel_id,
                "deployment_id": m.deployment_id,
                "person": people.get(m.personnel_id, ""),
                "start_date": m.start_date.isoformat(),
                "end_date": m.end_date.isoformat() if m.end_date else None,
                "active": m.active and (m.end_date is None or m.end_date >= date.today()),
            }
            for m in members
            if m.active
        ],
    }


def _on_leave(db, project, personnel_id, day):
    from .leave import approved_leave

    return approved_leave(db, project, personnel_id, day) is not None


def sheet_view(db, user, project, row, people, users):
    shift = db.get(Shift, row.shift_id)
    crew = db.get(Crew, row.crew_id) if row.crew_id else None
    records = db.query(AttendanceRecord).filter_by(sheet_id=row.id).order_by(AttendanceRecord.id).all()
    items = []
    for record in records:
        snap = _snapshot(db, record)
        person = db.get(Personnel, record.personnel_id)
        items.append(
            {
                "id": record.id,
                "personnel_id": record.personnel_id,
                "person": people.get(record.personnel_id, ""),
                "own": bool(person and person.user_id == user.id),
                "on_leave": record.status in WORKED and _on_leave(db, project, record.personnel_id, record.attendance_date),
                "status": record.status,
                "source": record.source,
                "segments": snap["segments"],
                "worked": _hm(record.worked_minutes),
                "regular": _hm(record.regular_minutes),
                "overtime": _hm(record.overtime_minutes),
                "remarks": record.remarks,
                "version": record.version,
            }
        )
    return {
        "id": row.id,
        "attendance_date": row.attendance_date.isoformat(),
        "shift_id": row.shift_id,
        "shift": f"{shift.code} · {shift.start_time.strftime('%H:%M')}–{shift.end_time.strftime('%H:%M')}" if shift else "",
        "crew_id": row.crew_id,
        "crew": crew.code if crew else "",
        "status": row.status,
        "late": row.late,
        "submitted_by": users.get(row.submitted_by, "") if row.submitted_by else "",
        "locked": bool(_locked(db, project, row.attendance_date)),
        "version": row.version,
        "records": items,
        "review": _review_view(db, user, project, SHEET, row.id),
    }


def correction_view(db, user, project, row, people, users):
    record = db.get(AttendanceRecord, row.attendance_id)
    return {
        "id": row.id,
        "attendance_id": row.attendance_id,
        "person": people.get(record.personnel_id, "") if record else "",
        "attendance_date": record.attendance_date.isoformat() if record else "",
        "kind": row.kind,
        "original": {**row.original, "worked": _hm(row.original.get("worked_minutes", 0))},
        "proposed": {**row.proposed, "worked": _hm(row.proposed.get("worked_minutes", 0))},
        "reason": row.reason,
        "evidence": row.evidence,
        "status": row.status,
        "requested_by": users.get(row.requested_by, ""),
        "applied_at": row.applied_at.isoformat() if row.applied_at else None,
        "version": row.version,
        "review": _review_view(db, user, project, CORRECTION, row.id),
    }


def supplement(db, user, project, payload, names):
    today = date.today()
    people = {
        row.id: f"{row.code} · {row.full_name}"
        for row in db.query(Personnel).filter(Personnel.organization_id == project.organization_id)
    }
    users = {row.id: row.name for row in db.query(User).filter(User.organization_id == project.organization_id)}
    shifts = db.query(Shift).filter_by(project_id=project.id).order_by(Shift.code).all()
    crews = db.query(Crew).filter_by(project_id=project.id).order_by(Crew.code).all()
    sheets = (
        db.query(AttendanceSheet)
        .filter_by(project_id=project.id)
        .order_by(AttendanceSheet.attendance_date.desc(), AttendanceSheet.id.desc())
        .limit(60)
        .all()
    )
    corrections = (
        db.query(AttendanceCorrection).filter_by(project_id=project.id).order_by(AttendanceCorrection.id.desc()).limit(60).all()
    )
    locks = db.query(AttendanceLock).filter_by(project_id=project.id).order_by(AttendanceLock.period_start.desc()).all()
    payload["shifts"] = [shift_view(row) for row in shifts]
    payload["crews"] = [crew_view(db, row, names, people) for row in crews]
    payload["sheets"] = [sheet_view(db, user, project, row, people, users) for row in sheets]
    payload["corrections"] = [correction_view(db, user, project, row, people, users) for row in corrections]
    payload["locks"] = [
        {
            "id": row.id,
            "period_start": row.period_start.isoformat(),
            "period_end": row.period_end.isoformat(),
            "reason": row.reason,
            "locked_by": users.get(row.locked_by, ""),
            "reopened": row.reopened_at is not None,
            "reopened_by": users.get(row.reopened_by, "") if row.reopened_by else "",
            "reopen_reason": row.reopen_reason,
        }
        for row in locks
    ]
    payload["attendance_statuses"] = list(ATTENDANCE_STATUSES)
    payload["correction_kinds"] = list(CORRECTION_KINDS)
    payload["attributions"] = list(ATTRIBUTIONS)
    payload["crew_note"] = CREW_NOTE
    payload["attendance_note"] = ATTENDANCE_NOTE
    payload["can_attend"] = holds(db, user, project, "hr.attendance")

    todays = db.query(AttendanceRecord).filter_by(project_id=project.id, attendance_date=today).all()
    present = {}
    for record in todays:
        if record.status in WORKED:
            code = next((s.code for s in shifts if s.id == record.shift_id), "")
            present.setdefault(code, set()).add(record.personnel_id)
    recorded = {record.personnel_id for record in todays}
    mobilized = {
        row.personnel_id
        for row in db.query(Deployment).filter_by(project_id=project.id, status="Mobilized")
        if row.actual_start and row.actual_start <= today and (row.actual_end is None or today <= row.actual_end)
    }
    from .models import Leave

    away = {record.personnel_id for record in todays if record.status in {"Absent", "On Leave", "Weekly Off/Holiday"}}
    away |= {
        row.personnel_id
        for row in db.query(Leave).filter(
            Leave.project_id == project.id, Leave.status == "Approved", Leave.start_date <= today, Leave.end_date >= today
        )
    }
    payload["present_by_shift"] = {code: len(ids) for code, ids in present.items()}
    payload["counts"].update(
        {
            "present_today": len(set().union(*present.values())) if present else 0,
            "available_today": len(mobilized - away),
            "missing_attendance": len(mobilized - recorded),
            "pending_sheets": sum(1 for row in sheets if row.status == "Pending Review"),
            "pending_corrections": sum(1 for row in corrections if row.status == "Pending Review"),
            "active_crews": sum(1 for row in crews if row.active),
        }
    )
    payload["attendance_count_note"] = (
        f"Present, available, and missing are for {today.isoformat()} and include sheets not yet approved. "
        "Available is mobilized, not on approved leave, and not recorded absent, on leave, or off. It is not task eligibility."
    )
    return payload
