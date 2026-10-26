"""Planned allocation of people and crews to activities.

An assignment is planned work, not attendance. It is proposed against an HR
deployment and confirmed only when the person is mobilized, not on approved
leave, holds the qualifications the activity needs, works for the executing
company, and is not booked on an overlapping shift. Qualification problems name
the requirement and its state; medical or private details are never returned.
"""

from datetime import datetime, timedelta

from fastapi import HTTPException

from app.domains.workforce.attendance import _hm, _shift, _shift_minutes
from app.domains.workforce.credentials import eligibility
from app.domains.workforce.deployments import REQUEST_ALLOCATING, _bump
from app.domains.workforce.leave import approved_leave
from app.domains.workforce.models import Crew, CrewMember, Deployment, Personnel, Shift, WorkforceRequest, now

from .availability import HELD, _covers, _window
from .models import Assignment

LIVE = ("Proposed", "Confirmed")
ALLOCATION_NOTE = (
    "An assignment is planned work, not attendance or hours worked. Proposing needs an approved or mobilized "
    "HR deployment; confirming needs the person mobilized on that date. Leave, qualifications, the executing "
    "company, and overlapping shifts are checked each time, and problems that appear later are shown on the "
    "assignment. Several activities may share one shift up to its scheduled hours."
)


def _activity(db, project, activity_id):
    from app.domains.construction.models import ConstructionActivity

    row = db.get(ConstructionActivity, activity_id)
    if not row or row.project_id != project.id or not row.active:
        raise HTTPException(422, "Choose an active activity on this project")
    return row


def _span(shift, day):
    start = datetime.combine(day, shift.start_time)
    return start, start + timedelta(minutes=_shift_minutes(shift))


def _capacity(shift):
    return _shift_minutes(shift) - shift.break_minutes


def check(db, project, person, activity, shift, day, minutes, *, confirm, exclude_id=None):
    """Every reason this person cannot take this work, and the deployment it would use."""
    problems = []
    if person.status != "Active":
        problems.append("not an active worker")
    if person.company_id != activity.company_id:
        problems.append("not employed by the company executing this activity")
    covering = [
        row
        for row in db.query(Deployment).filter(
            Deployment.project_id == project.id, Deployment.personnel_id == person.id, Deployment.status.in_(HELD)
        )
        if _covers(*_window(row), day)
    ]
    deployment = next((row for row in covering if row.status == "Mobilized"), covering[0] if covering else None)
    if not covering:
        problems.append(f"no approved HR deployment on {day.isoformat()}")
    elif any(row.status == "Temporarily Unavailable" for row in covering):
        problems.append("temporarily unavailable in HR")
    elif confirm and deployment.status != "Mobilized":
        problems.append("approved for mobilization but not yet mobilized")
    if approved_leave(db, project, person.id, day):
        problems.append("on approved leave")
    result = eligibility(db, project, person, day, activity.package_id, activity.id)
    if result["status"] != "Eligible":
        missing = ", ".join(f"{item['type']} {item['status'].lower()}" for item in result["items"] if item["status"] != "Eligible")
        problems.append(f"qualification: {missing}")

    others = db.query(Assignment).filter(
        Assignment.project_id == project.id,
        Assignment.personnel_id == person.id,
        Assignment.state.in_(LIVE),
        Assignment.work_date.between(day - timedelta(days=1), day + timedelta(days=1)),
    )
    if exclude_id is not None:
        others = others.filter(Assignment.id != exclude_id)
    start, end = _span(shift, day)
    booked = minutes
    for other in others:
        other_shift = db.get(Shift, other.shift_id)
        if other.shift_id == shift.id and other.work_date == day:
            if other.activity_id == activity.id:
                problems.append("already assigned to this activity on this shift")
            booked += other.planned_minutes
            continue
        other_start, other_end = _span(other_shift, other.work_date)
        if other_start < end and start < other_end:
            problems.append(f"already assigned on shift {other_shift.code} {other.work_date.isoformat()}, which overlaps")
    if booked > _capacity(shift):
        problems.append(f"would be booked {_hm(booked)} on shift {shift.code}, more than its {_hm(_capacity(shift))} scheduled")
    return problems, deployment


def _demand(db, project, demand_id, activity):
    if demand_id is None:
        return None
    row = db.get(WorkforceRequest, demand_id)
    if not row or row.project_id != project.id:
        raise HTTPException(422, "Choose a demand on this project")
    if row.status not in REQUEST_ALLOCATING:
        raise HTTPException(422, "Only an approved, open demand can take assignments")
    if row.activity_id and row.activity_id != activity.id:
        raise HTTPException(422, f"Demand {row.number} is for another activity")
    return row


def _crew_people(db, crew, day):
    members = db.query(CrewMember).filter(CrewMember.crew_id == crew.id, CrewMember.active.is_(True))
    return [member.personnel_id for member in members if _covers(member.start_date, member.end_date, day)]


def create(db, user, project, data):
    if (data.personnel_id is None) == (data.crew_id is None):
        raise HTTPException(422, "Choose one person or one crew")
    activity = _activity(db, project, data.activity_id)
    shift = _shift(db, project, data.shift_id, on=data.work_date)
    demand = _demand(db, project, data.demand_id, activity)
    crew = None
    if data.crew_id is not None:
        crew = db.get(Crew, data.crew_id)
        if not crew or crew.project_id != project.id or not crew.active:
            raise HTTPException(422, "Choose an active crew on this project")
        if not _covers(crew.effective_from, crew.effective_to, data.work_date):
            raise HTTPException(422, f"Crew {crew.code} is not in effect on {data.work_date.isoformat()}")
        if crew.shift_id and crew.shift_id != shift.id:
            raise HTTPException(422, f"Crew {crew.code} works another shift")
        ids = _crew_people(db, crew, data.work_date)
        if not ids:
            raise HTTPException(422, f"Crew {crew.code} has no members on {data.work_date.isoformat()}")
    else:
        ids = [data.personnel_id]
    # Row locks serialize concurrent bookings of the same people on PostgreSQL.
    people = (
        db.query(Personnel)
        .filter(Personnel.id.in_(ids), Personnel.organization_id == project.organization_id)
        .order_by(Personnel.id)
        .with_for_update()
        .all()
    )
    if len(people) != len(ids):
        raise HTTPException(422, "Choose a person on this project")
    created, skipped = [], []
    for person in people:
        problems, deployment = check(db, project, person, activity, shift, data.work_date, data.planned_minutes, confirm=False)
        if demand and person.trade_id != demand.trade_id:
            problems.append(f"trade does not match demand {demand.number}")
        if problems:
            skipped.append({"personnel_id": person.id, "person": f"{person.code} · {person.full_name}", "problems": problems})
            continue
        row = Assignment(
            organization_id=project.organization_id,
            project_id=project.id,
            activity_id=activity.id,
            work_date=data.work_date,
            shift_id=shift.id,
            personnel_id=person.id,
            deployment_id=deployment.id,
            crew_id=crew.id if crew else None,
            demand_id=demand.id if demand else None,
            planned_minutes=data.planned_minutes,
            note=data.note.strip(),
            created_by=user.id,
        )
        db.add(row)
        db.flush()
        created.append(row)
    if not created:
        detail = "; ".join(f"{item['person']}: {', '.join(item['problems'])}" for item in skipped)
        raise HTTPException(422, f"Nobody could be assigned. {detail}")
    return created, skipped


def confirm(db, user, project, row, version):
    if row.state != "Proposed":
        raise HTTPException(409, "Only a proposed assignment can be confirmed")
    person = db.query(Personnel).filter(Personnel.id == row.personnel_id).with_for_update().one()
    activity = _activity(db, project, row.activity_id)
    shift = _shift(db, project, row.shift_id, on=row.work_date)
    problems, deployment = check(
        db, project, person, activity, shift, row.work_date, row.planned_minutes, confirm=True, exclude_id=row.id
    )
    if problems:
        raise HTTPException(422, f"{person.code} cannot be confirmed: {', '.join(problems)}")
    _bump(
        db,
        Assignment,
        row,
        version,
        {"state": "Confirmed", "deployment_id": deployment.id, "confirmed_by": user.id, "confirmed_at": now(), "modified_at": now()},
    )
    return row


def release(db, user, project, row, data):
    if row.state not in LIVE:
        raise HTTPException(409, "This assignment is already released")
    _bump(
        db,
        Assignment,
        row,
        data.version,
        {"state": "Released", "release_reason": data.reason.strip(), "released_by": user.id, "released_at": now(), "modified_at": now()},
    )
    return row


def release_after(db, user, deployment, last_day, reason):
    """Release live assignments on this deployment after the last working day."""
    for row in db.query(Assignment).filter(
        Assignment.deployment_id == deployment.id, Assignment.state.in_(LIVE), Assignment.work_date > last_day
    ):
        row.state = "Released"
        row.release_reason = reason
        row.released_by = user.id
        row.released_at = now()
        row.version += 1
        row.modified_at = now()


def board(db, project, names, first, days):
    from app.domains.construction.models import ConstructionActivity

    last = first + timedelta(days=days - 1)
    rows = (
        db.query(Assignment)
        .filter(Assignment.project_id == project.id, Assignment.work_date.between(first, last))
        .order_by(Assignment.work_date, Assignment.shift_id, Assignment.activity_id, Assignment.id)
        .all()
    )
    people = {row.id: row for row in db.query(Personnel).filter(Personnel.id.in_({r.personnel_id for r in rows} or {-1}))}
    activities = {row.id: row for row in db.query(ConstructionActivity).filter_by(project_id=project.id)}
    shifts = {row.id: row for row in db.query(Shift).filter_by(project_id=project.id)}
    crews = {row.id: row.code for row in db.query(Crew).filter_by(project_id=project.id)}
    demands = {row.id: row.number for row in db.query(WorkforceRequest).filter_by(project_id=project.id)}
    out = []
    for row in rows:
        person, activity, shift = people[row.personnel_id], activities[row.activity_id], shifts[row.shift_id]
        problems = []
        if row.state in LIVE:
            problems, _ = check(
                db, project, person, activity, shift, row.work_date, row.planned_minutes, confirm=True, exclude_id=row.id
            )
        out.append(
            {
                "id": row.id,
                "work_date": row.work_date.isoformat(),
                "shift_id": row.shift_id,
                "shift": shift.code,
                "activity_id": row.activity_id,
                "activity": f"{activity.code} · {activity.name}",
                "personnel_id": row.personnel_id,
                "person": f"{person.code} · {person.full_name}",
                "trade": names["master"].get(person.trade_id, ""),
                "crew": crews.get(row.crew_id, "") if row.crew_id else "",
                "demand": demands.get(row.demand_id, "") if row.demand_id else "",
                "planned": _hm(row.planned_minutes),
                "planned_minutes": row.planned_minutes,
                "note": row.note,
                "state": row.state,
                "release_reason": row.release_reason,
                "problems": problems,
                "version": row.version,
            }
        )
    live = [item for item in out if item["state"] in LIVE]
    return {
        "note": ALLOCATION_NOTE,
        "start": first.isoformat(),
        "dates": [(first + timedelta(days=n)).isoformat() for n in range(days)],
        "assignments": out,
        "counts": {
            "proposed": sum(1 for item in live if item["state"] == "Proposed"),
            "confirmed": sum(1 for item in live if item["state"] == "Confirmed"),
            "flagged": sum(1 for item in live if item["problems"]),
            "planned_hours": round(sum(item["planned_minutes"] for item in live if item["state"] == "Confirmed") / 60, 1),
        },
    }


def demand_hours(db, project):
    """Confirmed planned hours per demand."""
    totals = {}
    for row in db.query(Assignment).filter(
        Assignment.project_id == project.id, Assignment.state == "Confirmed", Assignment.demand_id.isnot(None)
    ):
        totals[row.demand_id] = totals.get(row.demand_id, 0) + row.planned_minutes
    return {key: round(value / 60, 1) for key, value in totals.items()}
