"""Attendance against Construction activity hours.

Only approved attendance and approved daily reports are counted, so nothing
pending is reconciled twice. Activity hours stay Construction records and
attendance stays HR records; this view only compares them.
"""

from collections import defaultdict
from datetime import date, timedelta

from .models import AttendanceRecord, AttendanceSheet, Leave, Overtime
from .leave import _attended, _hm, _targets

RECON_DAYS = 31
RECON_NOTE = (
    "Only approved attendance and approved Construction daily reports are counted. Activity and idle hours come from "
    "Construction labour lines and are not attendance. Unallocated is approved attendance not booked to an activity. "
    "Payable overtime is approved and attended; it is not a payment."
)


def rows(db, project, people, start, end):
    from app.domains.construction.models import ProgressLabour, ProgressReport

    worked = defaultdict(int)
    attended_ot = defaultdict(int)
    for record in (
        db.query(AttendanceRecord)
        .join(AttendanceSheet, AttendanceSheet.id == AttendanceRecord.sheet_id)
        .filter(
            AttendanceRecord.project_id == project.id,
            AttendanceSheet.status == "Approved",
            AttendanceRecord.attendance_date >= start,
            AttendanceRecord.attendance_date <= end,
        )
    ):
        key = (record.attendance_date, record.personnel_id)
        worked[key] += record.worked_minutes
        attended_ot[key] += record.overtime_minutes

    productive = defaultdict(int)
    idle = defaultdict(int)
    for entry, report in (
        db.query(ProgressLabour, ProgressReport)
        .join(ProgressReport, ProgressReport.id == ProgressLabour.report_id)
        .filter(
            ProgressReport.project_id == project.id,
            ProgressReport.status == "Approved",
            ProgressReport.report_date >= start,
            ProgressReport.report_date <= end,
        )
    ):
        key = (report.report_date, entry.personnel_id)
        productive[key] += entry.productive_minutes
        idle[key] += entry.idle_minutes

    approved_ot = defaultdict(int)
    payable_ot = defaultdict(int)
    for row in db.query(Overtime).filter(
        Overtime.project_id == project.id,
        Overtime.status == "Approved",
        Overtime.work_date >= start,
        Overtime.work_date <= end,
    ):
        approved = row.approved_minutes or 0
        for personnel_id in _targets(db, row):
            key = (row.work_date, personnel_id)
            approved_ot[key] += approved
            payable_ot[key] += min(approved, _attended(db, row, personnel_id))

    keys = set(worked) | set(productive) | set(idle) | set(approved_ot)
    on_leave = set()
    for row in db.query(Leave).filter(
        Leave.project_id == project.id, Leave.status == "Approved", Leave.start_date <= end, Leave.end_date >= start
    ):
        for key in keys:
            if key[1] == row.personnel_id and row.start_date <= key[0] <= row.end_date:
                on_leave.add(key)

    result = []
    for key in sorted(keys, key=lambda k: (k[0], people.get(k[1], "")), reverse=True):
        day, personnel_id = key
        booked = productive[key] + idle[key]
        exceptions = []
        if booked and not worked[key]:
            exceptions.append("Activity hours without approved attendance")
        elif booked > worked[key]:
            exceptions.append(f"Activity hours exceed attendance by {_hm(booked - worked[key])}")
        if attended_ot[key] > approved_ot[key]:
            exceptions.append(f"Overtime worked beyond approval by {_hm(attended_ot[key] - approved_ot[key])}")
        if key in on_leave and (worked[key] or booked):
            exceptions.append("Recorded while on approved leave")
        result.append(
            {
                "date": day.isoformat(),
                "personnel_id": personnel_id,
                "person": people.get(personnel_id, ""),
                "attendance": _hm(worked[key]),
                "activity": _hm(productive[key]),
                "idle": _hm(idle[key]),
                "unallocated": _hm(max(worked[key] - booked, 0)),
                "overtime_attended": _hm(attended_ot[key]),
                "overtime_approved": _hm(approved_ot[key]),
                "overtime_payable": _hm(payable_ot[key]),
                "exceptions": exceptions,
            }
        )
    return result


def supplement(db, user, project, payload, people):
    end = date.today()
    start = end - timedelta(days=RECON_DAYS - 1)
    lines = rows(db, project, people, start, end)
    payload["reconciliation"] = lines
    payload["reconciliation_from"] = start.isoformat()
    payload["reconciliation_note"] = RECON_NOTE
    payload["counts"]["recon_exceptions"] = sum(1 for line in lines if line["exceptions"])
    return payload
