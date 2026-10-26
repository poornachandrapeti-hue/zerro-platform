"""Daily returns: planned work against HR attendance and Construction labour.

A return compares, for one date and shift, each person's confirmed assignment
minutes with the minutes HR attendance recorded and the minutes approved
Construction progress booked. It never edits attendance, assignments, or progress.
"""

from datetime import date

from fastapi import HTTPException

from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import holds
from app.domains.workforce.attendance import _hm, _shift
from app.domains.workforce.deployments import _bump
from app.domains.workforce.models import AttendanceRecord, AttendanceSheet, Personnel, now

from .models import Assignment, DailyReturn, ReturnLine

TOLERANCE = 30
RETURN_NOTE = (
    "A daily return compares confirmed assignments with HR attendance and approved Construction labour for one "
    "date and shift. It does not change attendance, assignments, or progress. Every flagged person needs a "
    "reason before submission, and the person who submits cannot accept."
)


def _planned(db, project, day, shift_id):
    totals = {}
    for row in db.query(Assignment).filter(
        Assignment.project_id == project.id,
        Assignment.work_date == day,
        Assignment.shift_id == shift_id,
        Assignment.state == "Confirmed",
    ):
        totals[row.personnel_id] = totals.get(row.personnel_id, 0) + row.planned_minutes
    return totals


def _attended(db, project, day, shift_id):
    out = {}
    rows = (
        db.query(AttendanceRecord, AttendanceSheet.status)
        .join(AttendanceSheet, AttendanceSheet.id == AttendanceRecord.sheet_id)
        .filter(
            AttendanceRecord.project_id == project.id,
            AttendanceRecord.attendance_date == day,
            AttendanceRecord.shift_id == shift_id,
        )
    )
    for record, sheet_status in rows:
        out[record.personnel_id] = {
            "minutes": record.worked_minutes,
            "status": record.status,
            "approved": sheet_status == "Approved",
        }
    return out


def _attended_day(db, project, day):
    totals = {}
    for row in db.query(AttendanceRecord).filter(
        AttendanceRecord.project_id == project.id, AttendanceRecord.attendance_date == day
    ):
        totals[row.personnel_id] = totals.get(row.personnel_id, 0) + row.worked_minutes
    return totals


def _booked(db, project, day):
    from app.domains.construction.models import ProgressLabour, ProgressReport

    totals = {}
    rows = (
        db.query(ProgressLabour)
        .join(ProgressReport, ProgressReport.id == ProgressLabour.report_id)
        .filter(
            ProgressReport.project_id == project.id,
            ProgressReport.report_date == day,
            ProgressReport.status == "Approved",
        )
    )
    for row in rows:
        totals[row.personnel_id] = totals.get(row.personnel_id, 0) + row.productive_minutes + row.idle_minutes
    return totals


def reconcile(db, project, day, shift):
    """Live lines for every person planned or attended on this date and shift."""
    planned = _planned(db, project, day, shift.id)
    attended = _attended(db, project, day, shift.id)
    booked = _booked(db, project, day)
    day_total = _attended_day(db, project, day)
    lines = []
    for pid in set(planned) | set(attended):
        plan = planned.get(pid, 0)
        seen = attended.get(pid)
        worked = seen["minutes"] if seen else 0
        flags = []
        if plan and not seen:
            flags.append("no attendance recorded")
        elif seen and not seen["approved"]:
            flags.append("attendance not approved yet")
        if plan and seen and seen["status"] in ("Absent", "On Leave"):
            flags.append(f"assigned but {seen['status'].lower()}")
        if worked and not plan:
            flags.append("attended without an assignment")
        if plan and worked and abs(worked - plan) > TOLERANCE:
            flags.append(f"attended {_hm(worked)} against {_hm(plan)} planned")
        if booked.get(pid, 0) > day_total.get(pid, 0):
            flags.append(
                f"booked {_hm(booked[pid])} on activities, more than {_hm(day_total.get(pid, 0))} attended that day"
            )
        lines.append(
            {
                "personnel_id": pid,
                "planned_minutes": plan,
                "attended_minutes": worked,
                "booked_minutes": booked.get(pid, 0),
                "attendance": seen["status"] if seen else "",
                "flags": flags,
            }
        )
    return lines


def _stored(db, row):
    return [
        {
            "personnel_id": line.personnel_id,
            "planned_minutes": line.planned_minutes,
            "attended_minutes": line.attended_minutes,
            "booked_minutes": line.booked_minutes,
            "attendance": line.attendance,
            "flags": [text for text in line.flags.split("; ") if text],
            "reason": line.reason,
        }
        for line in db.query(ReturnLine).filter(ReturnLine.return_id == row.id).order_by(ReturnLine.id)
    ]


def _key(lines):
    return sorted(
        (line["personnel_id"], line["planned_minutes"], line["attended_minutes"], line["booked_minutes"])
        for line in lines
    )


def _name(db, user_id):
    user = db.get(User, user_id) if user_id else None
    return user.name if user else ""


def view(db, user, project, names, day, shift_id):
    shift = _shift(db, project, shift_id)
    row = db.query(DailyReturn).filter_by(project_id=project.id, work_date=day, shift_id=shift.id).one_or_none()
    live = reconcile(db, project, day, shift)
    stored = _stored(db, row) if row else []
    frozen = row is not None and row.state in ("Submitted", "Accepted")
    reasons = {line["personnel_id"]: line["reason"] for line in stored}
    lines = stored if frozen else [{**line, "reason": reasons.get(line["personnel_id"], "")} for line in live]
    people = {
        person.id: person
        for person in db.query(Personnel).filter(Personnel.id.in_({line["personnel_id"] for line in lines} or {-1}))
    }
    out = []
    for line in sorted(lines, key=lambda item: people[item["personnel_id"]].code):
        person = people[line["personnel_id"]]
        out.append(
            {
                **line,
                "person": f"{person.code} · {person.full_name}",
                "trade": names["master"].get(person.trade_id, ""),
                "planned": _hm(line["planned_minutes"]),
                "attended": _hm(line["attended_minutes"]),
                "booked": _hm(line["booked_minutes"]),
            }
        )
    return {
        "note": RETURN_NOTE,
        "work_date": day.isoformat(),
        "shift": shift.code,
        "record": (
            {
                "id": row.id,
                "state": row.state,
                "note": row.note,
                "return_reason": row.return_reason,
                "submitted_by": _name(db, row.submitted_by),
                "submitted_at": row.submitted_at.isoformat() if row.submitted_at else "",
                "accepted_by": _name(db, row.accepted_by),
                "version": row.version,
            }
            if row
            else None
        ),
        "lines": out,
        "changed": frozen and _key(live) != _key(stored),
        "flagged": sum(1 for line in out if line["flags"]),
        "can_submit": holds(db, user, project, "manpower.returns"),
        "can_accept": holds(db, user, project, "manpower.coordinate"),
    }


def submit(db, user, project, data):
    shift = _shift(db, project, data.shift_id, on=data.work_date)
    if data.work_date > date.today():
        raise HTTPException(422, "A return can only cover today or an earlier date")
    row = (
        db.query(DailyReturn)
        .filter_by(project_id=project.id, work_date=data.work_date, shift_id=shift.id)
        .with_for_update()
        .one_or_none()
    )
    if row and row.state != "Returned":
        raise HTTPException(409, "This return is already submitted")
    lines = reconcile(db, project, data.work_date, shift)
    if not lines:
        raise HTTPException(422, "Nothing to return: no confirmed assignments or attendance on this shift")
    reasons = {item.personnel_id: item.reason.strip() for item in data.reasons}
    missing = [line["personnel_id"] for line in lines if line["flags"] and len(reasons.get(line["personnel_id"], "")) < 3]
    if missing:
        codes = [person.code for person in db.query(Personnel).filter(Personnel.id.in_(missing)).order_by(Personnel.code)]
        raise HTTPException(422, f"Give a reason for every flagged person: {', '.join(codes)}")
    values = {
        "state": "Submitted",
        "note": data.note.strip(),
        "return_reason": "",
        "submitted_by": user.id,
        "submitted_at": now(),
        "modified_at": now(),
    }
    if row is None:
        row = DailyReturn(
            organization_id=project.organization_id,
            project_id=project.id,
            work_date=data.work_date,
            shift_id=shift.id,
            created_by=user.id,
            **values,
        )
        db.add(row)
        db.flush()
    else:
        if data.version is None:
            raise HTTPException(409, "This record changed. Reload it and try again")
        _bump(db, DailyReturn, row, data.version, values)
        db.query(ReturnLine).filter(ReturnLine.return_id == row.id).delete()
    for line in lines:
        db.add(
            ReturnLine(
                return_id=row.id,
                personnel_id=line["personnel_id"],
                planned_minutes=line["planned_minutes"],
                attended_minutes=line["attended_minutes"],
                booked_minutes=line["booked_minutes"],
                attendance=line["attendance"],
                flags="; ".join(line["flags"]),
                reason=reasons.get(line["personnel_id"], ""),
            )
        )
    db.flush()
    return row


def accept(db, user, project, row, version):
    if row.state != "Submitted":
        raise HTTPException(409, "Only a submitted return can be accepted")
    if row.submitted_by == user.id:
        raise HTTPException(403, "You cannot accept a return you submitted")
    _bump(db, DailyReturn, row, version, {"state": "Accepted", "accepted_by": user.id, "accepted_at": now(), "modified_at": now()})
    return row


def send_back(db, user, project, row, data):
    if row.state != "Submitted":
        raise HTTPException(409, "Only a submitted return can be sent back")
    if row.submitted_by == user.id:
        raise HTTPException(403, "You cannot send back a return you submitted")
    _bump(db, DailyReturn, row, data.version, {"state": "Returned", "return_reason": data.reason.strip(), "modified_at": now()})
    return row
