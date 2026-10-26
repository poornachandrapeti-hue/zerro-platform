"""Planning resource allocation proposals, not HR or Equipment authorization.

Confirmed shift availability and resource-constrained CPM remain out of scope.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from .workspace_router import access
from .workspace_models import PlanningSchedule,PlanningActivity,PlanningResourceAllocation
from .allocation_rules import conflict_ids
from app.domains.workforce.models import Crew, Personnel

router=APIRouter(prefix='/api/projects/{pid}/planning',tags=['Planning Resource Allocations'])

class AllocationInput(BaseModel):
    schedule_id:int
    activity_id:int
    resource_type:str
    resource_ref:str=Field(min_length=1,max_length=120)
    company_id:int|None=None
    starts_at:datetime
    ends_at:datetime
    notes:str=Field(default='',max_length=2000)
    @model_validator(mode='after')
    def check(self):
        if self.resource_type not in ('Workforce','Equipment'):
            raise ValueError('Unsupported resource type')
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError('Timezone-aware shift dates required')
        if self.starts_at>=self.ends_at:
            raise ValueError('End must be later than start')
        if self.ends_at-self.starts_at > __import__('datetime').timedelta(days=31):
            raise ValueError('Split reservations longer than 31 days')
        return self

def serialize(row):
    return {key:getattr(row,key) for key in ('id','schedule_id','activity_id','resource_type','resource_ref','company_id','starts_at','ends_at','status','notes','created_at','reviewed_by','reviewed_at','review_note')}

def check_refs(db,user,pid,sid,aid):
    schedule=db.query(PlanningSchedule).filter_by(id=sid,project_id=pid,organization_id=user.organization_id).one_or_none()
    activity=db.query(PlanningActivity).filter_by(id=aid,schedule_id=sid,project_id=pid,organization_id=user.organization_id).one_or_none()
    if not schedule or not activity:raise HTTPException(404,'Schedule or activity not found')
    if activity.activity_type=='Summary':raise HTTPException(422,'Cannot allocate to summary activity')
    return activity

@router.get('/allocations')
def list_allocations(pid:int,schedule_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)  # Restricted to internal planning managers
    if db.query(PlanningSchedule).filter_by(id=schedule_id,project_id=pid,organization_id=user.organization_id).first() is None:
        raise HTTPException(404,'Schedule not found')
    rows=db.query(PlanningResourceAllocation).filter_by(organization_id=user.organization_id,project_id=pid,schedule_id=schedule_id).order_by(PlanningResourceAllocation.starts_at).all()
    return {'items':[serialize(r) for r in rows], 'basis':'Planning reservations only; workforce assignment and equipment availability have not been independently verified'}

@router.post('/allocations',status_code=201)
def create_allocation(pid:int,body:AllocationInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    check_refs(db,user,pid,body.schedule_id,body.activity_id)
    # Accept source-linked HR IDs only when they exist and belong to this project.
    # Raw external refs remain proposals and cannot establish verified supply.
    if body.resource_type=='Workforce' and body.resource_ref.startswith(('crew:', 'personnel:')):
        kind, _, raw_id = body.resource_ref.partition(':')
        if not raw_id.isdigit():raise HTTPException(422,'Invalid workforce source ID')
        model=Crew if kind=='crew' else Personnel
        source=db.query(model).filter_by(id=int(raw_id),organization_id=user.organization_id).one_or_none()
        if not source or (kind=='crew' and (source.project_id!=pid or not source.active)) or (kind=='personnel' and source.status!='Active'):
            raise HTTPException(422,'Workforce reference not found or inactive for project')
    if body.resource_type=='Equipment' and body.resource_ref.startswith('equipment:'):
        from .workspace_models import PlanningEquipmentAsset
        try: asset_id=int(body.resource_ref.split(':',1)[1])
        except ValueError: raise HTTPException(422,'Invalid equipment identity reference')
        if not db.query(PlanningEquipmentAsset).filter_by(id=asset_id,organization_id=user.organization_id).first():
            raise HTTPException(422,'Registered equipment not found')
    row=PlanningResourceAllocation(organization_id=user.organization_id,project_id=pid,created_by=user.id,status='Proposed',**body.model_dump())
    # Lock relevant resource key at DB level for PostgreSQL to serialize concurrent requests.
    # A transaction-scoped advisory lock avoids a check-then-insert race.
    from sqlalchemy import text
    if db.bind and db.bind.dialect.name=='postgresql':
        import hashlib
        token=f'{user.organization_id}:{body.resource_type}:{body.resource_ref}'.encode()
        lock_key=int.from_bytes(hashlib.sha256(token).digest()[:8],'big',signed=True)
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':lock_key})
    existing=db.query(PlanningResourceAllocation).filter_by(organization_id=user.organization_id,resource_type=body.resource_type,resource_ref=body.resource_ref).all()
    matches=conflict_ids(row,existing)
    if matches:raise HTTPException(409,{'message':'Resource already proposed in overlapping time window across organization projects','conflicting_count':len(matches)})
    db.add(row);db.commit();db.refresh(row)
    return serialize(row)

@router.post('/allocations/{allocation_id}/cancel')
def cancel_allocation(pid:int,allocation_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    row=db.query(PlanningResourceAllocation).filter_by(id=allocation_id,organization_id=user.organization_id,project_id=pid).one_or_none()
    if row is None:raise HTTPException(404,'Allocation not found')
    if row.status=='Cancelled':return serialize(row)
    if row.status in ('EquipmentConfirmed','HRConfirmed'):raise HTTPException(409,'Use owning resource release workflow for confirmed booking')
    row.status='Cancelled';db.commit();return serialize(row)

class AllocationReview(BaseModel):
    decision:str
    note:str=Field(min_length=5,max_length=2000)

@router.post('/allocations/{allocation_id}/review')
def review_allocation(pid:int,allocation_id:int,body:AllocationReview,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    """Internal Planning review, NOT HR/Equipment availability confirmation."""
    access(db,user,pid,True)
    if body.decision not in ('Reviewed','Returned'):
        raise HTTPException(422,'Decision must be Reviewed or Returned')
    row=db.query(PlanningResourceAllocation).filter_by(id=allocation_id,organization_id=user.organization_id,project_id=pid).one_or_none()
    if row is None:raise HTTPException(404,'Allocation not found')
    if row.status!='Proposed':raise HTTPException(409,'Only proposed allocations may be reviewed')
    if row.created_by==user.id:raise HTTPException(403,'Independent review required')
    row.status=body.decision
    row.review_note=body.note
    row.reviewed_by=user.id
    row.reviewed_at=datetime.now(timezone.utc)
    db.commit();db.refresh(row)
    return serialize(row)
