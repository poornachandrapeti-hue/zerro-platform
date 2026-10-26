from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.identity_projects.models import Discipline, User
from app.domains.identity_projects.security import authenticated, permitted
from app.domains.workforce import attendance, deployments
from app.domains.workforce.models import Crew, CrewMember, WorkforceRequest
from app.domains.workforce.router import _audit, _commit, _owned, _project
from app.domains.workforce.schemas import (
    CloseIn,
    CrewIn,
    CrewUpdate,
    ForecastIn,
    LineIn,
    MemberEnd,
    MemberIn,
    RequestIn,
    RequestUpdate,
    VersionIn,
)
from app.domains.workforce.service import masters, project_companies

from . import allocation, availability, productivity, returns, service, utilization
from .models import Assignment, DailyReturn
from .schemas import AssignmentIn, AssignmentRelease, ReturnBack, ReturnSubmit

router = APIRouter(prefix="/api")


def _demand(db, project, rid):
    row = db.get(WorkforceRequest, rid)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "Demand not found")
    return row


@router.get("/projects/{pid}/manpower")
def manpower_board(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.view")
    return service.board(db, u, project)


@router.post("/projects/{pid}/manpower/demands", status_code=201)
def add_demand(pid: int, data: RequestIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.demand")
    row = deployments.add_request(db, u, project, data)
    _audit(db, u, "manpower.demand.create", "hr_request", row.id, project.id, {"number": row.number})
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.put("/projects/{pid}/manpower/demands/{rid}")
def save_demand(pid: int, rid: int, data: RequestUpdate, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.demand")
    row = deployments.save_request(db, u, project, _demand(db, project, rid), data)
    _audit(db, u, "manpower.demand.update", "hr_request", row.id, project.id)
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.post("/projects/{pid}/manpower/demands/{rid}/submit")
def submit_demand(pid: int, rid: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.demand")
    row = _demand(db, project, rid)
    instance = deployments.submit_request(db, u, project, row, data.version)
    _audit(db, u, "manpower.demand.submit", "hr_request", row.id, project.id, {"review_id": instance.id})
    _commit(db)
    return {"id": row.id, "status": row.status, "review_id": instance.id}


@router.post("/projects/{pid}/manpower/demands/{rid}/lines")
def save_demand_line(pid: int, rid: int, data: LineIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.coordinate")
    row = deployments.save_line(db, u, project, _demand(db, project, rid), data)
    _audit(db, u, "manpower.demand.line", "hr_request", row.id, project.id, {"personnel_id": data.personnel_id, "state": data.state})
    _commit(db)
    return {"id": row.id, "status": row.status, "version": row.version}


@router.post("/projects/{pid}/manpower/demands/{rid}/forecast")
def forecast_demand(pid: int, rid: int, data: ForecastIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.coordinate")
    row = service.save_forecast(db, u, project, _demand(db, project, rid), data)
    _audit(db, u, "manpower.demand.forecast", "hr_request", row.id, project.id)
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.post("/projects/{pid}/manpower/demands/{rid}/close")
def close_demand(pid: int, rid: int, data: CloseIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.view")
    row = _demand(db, project, rid)
    if data.action == "close":
        permitted(db, u, project, "manpower.coordinate")
    row = deployments.close_request(db, u, project, row, data)
    _audit(db, u, f"manpower.demand.{data.action}", "hr_request", row.id, project.id, {"reason": data.reason})
    _commit(db)
    return {"id": row.id, "status": row.status, "version": row.version}


@router.get("/projects/{pid}/manpower/availability")
def manpower_availability(
    pid: int,
    start: date | None = None,
    days: int = Query(14, ge=7, le=28),
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.view")
    return availability.availability(db, project, _names(db, project), start or date.today(), days)


def _names(db, project):
    return {
        "company": {row.id: row.name for row in project_companies(db, project)},
        "master": {row.id: row.name for row in masters(db, project.organization_id)},
        "discipline": {row.id: row.name for row in db.query(Discipline)},
    }


def _assignment(db, project, aid):
    row = db.get(Assignment, aid)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "Assignment not found")
    return row


@router.get("/projects/{pid}/manpower/allocations")
def manpower_allocations(
    pid: int,
    start: date | None = None,
    days: int = Query(7, ge=1, le=28),
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.view")
    return allocation.board(db, project, _names(db, project), start or date.today(), days)


@router.post("/projects/{pid}/manpower/assignments", status_code=201)
def add_assignment(pid: int, data: AssignmentIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.allocate")
    created, skipped = allocation.create(db, u, project, data)
    for row in created:
        _audit(
            db, u, "manpower.assignment.propose", "mp_assignment", row.id, project.id,
            {"personnel_id": row.personnel_id, "activity_id": row.activity_id, "work_date": row.work_date.isoformat()},
        )
    _commit(db)
    return {"created": [row.id for row in created], "skipped": skipped}


@router.post("/projects/{pid}/manpower/assignments/{aid}/confirm")
def confirm_assignment(pid: int, aid: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.allocate")
    row = allocation.confirm(db, u, project, _assignment(db, project, aid), data.version)
    _audit(db, u, "manpower.assignment.confirm", "mp_assignment", row.id, project.id)
    _commit(db)
    return {"id": row.id, "state": row.state, "version": row.version}


@router.post("/projects/{pid}/manpower/assignments/{aid}/release")
def release_assignment(pid: int, aid: int, data: AssignmentRelease, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.allocate")
    row = allocation.release(db, u, project, _assignment(db, project, aid), data)
    _audit(db, u, "manpower.assignment.release", "mp_assignment", row.id, project.id, {"reason": data.reason})
    _commit(db)
    return {"id": row.id, "state": row.state, "version": row.version}


@router.post("/projects/{pid}/manpower/crews", status_code=201)
def add_crew(pid: int, data: CrewIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.coordinate")
    row = attendance.add_crew(db, u, project, data)
    _audit(db, u, "manpower.crew.create", "hr_crew", row.id, project.id, {"code": row.code})
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.put("/projects/{pid}/manpower/crews/{cid}")
def save_crew(pid: int, cid: int, data: CrewUpdate, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.coordinate")
    row = attendance.save_crew(db, u, project, _owned(db, Crew, project, cid, "Crew"), data)
    _audit(db, u, "manpower.crew.update", "hr_crew", row.id, project.id, {"code": row.code, "active": row.active})
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.post("/projects/{pid}/manpower/crews/{cid}/members", status_code=201)
def add_member(pid: int, cid: int, data: MemberIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.coordinate")
    crew = _owned(db, Crew, project, cid, "Crew")
    member = attendance.add_member(db, u, project, crew, data)
    _audit(db, u, "manpower.crew.member.add", "hr_crew", crew.id, project.id, {"personnel_id": member.personnel_id})
    _commit(db)
    return {"id": member.id, "crew_version": crew.version}


@router.post("/projects/{pid}/manpower/crews/{cid}/members/{mid}/end")
def end_member(pid: int, cid: int, mid: int, data: MemberEnd, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.coordinate")
    crew = _owned(db, Crew, project, cid, "Crew")
    member = db.get(CrewMember, mid)
    if not member:
        raise HTTPException(404, "Crew member not found")
    member = attendance.end_member(db, u, project, crew, member, data)
    _audit(
        db, u, "manpower.crew.member.end", "hr_crew", crew.id, project.id,
        {"personnel_id": member.personnel_id, "end": data.end_date.isoformat()},
    )
    _commit(db)
    return {"id": member.id, "crew_version": crew.version}


@router.get("/projects/{pid}/manpower/utilization")
def manpower_utilization(
    pid: int,
    start: date | None = None,
    days: int = Query(7, ge=7, le=28),
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.view")
    return utilization.utilization(db, project, _names(db, project), start or date.today(), days)


@router.get("/projects/{pid}/manpower/alerts")
def manpower_alerts(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.view")
    return utilization.alerts(db, project, _names(db, project))


@router.get("/projects/{pid}/manpower/productivity")
def manpower_productivity(
    pid: int,
    start: date | None = None,
    end: date | None = None,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.view")
    last = end or date.today()
    return productivity.productivity(db, project, start or last - timedelta(days=6), last)


@router.get("/projects/{pid}/manpower/summary")
def manpower_summary(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.view")
    return productivity.summary(db, project, _names(db, project))


@router.get("/projects/{pid}/manpower/returns")
def manpower_return(pid: int, work_date: date, shift_id: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.view")
    return returns.view(db, u, project, _names(db, project), work_date, shift_id)


@router.post("/projects/{pid}/manpower/returns", status_code=201)
def submit_return(pid: int, data: ReturnSubmit, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.returns")
    row = returns.submit(db, u, project, data)
    _audit(
        db, u, "manpower.return.submit", "mp_daily_return", row.id, project.id,
        {"work_date": row.work_date.isoformat(), "shift_id": row.shift_id},
    )
    _commit(db)
    return {"id": row.id, "state": row.state, "version": row.version}


@router.post("/projects/{pid}/manpower/returns/{rid}/accept")
def accept_return(pid: int, rid: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.coordinate")
    row = returns.accept(db, u, project, _owned(db, DailyReturn, project, rid, "Daily return"), data.version)
    _audit(db, u, "manpower.return.accept", "mp_daily_return", row.id, project.id)
    _commit(db)
    return {"id": row.id, "state": row.state, "version": row.version}


@router.post("/projects/{pid}/manpower/returns/{rid}/return")
def send_back_return(pid: int, rid: int, data: ReturnBack, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.coordinate")
    row = returns.send_back(db, u, project, _owned(db, DailyReturn, project, rid, "Daily return"), data)
    _audit(db, u, "manpower.return.send_back", "mp_daily_return", row.id, project.id, {"reason": data.reason})
    _commit(db)
    return {"id": row.id, "state": row.state, "version": row.version}
