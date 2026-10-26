from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.identity_projects.models import Audit, Project, User
from app.domains.identity_projects.security import authenticated, permitted

from . import attendance, credentials, deployments, leave, monitor, offboarding, service
from .models import (
    Offboarding,
    OffboardingItem,
    Credential,
    CredentialRule,
    CredentialType,
    Leave,
    Overtime,
    AttendanceLock,
    AttendanceRecord,
    AttendanceSheet,
    Crew,
    CrewMember,
    Deployment,
    OnboardingCheck,
    Personnel,
    Shift,
    WorkforceMaster,
    WorkforceRequest,
)
from .schemas import (
    ApprovedHoursIn,
    CancelIn,
    CredentialDecision,
    CredentialIn,
    CredentialRuleIn,
    CredentialTypeIn,
    CredentialTypeUpdate,
    MonitorIn,
    OffboardingIn,
    OffboardingItemIn,
    LeaveIn,
    LeaveUpdate,
    OvertimeIn,
    AttendanceIn,
    CheckIn,
    CloseIn,
    CorrectionIn,
    CrewIn,
    CrewUpdate,
    LockIn,
    MemberEnd,
    MemberIn,
    RemoveIn,
    ReopenIn,
    SheetIn,
    ShiftIn,
    ShiftUpdate,
    DeploymentIn,
    DeploymentUpdate,
    ForecastIn,
    LineIn,
    MasterIn,
    MasterUpdate,
    MoveIn,
    PersonnelIn,
    PersonnelUpdate,
    RequestIn,
    RequestUpdate,
    VersionIn,
)

router = APIRouter(prefix="/api")


def _commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Duplicate value or invalid record reference")


def _audit(db, user, action, resource, rid, project_id, details=None):
    db.add(
        Audit(
            organization_id=user.organization_id,
            actor_id=user.id,
            action=action,
            resource=resource,
            resource_id=rid,
            details=details or {},
            project_id=project_id,
        )
    )


def _project(db, user, pid):
    project = db.get(Project, pid)
    if not project or project.organization_id != user.organization_id:
        raise HTTPException(404, "Project not found")
    return project


def _person(db, project, person_id):
    person = db.get(Personnel, person_id)
    if not person or person.organization_id != project.organization_id:
        raise HTTPException(404, "Person not found")
    return person


@router.get("/projects/{pid}/hr")
def hr_board(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.view")
    return service.board(db, u, project)


@router.post("/projects/{pid}/hr/masters", status_code=201)
def add_master(pid: int, data: MasterIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = service.add_master(db, u, data)
    _audit(db, u, "hr.master.create", "hr_master", row.id, project.id, {"kind": row.kind, "name": row.name})
    _commit(db)
    return service.present_master(row)


@router.put("/projects/{pid}/hr/masters/{mid}")
def save_master(pid: int, mid: int, data: MasterUpdate, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = db.get(WorkforceMaster, mid)
    if not row or row.organization_id != project.organization_id:
        raise HTTPException(404, "List value not found")
    row = service.save_master(db, u, row, data)
    _audit(db, u, "hr.master.update", "hr_master", row.id, project.id, {"name": row.name, "active": row.active})
    _commit(db)
    return service.present_master(row)


@router.post("/projects/{pid}/hr/personnel", status_code=201)
def add_person(pid: int, data: PersonnelIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    person = service.add_person(db, u, project, data)
    _audit(db, u, "hr.personnel.create", "hr_personnel", person.id, project.id, {"code": person.code, "status": person.status})
    _commit(db)
    return {"id": person.id, "version": person.version}


@router.put("/projects/{pid}/hr/personnel/{person_id}")
def save_person(pid: int, person_id: int, data: PersonnelUpdate, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    person = _person(db, project, person_id)
    before = person.status
    person = service.save_person(db, u, project, person, data)
    _audit(
        db,
        u,
        "hr.personnel.update",
        "hr_personnel",
        person.id,
        project.id,
        {"code": person.code, "status_from": before, "status_to": person.status},
    )
    _commit(db)
    return {"id": person.id, "version": person.version}


def _deployment(db, project, did):
    row = db.get(Deployment, did)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "Deployment not found")
    return row


def _request(db, project, rid):
    row = db.get(WorkforceRequest, rid)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "Workforce request not found")
    return row


@router.post("/projects/{pid}/hr/deployments", status_code=201)
def add_deployment(pid: int, data: DeploymentIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = deployments.add_deployment(db, u, project, data)
    _audit(db, u, "hr.deployment.create", "hr_deployment", row.id, project.id, {"personnel_id": row.personnel_id})
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.put("/projects/{pid}/hr/deployments/{did}")
def save_deployment(pid: int, did: int, data: DeploymentUpdate, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = deployments.save_deployment(db, u, project, _deployment(db, project, did), data)
    _audit(db, u, "hr.deployment.update", "hr_deployment", row.id, project.id)
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.post("/projects/{pid}/hr/deployments/{did}/checks/{cid}")
def verify_check(pid: int, did: int, cid: int, data: CheckIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.view")
    row = _deployment(db, project, did)
    check = db.get(OnboardingCheck, cid)
    if not check:
        raise HTTPException(404, "Check not found")
    check = deployments.verify_check(db, u, project, row, check, data)
    _audit(db, u, "hr.onboarding.check", "hr_onboarding_check", check.id, project.id, {"type": check.check_type, "status": check.status})
    _commit(db)
    return {"id": check.id, "status": check.status, "version": check.version}


@router.post("/projects/{pid}/hr/deployments/{did}/submit")
def submit_deployment(pid: int, did: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = _deployment(db, project, did)
    instance = deployments.submit_deployment(db, u, project, row, data.version)
    _audit(db, u, "hr.deployment.submit", "hr_deployment", row.id, project.id, {"review_id": instance.id})
    _commit(db)
    return {"id": row.id, "status": row.status, "review_id": instance.id}


@router.post("/projects/{pid}/hr/deployments/{did}/move")
def move_deployment(pid: int, did: int, data: MoveIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = _deployment(db, project, did)
    before = row.status
    row = deployments.move_deployment(db, u, project, row, data)
    _audit(db, u, "hr.deployment.move", "hr_deployment", row.id, project.id, {"from": before, "to": row.status})
    _commit(db)
    return {"id": row.id, "status": row.status, "version": row.version}


@router.post("/projects/{pid}/hr/requests", status_code=201)
def add_request(pid: int, data: RequestIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.request")
    row = deployments.add_request(db, u, project, data)
    _audit(db, u, "hr.request.create", "hr_request", row.id, project.id, {"number": row.number})
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.put("/projects/{pid}/hr/requests/{rid}")
def save_request(pid: int, rid: int, data: RequestUpdate, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.request")
    row = deployments.save_request(db, u, project, _request(db, project, rid), data)
    _audit(db, u, "hr.request.update", "hr_request", row.id, project.id)
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.post("/projects/{pid}/hr/requests/{rid}/submit")
def submit_request(pid: int, rid: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.request")
    row = _request(db, project, rid)
    instance = deployments.submit_request(db, u, project, row, data.version)
    _audit(db, u, "hr.request.submit", "hr_request", row.id, project.id, {"review_id": instance.id})
    _commit(db)
    return {"id": row.id, "status": row.status, "review_id": instance.id}


@router.post("/projects/{pid}/hr/requests/{rid}/lines")
def save_line(pid: int, rid: int, data: LineIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = deployments.save_line(db, u, project, _request(db, project, rid), data)
    _audit(db, u, "hr.request.line", "hr_request", row.id, project.id, {"personnel_id": data.personnel_id, "state": data.state})
    _commit(db)
    return {"id": row.id, "status": row.status, "version": row.version}


@router.post("/projects/{pid}/hr/requests/{rid}/forecast")
def forecast_request(pid: int, rid: int, data: ForecastIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = deployments.forecast_request(db, u, project, _request(db, project, rid), data)
    _audit(db, u, "hr.request.forecast", "hr_request", row.id, project.id)
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.post("/projects/{pid}/hr/requests/{rid}/close")
def close_request(pid: int, rid: int, data: CloseIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.view")
    row = _request(db, project, rid)
    if data.action == "close":
        permitted(db, u, project, "hr.edit")
    row = deployments.close_request(db, u, project, row, data)
    _audit(db, u, f"hr.request.{data.action}", "hr_request", row.id, project.id, {"reason": data.reason})
    _commit(db)
    return {"id": row.id, "status": row.status, "version": row.version}


def _owned(db, model, project, rid, label):
    row = db.get(model, rid)
    if not row or row.project_id != project.id:
        raise HTTPException(404, f"{label} not found")
    return row


@router.post("/projects/{pid}/hr/shifts", status_code=201)
def add_shift(pid: int, data: ShiftIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = attendance.add_shift(db, u, project, data)
    _audit(db, u, "hr.shift.create", "hr_shift", row.id, project.id, {"code": row.code})
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.put("/projects/{pid}/hr/shifts/{sid}")
def save_shift(pid: int, sid: int, data: ShiftUpdate, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = attendance.save_shift(db, u, project, _owned(db, Shift, project, sid, "Shift"), data)
    _audit(db, u, "hr.shift.update", "hr_shift", row.id, project.id, {"code": row.code, "active": row.active})
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.post("/projects/{pid}/hr/crews", status_code=201)
def add_crew(pid: int, data: CrewIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = attendance.add_crew(db, u, project, data)
    _audit(db, u, "hr.crew.create", "hr_crew", row.id, project.id, {"code": row.code})
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.put("/projects/{pid}/hr/crews/{cid}")
def save_crew(pid: int, cid: int, data: CrewUpdate, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = attendance.save_crew(db, u, project, _owned(db, Crew, project, cid, "Crew"), data)
    _audit(db, u, "hr.crew.update", "hr_crew", row.id, project.id, {"code": row.code, "active": row.active})
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.post("/projects/{pid}/hr/crews/{cid}/members", status_code=201)
def add_member(pid: int, cid: int, data: MemberIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    crew = _owned(db, Crew, project, cid, "Crew")
    member = attendance.add_member(db, u, project, crew, data)
    _audit(db, u, "hr.crew.member.add", "hr_crew", crew.id, project.id, {"personnel_id": member.personnel_id})
    _commit(db)
    return {"id": member.id, "crew_version": crew.version}


@router.post("/projects/{pid}/hr/crews/{cid}/members/{mid}/end")
def end_member(pid: int, cid: int, mid: int, data: MemberEnd, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    crew = _owned(db, Crew, project, cid, "Crew")
    member = db.get(CrewMember, mid)
    if not member:
        raise HTTPException(404, "Crew member not found")
    member = attendance.end_member(db, u, project, crew, member, data)
    _audit(db, u, "hr.crew.member.end", "hr_crew", crew.id, project.id, {"personnel_id": member.personnel_id, "end": data.end_date.isoformat()})
    _commit(db)
    return {"id": member.id, "crew_version": crew.version}


@router.post("/projects/{pid}/hr/attendance", status_code=201)
def add_sheet(pid: int, data: SheetIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.attendance")
    row = attendance.add_sheet(db, u, project, data)
    _audit(db, u, "hr.attendance.sheet.create", "hr_attendance_sheet", row.id, project.id, {"date": row.attendance_date.isoformat()})
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.post("/projects/{pid}/hr/attendance/{sid}/records")
def put_record(pid: int, sid: int, data: AttendanceIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.attendance")
    sheet = _owned(db, AttendanceSheet, project, sid, "Attendance sheet")
    record = attendance.put_record(db, u, project, sheet, data)
    _audit(db, u, "hr.attendance.record", "hr_attendance", record.id, project.id, {"personnel_id": record.personnel_id, "status": record.status})
    _commit(db)
    return {"id": record.id, "sheet_version": sheet.version}


@router.post("/projects/{pid}/hr/attendance/{sid}/remove")
def remove_record(pid: int, sid: int, data: RemoveIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.attendance")
    sheet = _owned(db, AttendanceSheet, project, sid, "Attendance sheet")
    attendance.remove_record(db, u, project, sheet, data)
    _audit(db, u, "hr.attendance.remove", "hr_attendance_sheet", sheet.id, project.id, {"personnel_id": data.personnel_id})
    _commit(db)
    return {"id": sheet.id, "version": sheet.version}


@router.post("/projects/{pid}/hr/attendance/{sid}/submit")
def submit_sheet(pid: int, sid: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.attendance")
    sheet = _owned(db, AttendanceSheet, project, sid, "Attendance sheet")
    instance = attendance.submit_sheet(db, u, project, sheet, data.version)
    _audit(db, u, "hr.attendance.submit", "hr_attendance_sheet", sheet.id, project.id, {"review_id": instance.id, "late": sheet.late})
    _commit(db)
    return {"id": sheet.id, "status": sheet.status, "review_id": instance.id}


@router.post("/projects/{pid}/hr/attendance/records/{rid}/corrections", status_code=201)
def request_correction(pid: int, rid: int, data: CorrectionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.view")
    record = _owned(db, AttendanceRecord, project, rid, "Attendance")
    row = attendance.request_correction(db, u, project, record, data)
    _audit(db, u, "hr.attendance.correction", "hr_attendance_correction", row.id, project.id, {"kind": row.kind, "attendance_id": record.id})
    _commit(db)
    return {"id": row.id, "status": row.status}


@router.post("/projects/{pid}/hr/attendance-locks", status_code=201)
def lock_period(pid: int, data: LockIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = attendance.lock_period(db, u, project, data)
    _audit(db, u, "hr.attendance.lock", "hr_attendance_lock", row.id, project.id, {"from": row.period_start.isoformat(), "to": row.period_end.isoformat()})
    _commit(db)
    return {"id": row.id}


@router.post("/projects/{pid}/hr/attendance-locks/{lid}/reopen")
def reopen_period(pid: int, lid: int, data: ReopenIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = attendance.reopen_period(db, u, project, _owned(db, AttendanceLock, project, lid, "Lock"), data)
    _audit(db, u, "hr.attendance.reopen", "hr_attendance_lock", row.id, project.id, {"reason": row.reopen_reason})
    _commit(db)
    return {"id": row.id}


@router.post("/projects/{pid}/hr/leave", status_code=201)
def add_leave(pid: int, data: LeaveIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.view")
    row = leave.add_leave(db, u, project, data)
    _audit(db, u, "hr.leave.create", "hr_leave", row.id, project.id, {"personnel_id": row.personnel_id})
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.put("/projects/{pid}/hr/leave/{lid}")
def save_leave(pid: int, lid: int, data: LeaveUpdate, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.view")
    row = leave.save_leave(db, u, project, _owned(db, Leave, project, lid, "Leave"), data)
    _audit(db, u, "hr.leave.update", "hr_leave", row.id, project.id)
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.post("/projects/{pid}/hr/leave/{lid}/submit")
def submit_leave(pid: int, lid: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.view")
    row = _owned(db, Leave, project, lid, "Leave")
    instance = leave.submit_leave(db, u, project, row, data.version)
    _audit(db, u, "hr.leave.submit", "hr_leave", row.id, project.id, {"review_id": instance.id})
    _commit(db)
    return {"id": row.id, "status": row.status, "review_id": instance.id}


@router.post("/projects/{pid}/hr/leave/{lid}/cancel")
def cancel_leave(pid: int, lid: int, data: CancelIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.view")
    row = leave.cancel_leave(db, u, project, _owned(db, Leave, project, lid, "Leave"), data)
    _audit(db, u, "hr.leave.cancel", "hr_leave", row.id, project.id)
    _commit(db)
    return {"id": row.id, "status": row.status, "version": row.version}


@router.post("/projects/{pid}/hr/overtime", status_code=201)
def add_overtime(pid: int, data: OvertimeIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.attendance")
    row = leave.add_overtime(db, u, project, data)
    _audit(db, u, "hr.overtime.create", "hr_overtime", row.id, project.id, {"minutes": row.requested_minutes})
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.post("/projects/{pid}/hr/overtime/{oid}/submit")
def submit_overtime(pid: int, oid: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.attendance")
    row = _owned(db, Overtime, project, oid, "Overtime")
    instance = leave.submit_overtime(db, u, project, row, data.version)
    _audit(db, u, "hr.overtime.submit", "hr_overtime", row.id, project.id, {"review_id": instance.id})
    _commit(db)
    return {"id": row.id, "status": row.status, "review_id": instance.id}


@router.post("/projects/{pid}/hr/overtime/{oid}/hours")
def set_overtime_hours(pid: int, oid: int, data: ApprovedHoursIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.view")
    row = leave.set_approved_minutes(db, u, project, _owned(db, Overtime, project, oid, "Overtime"), data)
    _audit(db, u, "hr.overtime.hours", "hr_overtime", row.id, project.id, {"approved_minutes": row.approved_minutes})
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.post("/projects/{pid}/hr/overtime/{oid}/cancel")
def cancel_overtime(pid: int, oid: int, data: CancelIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.view")
    row = leave.cancel_overtime(db, u, project, _owned(db, Overtime, project, oid, "Overtime"), data)
    _audit(db, u, "hr.overtime.cancel", "hr_overtime", row.id, project.id)
    _commit(db)
    return {"id": row.id, "status": row.status, "version": row.version}


def _credential(db, project, cid):
    row = db.get(Credential, cid)
    if not row or row.organization_id != project.organization_id:
        raise HTTPException(404, "Qualification not found")
    return row


@router.post("/projects/{pid}/hr/credential-types", status_code=201)
def add_credential_type(pid: int, data: CredentialTypeIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = credentials.add_type(db, u, project, data)
    _audit(db, u, "hr.credential_type.create", "hr_credential_type", row.id, project.id, {"owner": row.owner})
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.put("/projects/{pid}/hr/credential-types/{tid}")
def save_credential_type(pid: int, tid: int, data: CredentialTypeUpdate, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = db.get(CredentialType, tid)
    if not row or row.organization_id != project.organization_id:
        raise HTTPException(404, "Qualification type not found")
    credentials.save_type(db, u, project, row, data)
    _audit(db, u, "hr.credential_type.update", "hr_credential_type", row.id, project.id)
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.post("/projects/{pid}/hr/credentials", status_code=201)
def add_credential(pid: int, data: CredentialIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.view")
    row = credentials.add_credential(db, u, project, data)
    _audit(db, u, "hr.credential.create", "hr_credential", row.id, project.id, {"personnel_id": row.personnel_id, "type_id": row.type_id})
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.post("/projects/{pid}/hr/credentials/{cid}/decide")
def decide_credential(pid: int, cid: int, data: CredentialDecision, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.view")
    row = credentials.decide(db, u, project, _credential(db, project, cid), data)
    _audit(db, u, f"hr.credential.{data.action}", "hr_credential", row.id, project.id, {"reason": data.reason.strip()})
    _commit(db)
    return {"id": row.id, "status": row.status, "version": row.version}


@router.post("/projects/{pid}/hr/credentials/{cid}/withdraw")
def withdraw_credential(pid: int, cid: int, data: CancelIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.view")
    row = credentials.withdraw(db, u, project, _credential(db, project, cid), data)
    _audit(db, u, "hr.credential.withdraw", "hr_credential", row.id, project.id, {"reason": data.reason.strip()})
    _commit(db)
    return {"id": row.id, "status": row.status, "version": row.version}


@router.post("/projects/{pid}/hr/credential-rules", status_code=201)
def add_credential_rule(pid: int, data: CredentialRuleIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.view")
    row = credentials.add_rule(db, u, project, data)
    _audit(db, u, "hr.credential_rule.create", "hr_credential_rule", row.id, project.id, {"type_id": row.type_id, "scope": row.scope_key})
    _commit(db)
    return {"id": row.id}


@router.delete("/projects/{pid}/hr/credential-rules/{rid}")
def remove_credential_rule(pid: int, rid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.view")
    row = db.get(CredentialRule, rid)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "Requirement not found")
    details = {"type_id": row.type_id, "scope": row.scope_key}
    credentials.remove_rule(db, u, project, row)
    _audit(db, u, "hr.credential_rule.delete", "hr_credential_rule", rid, project.id, details)
    _commit(db)
    return {"id": rid}


def _offboarding(db, project, oid):
    row = db.get(Offboarding, oid)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "Offboarding not found")
    return row


@router.post("/projects/{pid}/hr/offboardings", status_code=201)
def add_offboarding(pid: int, data: OffboardingIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = offboarding.add_offboarding(db, u, project, data)
    _audit(db, u, "hr.offboarding.create", "hr_offboarding", row.id, project.id, {"deployment_id": row.deployment_id, "last_working_date": row.last_working_date.isoformat()})
    _commit(db)
    return {"id": row.id, "version": row.version}


@router.post("/projects/{pid}/hr/offboardings/{oid}/items/{iid}")
def save_offboarding_item(pid: int, oid: int, iid: int, data: OffboardingItemIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = _offboarding(db, project, oid)
    item = db.get(OffboardingItem, iid)
    if not item:
        raise HTTPException(404, "Checklist item not found")
    offboarding.save_item(db, u, project, row, item, data)
    _audit(db, u, "hr.offboarding.item", "hr_offboarding", row.id, project.id, {"item": item.item, "status": item.status})
    _commit(db)
    return {"id": item.id, "status": item.status, "version": item.version}


@router.post("/projects/{pid}/hr/offboardings/{oid}/submit")
def submit_offboarding(pid: int, oid: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = _offboarding(db, project, oid)
    instance = offboarding.submit_offboarding(db, u, project, row, data.version)
    _audit(db, u, "hr.offboarding.submit", "hr_offboarding", row.id, project.id, {"review_id": instance.id})
    _commit(db)
    return {"id": row.id, "status": row.status, "review_id": instance.id}


@router.post("/projects/{pid}/hr/offboardings/{oid}/cancel")
def cancel_offboarding(pid: int, oid: int, data: CancelIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = offboarding.cancel_offboarding(db, u, project, _offboarding(db, project, oid), data)
    _audit(db, u, "hr.offboarding.cancel", "hr_offboarding", row.id, project.id, {"reason": data.reason.strip()})
    _commit(db)
    return {"id": row.id, "status": row.status, "version": row.version}


@router.put("/projects/{pid}/hr/monitor")
def save_monitor(pid: int, data: MonitorIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "hr.edit")
    row = monitor.save_settings(db, u, project, data)
    _audit(db, u, "hr.monitor.save", "hr_monitor_setting", row.id, project.id, {"enabled": row.enabled, "escalate_after_days": row.escalate_after_days})
    _commit(db)
    return {"id": row.id, "version": row.version}
