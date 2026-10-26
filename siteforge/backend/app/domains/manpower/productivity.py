"""Labour productivity and the Manpower management summary.

Read from approved Construction daily reports, HR availability, Manpower
assignments, and daily returns. Nothing is stored. Quantities of different
units are never added together, and no cost or money figure is shown.
"""

from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException

from .models import DailyReturn
from .utilization import _measure, _pct, alerts, shortfalls

PRODUCTIVITY_NOTE = (
    "From approved Construction daily reports only. Quantity counts approved lines with reversals deducted and "
    "rework excluded. Labour hours include rework time, shown separately. Output per man-hour divides the "
    "quantity by all productive hours on the activity. Different units are never added, and weighted-milestone "
    "activities show hours only."
)
MAX_DAYS = 92


def _hours(minutes):
    return round(minutes / 60, 1)


def productivity(db, project, first, last):
    from app.domains.construction.models import ConstructionActivity, ProgressLabour, ProgressLine, ProgressReport

    if last < first:
        raise HTTPException(422, "The end date must be on or after the start date")
    if (last - first).days + 1 > MAX_DAYS:
        raise HTTPException(422, f"Choose a period of {MAX_DAYS} days or fewer")
    activities = {row.id: row for row in db.query(ConstructionActivity).filter_by(project_id=project.id)}
    lines = (
        db.query(ProgressLine)
        .join(ProgressReport, ProgressReport.id == ProgressLine.report_id)
        .filter(
            ProgressReport.project_id == project.id,
            ProgressReport.status == "Approved",
            ProgressReport.report_date.between(first, last),
        )
        .all()
    )
    stats = {}

    def slot(activity_id):
        return stats.setdefault(
            activity_id,
            {"quantity": Decimal("0"), "productive": 0, "idle": 0, "rework": 0, "people": set(), "reports": set(), "reasons": Counter()},
        )

    by_line = {}
    for line in lines:
        row = slot(line.activity_id)
        row["reports"].add(line.report_id)
        by_line[line.id] = line
        if line.quantity and not line.rework:
            row["quantity"] += -line.quantity if line.reverses_line_id else line.quantity
    for labour in db.query(ProgressLabour).filter(ProgressLabour.line_id.in_(list(by_line) or [-1])):
        line = by_line[labour.line_id]
        row = slot(line.activity_id)
        row["productive"] += labour.productive_minutes
        row["idle"] += labour.idle_minutes
        row["people"].add(labour.personnel_id)
        if line.rework:
            row["rework"] += labour.productive_minutes + labour.idle_minutes
        if labour.idle_minutes:
            row["reasons"][labour.idle_reason.strip() or "No reason given"] += labour.idle_minutes

    out = []
    for activity_id, row in stats.items():
        activity = activities.get(activity_id)
        if activity is None:
            continue
        weighted = activity.measurement_method == "Weighted milestones"
        hours = row["productive"] / 60
        rate = None if weighted or not hours else row["quantity"] / Decimal(str(hours))
        out.append(
            {
                "activity_id": activity_id,
                "code": activity.code,
                "name": activity.name,
                "unit": "" if weighted else activity.unit,
                "method": activity.measurement_method,
                "quantity": None if weighted else f"{row['quantity'].normalize():f}",
                "productive_hours": _hours(row["productive"]),
                "idle_hours": _hours(row["idle"]),
                "rework_hours": _hours(row["rework"]),
                "idle_pct": _pct(row["idle"], row["productive"] + row["idle"]),
                "rate": None if rate is None else f"{rate:.2f}",
                "people": len(row["people"]),
                "reports": len(row["reports"]),
                "idle_reasons": [
                    {"reason": reason, "hours": _hours(minutes)} for reason, minutes in row["reasons"].most_common(3)
                ],
            }
        )
    out.sort(key=lambda item: item["code"].casefold())
    productive = sum(item["productive_hours"] for item in out)
    idle = sum(item["idle_hours"] for item in out)
    return {
        "note": PRODUCTIVITY_NOTE,
        "start": first.isoformat(),
        "end": last.isoformat(),
        "activities": out,
        "totals": {
            "productive_hours": round(productive, 1),
            "idle_hours": round(idle, 1),
            "rework_hours": round(sum(item["rework_hours"] for item in out), 1),
            "idle_pct": _pct(idle, productive + idle),
            "people": len({pid for row in stats.values() for pid in row["people"]}),
        },
    }


def summary(db, project, names):
    """Headline numbers for the Manpower dashboard over the last seven days, ending today."""
    today = date.today()
    week = today - timedelta(days=6)
    measured = _measure(db, project, week, today, today)
    available = sum(m["available"] for m in measured.values())
    to_date = sum(m["available_to_date"] for m in measured.values())
    planned = sum(m["planned"] for m in measured.values())
    attended = sum(m["attended"] for m in measured.values())
    open_alerts = alerts(db, project, names)["alerts"]
    severity = {"High": 0, "Medium": 0, "Low": 0}
    for item in open_alerts:
        severity[item["severity"]] += 1
    work = productivity(db, project, week, today)
    returns = db.query(DailyReturn).filter(DailyReturn.project_id == project.id)
    return {
        "week_start": week.isoformat(),
        "today": today.isoformat(),
        "allocation_pct": _pct(planned, available),
        "utilization_pct": _pct(attended, to_date),
        "planned_hours": _hours(planned),
        "attended_hours": _hours(attended),
        "short_today": sum(row["days"][0]["gap"] for row in shortfalls(db, project, names, today, today)),
        "alerts": severity,
        "alert_total": len(open_alerts),
        "returns_pending": returns.filter(DailyReturn.state == "Submitted").count(),
        "returns_sent_back": returns.filter(DailyReturn.state == "Returned").count(),
        "productive_hours": work["totals"]["productive_hours"],
        "idle_hours": work["totals"]["idle_hours"],
        "idle_pct": work["totals"]["idle_pct"],
        "top_idle": sorted(
            (item for item in work["activities"] if item["idle_hours"]), key=lambda item: -item["idle_hours"]
        )[:3],
        "top_output": sorted(work["activities"], key=lambda item: -item["productive_hours"])[:5],
    }
