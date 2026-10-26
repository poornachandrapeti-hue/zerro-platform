"""Project-scoped planning commitments; readiness is advisory, never an execution release."""
from datetime import date,datetime,timezone,timedelta
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,model_validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from .workspace_router import access,owned
from .workspace_models import PlanningSchedule,PlanningActivity,PlanningLookahead,PlanningLookaheadItem

router=APIRouter(prefix='/api/projects/{pid}/planning',tags=['Planning Look Ahead'])

def obj(row,fields):
    return {k:getattr(row,k) for k in fields}
HEAD=['id','code','schedule_id','horizon','start_date','end_date','status','created_by']
ITEM=['id','activity_id','target_date','target_quantity','target_unit','owner_id','commitment','readiness','readiness_notes','blocker','resolution_owner_id','resolution_due','achieved_quantity','variance_reason','updated_at']
class CreatePlan(BaseModel):
    code:str=Field(min_length=1,max_length=80)
    schedule_id:int
    horizon:str
    start_date:date
    @model_validator(mode='after')
    def check(self):
        if self.horizon not in ('7-day','14-day','monthly'): raise ValueError('Invalid horizon')
        return self
class AddItem(BaseModel):
    activity_id:int
    target_date:date
    owner_id:int
    target_quantity:int|None=Field(default=None,ge=0)
    target_unit:str|None=Field(default=None,max_length=40)
    readiness:str='Unknown'
    readiness_notes:str=Field(default='',max_length=2000)
    blocker:str=Field(default='',max_length=2000)
    resolution_owner_id:int|None=None
    resolution_due:date|None=None
    @model_validator(mode='after')
    def check(self):
        if self.readiness not in ('Unknown','Ready','At Risk','Blocked'): raise ValueError('Invalid readiness')
        if self.target_quantity is not None and not self.target_unit: raise ValueError('Quantity needs a unit')
        return self
class ItemReview(BaseModel):
    commitment:str
    readiness:str
    readiness_notes:str=Field(default='',max_length=2000)
    blocker:str=Field(default='',max_length=2000)
    resolution_owner_id:int|None=None
    resolution_due:date|None=None
    achieved_quantity:int|None=Field(default=None,ge=0)
    variance_reason:str=Field(default='',max_length=2000)
    @model_validator(mode='after')
    def check(self):
        if self.commitment not in ('Pending','Committed','Declined','Completed'): raise ValueError('Invalid commitment')
        if self.readiness not in ('Unknown','Ready','At Risk','Blocked'): raise ValueError('Invalid readiness')
        return self

@router.get('/lookaheads')
def list_plans(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid)
    return [obj(r,HEAD) for r in db.query(PlanningLookahead).filter_by(project_id=pid).order_by(PlanningLookahead.id.desc()).all()]

@router.post('/lookaheads',status_code=201)
def create_plan(pid:int,body:CreatePlan,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    owned(db,PlanningSchedule,body.schedule_id,pid)
    days={'7-day':7,'14-day':14,'monthly':30}[body.horizon]
    row=PlanningLookahead(organization_id=user.organization_id,project_id=pid,**body.model_dump(),end_date=body.start_date+timedelta(days=days-1),created_by=user.id)
    db.add(row)
    try:db.commit();db.refresh(row)
    except IntegrityError:db.rollback();raise HTTPException(409,'Look-ahead code already exists')
    return obj(row,HEAD)

@router.get('/lookaheads/{lid}/items')
def list_items(pid:int,lid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid)
    owned(db,PlanningLookahead,lid,pid)
    return [obj(r,ITEM) for r in db.query(PlanningLookaheadItem).filter_by(project_id=pid,lookahead_id=lid).order_by(PlanningLookaheadItem.target_date).all()]

@router.post('/lookaheads/{lid}/items',status_code=201)
def add_item(pid:int,lid:int,body:AddItem,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    plan=owned(db,PlanningLookahead,lid,pid)
    if plan.status!='Draft':raise HTTPException(409,'Plan is not editable')
    act=owned(db,PlanningActivity,body.activity_id,pid)
    if act.schedule_id!=plan.schedule_id: raise HTTPException(422,'Activity is outside plan schedule')
    if not plan.start_date<=body.target_date<=plan.end_date:raise HTTPException(422,'Target date outside look-ahead window')
    from app.domains.identity_projects.models import Membership
    for uid in (body.owner_id,body.resolution_owner_id):
        if uid is None:continue
        if not db.query(Membership).filter_by(project_id=pid,user_id=uid,active=True).first():raise HTTPException(422,'Owner must have active project membership')
    row=PlanningLookaheadItem(organization_id=user.organization_id,project_id=pid,lookahead_id=lid,**body.model_dump(),updated_by=user.id)
    db.add(row)
    try:db.commit();db.refresh(row)
    except IntegrityError:db.rollback();raise HTTPException(409,'Activity already exists in look-ahead')
    return obj(row,ITEM)

@router.patch('/lookaheads/{lid}/items/{iid}')
def review_item(pid:int,lid:int,iid:int,body:ItemReview,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    owned(db,PlanningLookahead,lid,pid)
    row=owned(db,PlanningLookaheadItem,iid,pid)
    if row.lookahead_id!=lid:raise HTTPException(404,'Item not in this plan')
    if body.resolution_owner_id is not None:
        from app.domains.identity_projects.models import Membership
        if not db.query(Membership).filter_by(project_id=pid,user_id=body.resolution_owner_id,active=True).first():raise HTTPException(422,'Resolution owner not in project')
    if row.target_quantity is not None and body.achieved_quantity is not None and body.achieved_quantity<row.target_quantity and body.commitment=='Completed' and not body.variance_reason.strip():raise HTTPException(422,'Explain missed commitment')
    for k,v in body.model_dump().items():setattr(row,k,v)
    row.updated_by=user.id;row.updated_at=datetime.now(timezone.utc)
    db.commit();db.refresh(row)
    return obj(row,ITEM)

@router.post('/lookaheads/{lid}/publish')
def publish(pid:int,lid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    row=owned(db,PlanningLookahead,lid,pid)
    if row.status!='Draft':raise HTTPException(409,'Already published')
    if not db.query(PlanningLookaheadItem).filter_by(lookahead_id=lid,project_id=pid).first():raise HTTPException(422,'Add activities before publishing')
    row.status='Published';db.commit()
    return obj(row,HEAD)


@router.get('/lookaheads/{lid}/live-readiness')
def live_readiness(pid:int,lid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    """Live, read-only source indicators; never constitutes approval or work release.

    Missing and unmapped sources are Unavailable, not Ready. Source references are
    validated across tenant/project/company/discipline before any gate is read.
    """
    from app.domains.construction.models import ConstructionActivity, WorkPackage, ReadinessCheck
    from app.domains.construction.readiness import live_result
    project=access(db,user,pid)
    plan=owned(db,PlanningLookahead,lid,pid)
    items=db.query(PlanningLookaheadItem).filter_by(project_id=pid,lookahead_id=lid,organization_id=user.organization_id).all()
    activities={a.id:a for a in db.query(PlanningActivity).filter_by(project_id=pid,schedule_id=plan.schedule_id,organization_id=user.organization_id).all()}
    output=[]
    for item in items:
        act=activities.get(item.activity_id)
        result={'item_id':item.id,'activity_id':item.activity_id,'status':'Unavailable','source':'None',
                'package_id':None,'checks':[],'note':'No verified Construction source mapping'}
        if not act:
            output.append(result);continue
        stype=(act.source_type or '').strip().lower()
        sid=str(act.source_id or '').strip()
        if stype not in ('construction_activity','construction.activity') or not sid.isdecimal():
            output.append(result);continue
        source=db.get(ConstructionActivity,int(sid))
        if not source or not source.active or source.project_id!=pid or source.organization_id!=user.organization_id or source.company_id!=act.company_id:
            result['note']='Construction source missing or outside activity scope'
            output.append(result);continue
        package=db.get(WorkPackage,source.package_id)
        if not package or not package.active or package.project_id!=pid or package.organization_id!=user.organization_id or package.company_id!=act.company_id or (act.discipline_id is not None and package.discipline_id!=act.discipline_id):
            result['note']='Work package missing or outside activity scope'
            output.append(result);continue
        # Avoid exposing source evidence through a different company's mapped activity.
        check_rows=db.query(ReadinessCheck).filter_by(package_id=package.id).all()
        checks=[]
        for check in check_rows:
            live=live_result(db,project,package,check,item.target_date)
            checks.append({'type':check.check_type,'classification':check.classification,
                           'state':live['state'],'reason':live['reason'],'owner':live['owner']})
        mandatory=[c for c in checks if c['classification']=='Mandatory']
        result.update(source='Construction',package_id=package.id,checks=checks,
                      status=('Unavailable' if not mandatory else
                              'Blocked' if any(c['state']=='Blocked' for c in mandatory) else
                              'Ready' if all(c['state'] in ('Ready','Not Applicable') for c in mandatory) else 'Pending'),
                      note=('No mandatory readiness controls registered' if not mandatory else
                            'Live source checks; execution release must still be independently verified'))
        if package.release_state!='Released' and result['status']=='Ready':
            result['status']='Pending'
            result['note']='Readiness checks pass, but Construction work package is not released'
        result['release_state']=package.release_state
        output.append(result)
    return {'lookahead_id':lid,'retrieved_at':datetime.now(timezone.utc).isoformat(),
            'advisory_only':True,'items':output}
