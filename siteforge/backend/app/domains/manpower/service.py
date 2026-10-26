"""Manpower: workforce demand, crews, and HR references.

Manpower owns workforce demand and crew structure. A demand is the same record
HR stored as a workforce request, and a crew is the same crew HR attendance and
overtime use, so numbers and history stay the same and nothing is duplicated. HR stays the source for personnel, deployment, attendance, and leave;
Manpower reads them and never stores restricted HR details.
"""

from datetime import date

from app.domains.identity_projects.models import Area, Discipline, Membership, ProjectDiscipline, Role, User
from app.domains.identity_projects.security import holds
from app.domains.workforce.attendance import CREW_NOTE, crew_view
from app.domains.workforce.deployments import REQUEST_ALLOCATING, forecast_request, request_view
from app.domains.workforce.models import PRIORITIES, Crew, Deployment, Personnel, Shift, WorkforceRequest
from app.domains.workforce.service import masters, project_companies

NOTE = (
    "Manpower coordinates demand and references HR records. HR stays the source for personnel, "
    "deployment, attendance, and leave. Contact, identity, pay, and medical details are not shown here."
)
DEMAND_NOTE = (
    "Requested, approved, proposed, confirmed, and shortfall are separate. Approval does not mean people "
    "are available or mobilized, and proposed people do not reduce the shortfall. A person is confirmed "
    "only through an HR deployment that is approved for mobilization or mobilized."
)
REFERENCE_NOTE = (
    "Counts are distinct people today. Engaged is employment, not deployment. Deployed is a mobilized "
    "HR deployment, not attendance or eligibility for an activity."
)
APPROVED = {*REQUEST_ALLOCATING, "Closed"}
LIVE_DEPLOYMENT = ("Proposed", "Pending Approval", "Approved for Mobilization", "Mobilized", "Temporarily Unavailable")


def tracking(row):
    counts = row["counts"]
    approved = row["headcount"] if row["status"] in APPROVED else 0
    return {
        "requested": row["headcount"],
        "approved": approved,
        "proposed": counts["proposed"],
        "confirmed": counts["allocated"],
        "shortfall": max(0, approved - counts["allocated"]) if approved else None,
    }


def _current_deployment(rows, today):
    live = [row for row in rows if row.status in LIVE_DEPLOYMENT]
    if not live:
        return None
    covering = [row for row in live if row.planned_start <= today and (row.planned_end is None or row.planned_end >= today)]
    return sorted(covering or live, key=lambda row: (row.planned_start, row.id))[-1]


def references(db, project, names, today):
    people = (
        db.query(Personnel)
        .filter(Personnel.company_id.in_(list(names["company"]) or [-1]))
        .order_by(Personnel.full_name, Personnel.id)
        .all()
    )
    by_person = {}
    for row in db.query(Deployment).filter_by(project_id=project.id):
        by_person.setdefault(row.personnel_id, []).append(row)
    out = []
    for person in people:
        current = _current_deployment(by_person.get(person.id, []), today)
        out.append(
            {
                "id": person.id,
                "code": person.code,
                "full_name": person.full_name,
                "company_id": person.company_id,
                "company_name": names["company"].get(person.company_id, ""),
                "trade_id": person.trade_id,
                "trade": names["master"].get(person.trade_id, ""),
                "grade": names["master"].get(person.grade_id, "") if person.grade_id else "",
                "discipline": names["discipline"].get(person.discipline_id, "") if person.discipline_id else "",
                "status": person.status,
                "deployment_status": current.status if current else "",
                "deployment_from": current.planned_start.isoformat() if current else None,
                "deployment_to": current.planned_end.isoformat() if current and current.planned_end else None,
            }
        )
    return out


def notify_forecast(db, user, project, row, before):
    """A changed mobilization forecast goes to the requester and Planning on the project."""
    if row.expected_mobilization == before:
        return
    from app.domains.coordination.jobs import notify

    recipients = {row.requested_by}
    planning = db.query(Role).filter_by(name="Planning").first()
    if planning:
        recipients |= {
            member.user_id
            for member in db.query(Membership).filter_by(project_id=project.id, role_id=planning.id, active=True)
        }
    recipients.discard(user.id)
    when = row.expected_mobilization.isoformat() if row.expected_mobilization else "not set"
    for uid in recipients:
        target = db.get(User, uid)
        if target and target.active:
            notify(
                db,
                target,
                "Mobilization forecast changed",
                f"Demand {row.number}: expected mobilization is now {when}.",
                f"manpower:demand:{row.id}:forecast:{when}",
                project_id=project.id,
                link=f"/projects/{project.id}",
            )


def save_forecast(db, user, project, row, data):
    before = row.expected_mobilization
    forecast_request(db, user, project, row, data)
    notify_forecast(db, user, project, row, before)
    return row


def crews(db, project, names):
    from .availability import Calendar

    today = date.today()
    calendar = Calendar(db, project, today, today)
    people = {
        row.id: f"{row.code} · {row.full_name}"
        for row in db.query(Personnel).filter(Personnel.organization_id == project.organization_id)
    }
    out = []
    for row in db.query(Crew).filter_by(project_id=project.id).order_by(Crew.code):
        view = crew_view(db, row, names, people)
        for member in view["members"]:
            member["today"] = calendar.status(member["personnel_id"], today) if member["active"] else ""
        current = [m for m in view["members"] if m["active"] and date.fromisoformat(m["start_date"]) <= today]
        view["strength"] = {
            "members": len(current),
            "available": sum(1 for m in current if m["today"] == "Available"),
            "away": sum(1 for m in current if m["today"] in ("On leave", "Unavailable")),
        }
        out.append(view)
    return out


def board(db, user, project):
    from app.domains.construction.models import ConstructionActivity, WorkPackage

    from .availability import Calendar

    today = date.today()
    companies = project_companies(db, project)
    master_rows = masters(db, project.organization_id)
    disciplines = db.query(Discipline).order_by(Discipline.name).all()
    names = {
        "company": {row.id: row.name for row in companies},
        "master": {row.id: row.name for row in master_rows},
        "discipline": {row.id: row.name for row in disciplines},
    }
    refs = references(db, project, names, today)
    calendar = Calendar(db, project, today, today)
    for ref in refs:
        ref["today"] = calendar.status(ref["id"], today)
    crew_rows = crews(db, project, names)
    shift_rows = db.query(Shift).filter_by(project_id=project.id).order_by(Shift.code).all()
    from .allocation import demand_hours

    hours = demand_hours(db, project)
    demands = []
    for row in db.query(WorkforceRequest).filter_by(project_id=project.id).order_by(WorkforceRequest.id.desc()):
        view = request_view(db, user, project, row, names)
        view["tracking"] = tracking(view)
        view["planned_hours"] = hours.get(row.id, 0)
        demands.append(view)
    enabled = {row.discipline_id for row in db.query(ProjectDiscipline).filter_by(project_id=project.id, active=True)}
    members, seen = [], set()
    for member in db.query(Membership).filter_by(project_id=project.id, active=True):
        person = db.get(User, member.user_id)
        if person and person.active and person.id not in seen:
            seen.add(person.id)
            members.append({"id": person.id, "name": person.name})
    open_demands = [row for row in demands if row["status"] in REQUEST_ALLOCATING]
    deployments = (
        db.query(Deployment)
        .filter(Deployment.project_id == project.id, Deployment.status.in_(("Approved for Mobilization", "Mobilized")))
        .order_by(Deployment.planned_start)
        .all()
    )
    return {
        "note": NOTE,
        "demand_note": DEMAND_NOTE,
        "reference_note": REFERENCE_NOTE,
        "today": today.isoformat(),
        "references": refs,
        "demands": demands,
        "companies": [{"id": row.id, "name": row.name} for row in companies],
        "project_disciplines": [{"id": row.id, "name": row.name} for row in disciplines if row.id in enabled],
        "areas": [
            {"id": row.id, "name": f"{row.code} · {row.name}"}
            for row in db.query(Area).filter_by(project_id=project.id).order_by(Area.code)
        ],
        "packages": [
            {"id": row.id, "name": row.code}
            for row in db.query(WorkPackage).filter_by(project_id=project.id).order_by(WorkPackage.code)
        ],
        "activities": [
            {"id": row.id, "name": row.code, "title": row.name, "package_id": row.package_id, "company_id": row.company_id}
            for row in db.query(ConstructionActivity).filter_by(project_id=project.id, active=True).order_by(ConstructionActivity.code)
        ],
        "trades": [{"id": row.id, "name": row.name} for row in master_rows if row.kind == "Trade" and row.active],
        "grades": [{"id": row.id, "name": row.name} for row in master_rows if row.kind == "Skill grade" and row.active],
        "shifts": [row.name for row in shift_rows if row.active],
        "shift_options": [
            {"id": row.id, "name": f"{row.code} · {row.start_time.strftime('%H:%M')}–{row.end_time.strftime('%H:%M')}", "active": row.active}
            for row in shift_rows
        ],
        "crews": crew_rows,
        "crew_note": CREW_NOTE,
        "priorities": list(PRIORITIES),
        "members": members,
        "deployments": [
            {
                "id": row.id,
                "personnel_id": row.personnel_id,
                "status": row.status,
                "planned_start": row.planned_start.isoformat(),
                "planned_end": row.planned_end.isoformat() if row.planned_end else None,
            }
            for row in deployments
        ],
        "can_demand": holds(db, user, project, "manpower.demand"),
        "can_coordinate": holds(db, user, project, "manpower.coordinate"),
        "can_allocate": holds(db, user, project, "manpower.allocate"),
        "counts": {
            "engaged": sum(1 for row in refs if row["status"] == "Active"),
            "deployed": sum(1 for row in refs if row["deployment_status"] == "Mobilized"),
            "approved_mobilization": sum(1 for row in refs if row["deployment_status"] == "Approved for Mobilization"),
            "unavailable": sum(1 for row in refs if row["deployment_status"] == "Temporarily Unavailable"),
            "available_today": sum(1 for row in refs if row["today"] == "Available"),
            "on_leave_today": sum(1 for row in refs if row["today"] == "On leave"),
            "active_crews": sum(1 for row in crew_rows if row["active"]),
            "crew_away": sum(row["strength"]["away"] for row in crew_rows if row["active"]),
            "demands_pending": sum(1 for row in demands if row["status"] == "Pending Review"),
            "demands_open": len(open_demands),
            "requested": sum(row["tracking"]["requested"] for row in open_demands),
            "approved": sum(row["tracking"]["approved"] for row in open_demands),
            "proposed": sum(row["tracking"]["proposed"] for row in open_demands),
            "confirmed": sum(row["tracking"]["confirmed"] for row in open_demands),
            "shortfall": sum(row["tracking"]["shortfall"] or 0 for row in open_demands),
        },
    }
