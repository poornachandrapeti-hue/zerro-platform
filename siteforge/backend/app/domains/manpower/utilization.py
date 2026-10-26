"""Utilization, shortfalls, and alerts read from Manpower, HR, and daily returns.

Nothing here is stored. Available time comes from HR availability, planned
time from confirmed assignments, and attended time from approved HR attendance.
Alerts are worked out on each read; they are not notifications and they never
change a record.
"""

from datetime import date, timedelta

from app.domains.identity_projects.models import User
from app.domains.workforce.attendance import _hm
from app.domains.workforce.deployments import REQUEST_ALLOCATING
from app.domains.workforce.models import (
    AttendanceRecord,
    AttendanceSheet,
    Crew,
    CrewMember,
    Personnel,
    Shift,
    WorkforceRequest,
)

from .allocation import _capacity, check
from .availability import Calendar, _covers
from .models import Assignment, DailyReturn

UTILIZATION_NOTE = (
    "Available time counts each day a person is available in HR at the scheduled hours of their crew's shift, "
    "or of the project's earliest active shift when the crew has none. Allocation is confirmed planned time "
    "against all available time shown; utilization is approved attendance against available time up to today. "
    "Nothing here is stored."
)
ALERT_NOTE = (
    "Alerts are worked out from current records each time this screen opens. They are shown here only; no "
    "notification is sent and no record is changed."
)
LOW_UTILIZATION = 50
SOON_DAYS = 3
RETURN_LOOKBACK = 7


def _pct(part, whole):
    return round(part * 100 / whole) if whole else None


def _shifts(db, project):
    return {row.id: row for row in db.query(Shift).filter(Shift.project_id == project.id)}


def _default_shift(shifts, day):
    live = [
        row for row in shifts.values()
        if row.active and row.effective_from <= day and (row.effective_to is None or day <= row.effective_to)
    ]
    return min(live, key=lambda row: (row.start_time, row.id)) if live else None


def _crew_shifts(db, project):
    out = {}
    for member, crew in (
        db.query(CrewMember, Crew)
        .join(Crew, Crew.id == CrewMember.crew_id)
        .filter(Crew.project_id == project.id, CrewMember.active.is_(True), Crew.shift_id.isnot(None))
    ):
        out.setdefault(member.personnel_id, []).append((member.start_date, member.end_date, crew.shift_id))
    return out


def _attended(db, project, first, last):
    """Approved attendance minutes by person and date."""
    totals = {}
    rows = (
        db.query(AttendanceRecord)
        .join(AttendanceSheet, AttendanceSheet.id == AttendanceRecord.sheet_id)
        .filter(
            AttendanceRecord.project_id == project.id,
            AttendanceRecord.attendance_date.between(first, last),
            AttendanceSheet.status == "Approved",
        )
    )
    for row in rows:
        key = (row.personnel_id, row.attendance_date)
        totals[key] = totals.get(key, 0) + row.worked_minutes
    return totals


def _planned(db, project, first, last):
    """Confirmed planned minutes by person and date."""
    totals = {}
    for row in db.query(Assignment).filter(
        Assignment.project_id == project.id,
        Assignment.state == "Confirmed",
        Assignment.work_date.between(first, last),
    ):
        key = (row.personnel_id, row.work_date)
        totals[key] = totals.get(key, 0) + row.planned_minutes
    return totals


def _measure(db, project, first, last, today):
    """Per person: available, available to date, planned, and attended minutes over the range."""
    dates = [first + timedelta(days=n) for n in range((last - first).days + 1)]
    calendar = Calendar(db, project, first, last)
    shifts = _shifts(db, project)
    crew_shifts = _crew_shifts(db, project)
    planned = _planned(db, project, first, last)
    attended = _attended(db, project, first, last)
    out = {}
    for pid in calendar.deployments:
        row = {"available_days": 0, "available": 0, "available_to_date": 0, "planned": 0, "attended": 0}
        for day in dates:
            row["planned"] += planned.get((pid, day), 0)
            row["attended"] += attended.get((pid, day), 0)
            if calendar.status(pid, day) != "Available":
                continue
            shift_id = next((sid for start, end, sid in crew_shifts.get(pid, []) if _covers(start, end, day)), None)
            shift = shifts.get(shift_id) if shift_id else _default_shift(shifts, day)
            minutes = _capacity(shift) if shift else 0
            row["available_days"] += 1
            row["available"] += minutes
            if day <= today:
                row["available_to_date"] += minutes
        if row["available_days"] or row["planned"] or row["attended"]:
            out[pid] = row
    return out


def utilization(db, project, names, first, days):
    today = date.today()
    last = first + timedelta(days=days - 1)
    measured = _measure(db, project, first, last, today)
    people = {row.id: row for row in db.query(Personnel).filter(Personnel.id.in_(list(measured) or [-1]))}
    rows, trades = [], {}
    for pid, m in measured.items():
        person = people[pid]
        rows.append(
            {
                "id": pid,
                "person": f"{person.code} · {person.full_name}",
                "trade_id": person.trade_id,
                "trade": names["master"].get(person.trade_id, ""),
                "available_days": m["available_days"],
                "available": _hm(m["available"]),
                "planned": _hm(m["planned"]),
                "attended": _hm(m["attended"]),
                "allocation_pct": _pct(m["planned"], m["available"]),
                "utilization_pct": _pct(m["attended"], m["available_to_date"]),
            }
        )
        total = trades.setdefault(
            person.trade_id, {"people": 0, "available": 0, "available_to_date": 0, "planned": 0, "attended": 0}
        )
        total["people"] += 1
        for key in ("available", "available_to_date", "planned", "attended"):
            total[key] += m[key]
    rows.sort(key=lambda row: (row["trade"].casefold(), row["person"]))
    trade_rows = sorted(
        (
            {
                "trade_id": trade_id,
                "trade": names["master"].get(trade_id, ""),
                "people": t["people"],
                "available_hours": round(t["available"] / 60, 1),
                "planned_hours": round(t["planned"] / 60, 1),
                "attended_hours": round(t["attended"] / 60, 1),
                "allocation_pct": _pct(t["planned"], t["available"]),
                "utilization_pct": _pct(t["attended"], t["available_to_date"]),
            }
            for trade_id, t in trades.items()
        ),
        key=lambda row: row["trade"].casefold(),
    )
    return {
        "note": UTILIZATION_NOTE,
        "start": first.isoformat(),
        "dates": [(first + timedelta(days=n)).isoformat() for n in range(days)],
        "trades": trade_rows,
        "people": rows,
        "shortfalls": shortfalls(db, project, names, first, last),
    }


def shortfalls(db, project, names, first, last):
    """Approved headcount of each open demand against people confirmed on it, for each date in range."""
    demands = (
        db.query(WorkforceRequest)
        .filter(WorkforceRequest.project_id == project.id, WorkforceRequest.status.in_(REQUEST_ALLOCATING))
        .order_by(WorkforceRequest.start_date, WorkforceRequest.id)
        .all()
    )
    confirmed = {}
    for row in db.query(Assignment).filter(
        Assignment.project_id == project.id,
        Assignment.state == "Confirmed",
        Assignment.demand_id.in_([d.id for d in demands] or [-1]),
        Assignment.work_date.between(first, last),
    ):
        confirmed.setdefault((row.demand_id, row.work_date), set()).add(row.personnel_id)
    out = []
    for demand in demands:
        days = []
        day = max(first, demand.start_date)
        end = min(last, demand.end_date) if demand.end_date else last
        while day <= end:
            assigned = len(confirmed.get((demand.id, day), ()))
            days.append({"date": day.isoformat(), "needed": demand.headcount, "assigned": assigned, "gap": max(0, demand.headcount - assigned)})
            day += timedelta(days=1)
        short = [item for item in days if item["gap"]]
        if not short:
            continue
        out.append(
            {
                "id": demand.id,
                "number": demand.number,
                "trade": names["master"].get(demand.trade_id, ""),
                "priority": demand.priority,
                "headcount": demand.headcount,
                "first_short": short[0]["date"],
                "worst_gap": max(item["gap"] for item in short),
                "short_days": len(short),
                "days": days,
            }
        )
    return out


def _alert(kind, severity, owner, since, today, detail, tab):
    return {
        "kind": kind,
        "severity": severity,
        "owner": owner,
        "since": since.isoformat(),
        "age_days": max(0, (today - since).days),
        "detail": detail,
        "tab": tab,
    }


def alerts(db, project, names):
    from app.domains.construction.models import ConstructionActivity

    today = date.today()
    out = []

    # Demand still short within the next few days.
    for row in shortfalls(db, project, names, today, today + timedelta(days=SOON_DAYS)):
        start = date.fromisoformat(row["first_short"])
        out.append(
            _alert(
                "Demand short", "High" if row["priority"] in ("High", "Urgent") or start <= today else "Medium",
                "Manpower Coordinator", min(today, start - timedelta(days=SOON_DAYS)), today,
                f"{row['number']} · {row['trade']}: short on {row['short_days']} day(s) from {row['first_short']}, "
                f"up to {row['worst_gap']} of {row['headcount']} not confirmed",
                "Workforce demand",
            )
        )

    # Confirmed work that no longer passes its checks.
    shifts = _shifts(db, project)
    activities = {row.id: row for row in db.query(ConstructionActivity).filter_by(project_id=project.id)}
    upcoming = (
        db.query(Assignment)
        .filter(
            Assignment.project_id == project.id,
            Assignment.state == "Confirmed",
            Assignment.work_date.between(today, today + timedelta(days=14)),
        )
        .order_by(Assignment.work_date, Assignment.id)
        .all()
    )
    people = {row.id: row for row in db.query(Personnel).filter(Personnel.id.in_({a.personnel_id for a in upcoming} or {-1}))}
    for row in upcoming:
        person, activity, shift = people[row.personnel_id], activities.get(row.activity_id), shifts[row.shift_id]
        if activity is None:
            continue
        problems, _ = check(
            db, project, person, activity, shift, row.work_date, row.planned_minutes, confirm=True, exclude_id=row.id
        )
        if problems:
            since = row.confirmed_at.date() if row.confirmed_at else today
            out.append(
                _alert(
                    "Assignment needs attention", "High" if row.work_date <= today + timedelta(days=1) else "Medium",
                    "Allocating supervisor", min(since, today), today,
                    f"{person.code} on {activity.code} {row.work_date.isoformat()} shift {shift.code}: {', '.join(problems)}",
                    "Allocation",
                )
            )

    # Shifts with confirmed work but no daily return a day later.
    first = today - timedelta(days=RETURN_LOOKBACK)
    worked = {
        (row.work_date, row.shift_id)
        for row in db.query(Assignment).filter(
            Assignment.project_id == project.id,
            Assignment.state == "Confirmed",
            Assignment.work_date.between(first, today - timedelta(days=1)),
        )
    }
    filed = {
        (row.work_date, row.shift_id): row
        for row in db.query(DailyReturn).filter(DailyReturn.project_id == project.id, DailyReturn.work_date >= first)
    }
    for day, shift_id in sorted(worked):
        if (day, shift_id) not in filed:
            out.append(
                _alert(
                    "Daily return missing", "Medium", "Supervisor", day + timedelta(days=1), today,
                    f"{day.isoformat()} shift {shifts[shift_id].code} has confirmed work and no daily return",
                    "Daily returns",
                )
            )

    # Returns sent back and not resubmitted.
    for row in db.query(DailyReturn).filter(DailyReturn.project_id == project.id, DailyReturn.state == "Returned"):
        submitter = db.get(User, row.submitted_by)
        out.append(
            _alert(
                "Daily return sent back", "Medium", submitter.name if submitter else "Submitter",
                min(row.modified_at.date(), today), today,
                f"{row.work_date.isoformat()} shift {shifts[row.shift_id].code}: {row.return_reason}",
                "Daily returns",
            )
        )

    # People mostly idle over the last week.
    week_start = today - timedelta(days=7)
    measured = _measure(db, project, week_start, today - timedelta(days=1), today)
    low = {pid: m for pid, m in measured.items() if m["available_days"] >= 3 and m["available_to_date"]}
    names_by_id = {row.id: row for row in db.query(Personnel).filter(Personnel.id.in_(list(low) or [-1]))}
    for pid, m in low.items():
        pct = _pct(m["attended"], m["available_to_date"])
        if pct < LOW_UTILIZATION:
            person = names_by_id[pid]
            out.append(
                _alert(
                    "Low utilization", "Low", "Manpower Coordinator", week_start, today,
                    f"{person.code} · {person.full_name}: {pct}% of available time attended over the last 7 days",
                    "Utilization",
                )
            )

    rank = {"High": 0, "Medium": 1, "Low": 2}
    out.sort(key=lambda item: (rank[item["severity"]], -item["age_days"], item["kind"]))
    counts = {}
    for item in out:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    return {"note": ALERT_NOTE, "today": today.isoformat(), "alerts": out, "counts": counts}
