"""Planning demand and recovery proposals. No automatic resource leveling or baseline replacement."""
from datetime import date
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,model_validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from .workspace_router import access,owned
from .workspace_models import PlanningSchedule,PlanningActivity,PlanningResourceDemand,PlanningRecoveryScenario,PlanningRecoveryReview,PlanningRecoveryEvent

router=APIRouter(prefix='/api/projects/{pid}/planning',tags=['Planning Resources and Recovery'])

def asdict(row,fields):return {x:getattr(row,x) for x in fields}
RESOURCE_FIELDS=['id','schedule_id','activity_id','period_start','period_end','resource_type','resource_name','company_id','demand_quantity','demand_unit','confirmed_capacity','capacity_source','notes','created_at']
SCENARIO_FIELDS=['id','schedule_id','code','title','reason','proposed_changes','schedule_impact_days','resource_impact','cost_impact_reference','required_reviews','status','created_by','created_at']
class DemandBody(BaseModel):
    schedule_id:int
    activity_id:int
    period_start:date
    period_end:date
    resource_type:str
    resource_name:str=Field(min_length=1,max_length=160)
    company_id:int|None=None
    demand_quantity:int=Field(ge=0)
    demand_unit:str
    confirmed_capacity:int|None=Field(default=None,ge=0)
    capacity_source:str|None=Field(default=None,max_length=200)
    notes:str=Field(default='',max_length=3000)
    @model_validator(mode='after')
    def valid(self):
        if self.period_end<self.period_start:raise ValueError('Period finish precedes start')
        if self.resource_type not in ('Workforce','Equipment'):raise ValueError('Invalid resource type')
        if self.demand_unit not in ('headcount','person-hours','units','equipment-hours'):raise ValueError('Unsupported unit')
        if self.resource_type=='Workforce' and self.demand_unit not in ('headcount','person-hours'):raise ValueError('Invalid workforce unit')
        if self.resource_type=='Equipment' and self.demand_unit not in ('units','equipment-hours'):raise ValueError('Invalid equipment unit')
        if self.confirmed_capacity is not None and not (self.capacity_source or '').strip():raise ValueError('Confirmed capacity requires a traceable source')
        return self
class ScenarioBody(BaseModel):
    schedule_id:int
    code:str=Field(min_length=1,max_length=80)
    title:str=Field(min_length=1,max_length=200)
    reason:str=Field(min_length=1,max_length=3000)
    proposed_changes:str=Field(min_length=1,max_length=5000)
    schedule_impact_days:int|None=None
    resource_impact:str=Field(default='',max_length=3000)
    cost_impact_reference:str|None=Field(default=None,max_length=200)
    required_reviews:list[str]=Field(default_factory=list,max_length=20)
    @model_validator(mode='after')
    def valid(self):
        allowed={'Engineering','Construction','QA','HSE','Contracts','Financials','Project Manager'}
        if not set(self.required_reviews).issubset(allowed):raise ValueError('Invalid review department')
        return self

def scoped(db,user,pid,sid,aid=None):
    sched=owned(db,PlanningSchedule,sid,pid)
    if sched.organization_id!=user.organization_id:raise HTTPException(404,'Schedule not found')
    if aid is not None:
        act=owned(db,PlanningActivity,aid,pid)
        if act.organization_id!=user.organization_id or act.schedule_id!=sid:raise HTTPException(422,'Activity must belong to schedule')
    return sched

@router.get('/resource-demands')
def list_demands(pid:int,schedule_id:int|None=None,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid)
    q=db.query(PlanningResourceDemand).filter_by(project_id=pid,organization_id=user.organization_id)
    if schedule_id is not None:
        scoped(db,user,pid,schedule_id)
        q=q.filter_by(schedule_id=schedule_id)
    result=[]
    for row in q.order_by(PlanningResourceDemand.period_start,PlanningResourceDemand.id).all():
        data=asdict(row,RESOURCE_FIELDS)
        data['shortfall']=max(0,row.demand_quantity-row.confirmed_capacity) if row.confirmed_capacity is not None else None
        data['capacity_status']='Confirmed source supplied' if row.confirmed_capacity is not None else 'Unavailable'
        result.append(data)
    return result

@router.post('/resource-demands',status_code=201)
def add_demand(pid:int,body:DemandBody,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True);scoped(db,user,pid,body.schedule_id,body.activity_id)
    row=PlanningResourceDemand(organization_id=user.organization_id,project_id=pid,created_by=user.id,**body.model_dump())
    db.add(row);db.commit();db.refresh(row)
    return asdict(row,RESOURCE_FIELDS)

@router.get('/recovery-scenarios')
def list_scenarios(pid:int,schedule_id:int|None=None,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid)
    q=db.query(PlanningRecoveryScenario).filter_by(project_id=pid,organization_id=user.organization_id)
    if schedule_id is not None:
        scoped(db,user,pid,schedule_id);q=q.filter_by(schedule_id=schedule_id)
    return [asdict(row,SCENARIO_FIELDS) for row in q.order_by(PlanningRecoveryScenario.id.desc()).all()]

@router.post('/recovery-scenarios',status_code=201)
def add_scenario(pid:int,body:ScenarioBody,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True);scoped(db,user,pid,body.schedule_id)
    row=PlanningRecoveryScenario(organization_id=user.organization_id,project_id=pid,created_by=user.id,**body.model_dump())
    db.add(row)
    try:db.commit();db.refresh(row)
    except IntegrityError:db.rollback();raise HTTPException(409,'Recovery code already exists')
    return asdict(row,SCENARIO_FIELDS)


class RecoveryDecision(BaseModel):
    action:str
    department:str|None=None
    comment:str=Field(default='',max_length=3000)
    @model_validator(mode='after')
    def validate_action(self):
        if self.action not in ('submit','review_approve','review_reject','approve','return'):
            raise ValueError('Unsupported recovery action')
        if self.action in ('review_approve','review_reject') and not self.department:
            raise ValueError('Department is required')
        if self.action in ('review_reject','return') and not self.comment.strip():
            raise ValueError('Reason is required')
        return self

def _scenario(db,user,pid,scenario_id):
    row=db.query(PlanningRecoveryScenario).filter_by(id=scenario_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if row is None:raise HTTPException(404,'Scenario not found')
    return row

@router.get('/recovery-scenarios/{scenario_id}/history')
def scenario_history(pid:int,scenario_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid)
    _scenario(db,user,pid,scenario_id)
    reviews=db.query(PlanningRecoveryReview).filter_by(project_id=pid,organization_id=user.organization_id,scenario_id=scenario_id).order_by(PlanningRecoveryReview.id).all()
    events=db.query(PlanningRecoveryEvent).filter_by(project_id=pid,organization_id=user.organization_id,scenario_id=scenario_id).order_by(PlanningRecoveryEvent.id).all()
    return {'reviews':[asdict(r,['id','department','decision','comment','actor_id','created_at']) for r in reviews],
            'events':[asdict(e,['id','previous_status','next_status','action','comment','actor_id','created_at']) for e in events]}

@router.post('/recovery-scenarios/{scenario_id}/decision')
def scenario_decision(pid:int,scenario_id:int,body:RecoveryDecision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    row=_scenario(db,user,pid,scenario_id)
    previous=row.status
    if body.action=='submit':
        if previous not in ('Draft','Returned'):raise HTTPException(409,'Only draft or returned proposals can be submitted')
        if row.created_by!=user.id and not user.organization_admin:raise HTTPException(403,'Only creator or organization admin can submit')
        row.status='Pending Review'
    elif body.action in ('review_approve','review_reject'):
        if previous!='Pending Review':raise HTTPException(409,'Scenario is not pending review')
        if body.department not in (row.required_reviews or []):raise HTTPException(422,'Department not required by proposal')
        if row.created_by==user.id:raise HTTPException(403,'Creator cannot review own proposal')
        # Until department membership/authority is integrated, restrict review decisions to administrators.
        if not user.organization_admin:raise HTTPException(403,'Organization administrator review required')
        last=db.query(PlanningRecoveryReview).filter_by(scenario_id=row.id,department=body.department).order_by(PlanningRecoveryReview.id.desc()).first()
        if last is not None:raise HTTPException(409,'Department review already submitted')
        db.add(PlanningRecoveryReview(scenario_id=row.id,project_id=pid,organization_id=user.organization_id,
             department=body.department,decision='Approved' if body.action=='review_approve' else 'Rejected',
             comment=body.comment,actor_id=user.id))
        if body.action=='review_reject':row.status='Returned'
    elif body.action in ('approve','return'):
        if previous!='Pending Review':raise HTTPException(409,'Only pending proposals can be decided')
        if not user.organization_admin:raise HTTPException(403,'Organization administrator approval required')
        if row.created_by==user.id:raise HTTPException(403,'Creator cannot approve or return own proposal')
        if body.action=='approve':
            reviews=db.query(PlanningRecoveryReview).filter_by(scenario_id=row.id).all()
            approved={r.department for r in reviews if r.decision=='Approved'}
            if not set(row.required_reviews or []).issubset(approved):raise HTTPException(409,'Mandatory departmental reviews incomplete')
            row.status='Approved Proposal'
        else:row.status='Returned'
    db.add(PlanningRecoveryEvent(scenario_id=row.id,project_id=pid,organization_id=user.organization_id,
            previous_status=previous,next_status=row.status,action=body.action,comment=body.comment,actor_id=user.id))
    db.commit();db.refresh(row)
    return {'id':row.id,'status':row.status,'note':'Proposal decision only; no schedule, baseline, cost, QA or HSE change is applied'}
