"""Availability read from HR, and demand compared against it.

Nothing here is stored. A day's status comes from the HR deployment and
approved leave on that date. Approved for mobilization is expected, not
available, and leave reasons are never returned.
"""

from datetime import timedelta

from app.domains.workforce.models import Crew, CrewMember, Deployment, Leave, Personnel, WorkforceRequest

from .service import APPROVED

AVAILABILITY_NOTE = (
    "Read from HR for each date. Available is a mobilized deployment that is not on approved leave. "
    "Expected is approved for mobilization but not yet mobilized. Temporarily unavailable uses today's HR "
    "status for every date shown. Needed is the approved headcount of open demands covering the date. "
    "This is not eligibility for an activity."
)
HELD = ("Approved for Mobilization", "Mobilized", "Temporarily Unavailable")
STATUSES = ("Available", "Expected", "On leave", "Unavailable", "Not deployed")


def _window(row):
    if row.status == "Approved for Mobilization":
        return row.planned_start, row.planned_end
    return row.actual_start or row.planned_start, row.actual_end or row.planned_end


def _covers(start, end, day):
    return start <= day and (end is None or day <= end)


class Calendar:
    """HR deployments, approved leave, and crew memberships for one project and date range."""

    def __init__(self, db, project, first, last):
        self.deployments = {}
        for row in db.query(Deployment).filter(Deployment.project_id == project.id, Deployment.status.in_(HELD)):
            self.deployments.setdefault(row.personnel_id, []).append(row)
        self.leaves = {}
        for row in db.query(Leave).filter(
            Leave.project_id == project.id, Leave.status == "Approved", Leave.start_date <= last, Leave.end_date >= first
        ):
            self.leaves.setdefault(row.personnel_id, []).append((row.start_date, row.end_date))
        self.crews = {}
        for member, crew in (
            db.query(CrewMember, Crew)
            .join(Crew, Crew.id == CrewMember.crew_id)
            .filter(Crew.project_id == project.id, CrewMember.active.is_(True))
        ):
            self.crews.setdefault(member.personnel_id, []).append((member.start_date, member.end_date, crew.code))

    def status(self, personnel_id, day):
        live = [row for row in self.deployments.get(personnel_id, []) if _covers(*_window(row), day)]
        if not live:
            return "Not deployed"
        if any(row.status == "Temporarily Unavailable" for row in live):
            return "Unavailable"
        if any(_covers(start, end, day) for start, end in self.leaves.get(personnel_id, [])):
            return "On leave"
        if any(row.status == "Mobilized" for row in live):
            return "Available"
        return "Expected"

    def crew(self, personnel_id, day):
        return next((code for start, end, code in self.crews.get(personnel_id, []) if _covers(start, end, day)), "")


def availability(db, project, names, first, days):
    last = first + timedelta(days=days - 1)
    dates = [first + timedelta(days=n) for n in range(days)]
    calendar = Calendar(db, project, first, last)
    people = (
        db.query(Personnel)
        .filter(Personnel.id.in_(list(calendar.deployments) or [-1]))
        .order_by(Personnel.full_name, Personnel.id)
        .all()
    )
    rows, by_trade = [], {}
    for person in people:
        cells = [{"status": calendar.status(person.id, day), "crew": calendar.crew(person.id, day)} for day in dates]
        if all(cell["status"] == "Not deployed" for cell in cells):
            continue
        rows.append(
            {
                "id": person.id,
                "code": person.code,
                "full_name": person.full_name,
                "company_name": names["company"].get(person.company_id, ""),
                "trade_id": person.trade_id,
                "trade": names["master"].get(person.trade_id, ""),
                "days": cells,
            }
        )
        trade = by_trade.setdefault(person.trade_id, [{"available": 0, "expected": 0, "away": 0, "needed": 0} for _ in dates])
        for slot, cell in zip(trade, cells):
            if cell["status"] == "Available":
                slot["available"] += 1
            elif cell["status"] == "Expected":
                slot["expected"] += 1
            elif cell["status"] in ("On leave", "Unavailable"):
                slot["away"] += 1
    demands = db.query(WorkforceRequest).filter(
        WorkforceRequest.project_id == project.id, WorkforceRequest.status.in_(tuple(APPROVED - {"Closed"}))
    )
    for demand in demands:
        trade = by_trade.setdefault(demand.trade_id, [{"available": 0, "expected": 0, "away": 0, "needed": 0} for _ in dates])
        for slot, day in zip(trade, dates):
            if _covers(demand.start_date, demand.end_date, day):
                slot["needed"] += demand.headcount
    trades = []
    for trade_id, slots in by_trade.items():
        for slot in slots:
            slot["gap"] = max(0, slot["needed"] - slot["available"])
        trades.append({"trade_id": trade_id, "trade": names["master"].get(trade_id, ""), "days": slots})
    trades.sort(key=lambda row: row["trade"].casefold())
    return {
        "note": AVAILABILITY_NOTE,
        "start": first.isoformat(),
        "dates": [day.isoformat() for day in dates],
        "statuses": list(STATUSES),
        "people": rows,
        "trades": trades,
    }
