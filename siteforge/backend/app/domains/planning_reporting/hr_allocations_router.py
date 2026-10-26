"""Independent HR crew-shift confirmation for Planning reservations.

This is a reservation confirmation against an HR-owned crew/shift reference,
not a claim about worker attendance, deployment count or work authorization.
"""
from datetime import datetime, timezone
import hashlib
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User, Membership, Role, Project
from app.domains.identity_projects.security import authenticated
from app.domains.workforce.models import Crew, Shift
from .workspace_router import access
from .workspace_models import PlanningResourceAllocation
from .allocation_rules import conflict_ids
from .hr_allocation_rules import crew_shift_eligibility

router=APIRouter(prefix='/api/projects/{pid}/planning',tags=['Planning HR Shift Reservations'])

class Reason(BaseModel):
    reason:str=Field(min_length=5,max_length=1000)

def hr_access(db,user,pid):
    access(db,user,pid,False)
    if user.organization_admin:return
    roles=db.query(Membership).filter_by(project_id=pid,user_id=user.id,active=True).all()
    permissions=set()
    for membership in roles:
        role=db.get(Role,membership.role_id)
        if role:permissions.update(role.permissions or [])
    if 'hr.manage' not in permissions:
        raise HTTPException(403,'hr.manage permission required')

@router.post('/allocations/{allocation_id}/hr-confirm')
def confirm_crew(pid:int,allocation_id:int,body:Reason,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    hr_access(db,user,pid)
    allocation=db.query(PlanningResourceAllocation).filter_by(id=allocation_id,organization_id=user.organization_id,project_id=pid).with_for_update().one_or_none()
    if not allocation:raise HTTPException(404,'Allocation not found')
    if not allocation.resource_ref.startswith('crew:') or not allocation.resource_ref[5:].isdigit():
        raise HTTPException(422,'HR confirmation requires an existing crew ID')
    crew=db.query(Crew).filter_by(id=int(allocation.resource_ref[5:]),organization_id=user.organization_id,project_id=pid).one_or_none()
    if not crew:raise HTTPException(422,'Crew reference not found')
    shift=db.query(Shift).filter_by(id=crew.shift_id,organization_id=user.organization_id,project_id=pid).one_or_none() if crew.shift_id else None
    project=db.query(Project).filter_by(id=pid,organization_id=user.organization_id).one_or_none()
    eligible,reason=crew_shift_eligibility(allocation,crew,shift,project.timezone if project else "UTC")
    if not eligible:raise HTTPException(409,reason)
    if allocation.created_by==user.id or allocation.reviewed_by==user.id:
        raise HTTPException(403,'Independent HR confirmation required')
    if db.bind and db.bind.dialect.name=='postgresql':
        key=int.from_bytes(hashlib.sha256(f'{user.organization_id}:Workforce:{allocation.resource_ref}'.encode()).digest()[:8],'big',signed=True)
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':key})
    existing=db.query(PlanningResourceAllocation).filter_by(organization_id=user.organization_id,resource_type='Workforce',resource_ref=allocation.resource_ref).all()
    if conflict_ids(allocation,[x for x in existing if x.id != allocation.id]):
        raise HTTPException(409,'Overlapping workforce allocation elsewhere in organization')
    allocation.status='HRConfirmed'
    allocation.review_note=body.reason
    db.commit()
    return {'id':allocation.id,'status':allocation.status,'basis':'HR crew-shift reference aligned; worker attendance, headcount and task eligibility not verified'}

@router.post('/allocations/{allocation_id}/hr-release')
def release_crew(pid:int,allocation_id:int,body:Reason,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    hr_access(db,user,pid)
    a=db.query(PlanningResourceAllocation).filter_by(id=allocation_id,project_id=pid,organization_id=user.organization_id,resource_type='Workforce').with_for_update().one_or_none()
    if not a:raise HTTPException(404,'Workforce allocation not found')
    if a.status!='HRConfirmed':raise HTTPException(409,'Only HR-confirmed allocation can be released')
    a.status='Released';a.review_note=body.reason
    db.commit()
    return {'id':a.id,'status':a.status}

@router.get('/allocations/{allocation_id}/workforce-capacity')
def workforce_capacity(pid:int,allocation_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    """HR-backed evidence, not a forecast of available or billable headcount."""
    hr_access(db,user,pid)
    from datetime import timedelta
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    from app.domains.workforce.models import (CrewMember, Deployment, Personnel,
        AttendanceSheet, AttendanceRecord)
    from .workforce_capacity import capacity_counts
    allocation=db.query(PlanningResourceAllocation).filter_by(
        id=allocation_id,organization_id=user.organization_id,project_id=pid,
        resource_type='Workforce').one_or_none()
    if not allocation:raise HTTPException(404,'Workforce allocation not found')
    if not allocation.resource_ref.startswith('crew:') or not allocation.resource_ref[5:].isdigit():
        raise HTTPException(422,'An HR crew reference is required')
    crew=db.query(Crew).filter_by(id=int(allocation.resource_ref[5:]),
        organization_id=user.organization_id,project_id=pid).one_or_none()
    if not crew:raise HTTPException(422,'HR crew not found')
    project=db.query(Project).filter_by(id=pid,organization_id=user.organization_id).one_or_none()
    try: zone=ZoneInfo(project.timezone or 'UTC')
    except (ZoneInfoNotFoundError,ValueError): raise HTTPException(422,'Invalid project timezone')
    local_start=allocation.starts_at.astimezone(zone).date()
    local_finish=allocation.ends_at.astimezone(zone).date()
    # Only same-day reservations have unambiguous one-day attendance evidence.
    # The overnight-shift day is attributed to the shift start date.
    if local_finish > local_start + timedelta(days=1):
        raise HTTPException(422,'Capacity evidence currently supports shifts up to one overnight period')
    members=db.query(CrewMember).filter(CrewMember.crew_id==crew.id,
        CrewMember.active.is_(True),CrewMember.start_date<=local_start,
        (CrewMember.end_date.is_(None) | (CrewMember.end_date>=local_start))).all()
    ids=list({m.personnel_id for m in members})
    deployments={d.personnel_id:d for d in db.query(Deployment).filter(
        Deployment.id.in_([m.deployment_id for m in members]),
        Deployment.organization_id==user.organization_id,Deployment.project_id==pid,
        Deployment.status=='Mobilized',Deployment.actual_start<=local_start,
        (Deployment.actual_end.is_(None)|(Deployment.actual_end>=local_start))).all()}
    people={p.id:p for p in db.query(Personnel).filter(
        Personnel.id.in_(ids),Personnel.organization_id==user.organization_id).all()}
    attendance={}
    if ids and crew.shift_id:
        rows=db.query(AttendanceRecord,AttendanceSheet).join(
            AttendanceSheet,AttendanceSheet.id==AttendanceRecord.sheet_id).filter(
            AttendanceRecord.project_id==pid,AttendanceRecord.personnel_id.in_(ids),
            AttendanceRecord.shift_id==crew.shift_id,AttendanceRecord.attendance_date==local_start,
            AttendanceSheet.organization_id==user.organization_id,
            AttendanceSheet.project_id==pid,AttendanceSheet.status=='Approved').all()
        for a,sheet in rows:attendance[a.personnel_id]=(sheet.status,a.status)
    counts=capacity_counts(members,deployments,people,attendance)
    return {'allocation_id':allocation.id,'crew_id':crew.id,'shift_id':crew.shift_id,
        'shift_start_date':local_start.isoformat(),'reservation_status':allocation.status,
        **counts,'future_capacity_confirmed':False,
        'evidence_note':'Mobilized and active crew members with approved attendance are historical evidence only; shift reservation is not an attendance guarantee.'}
