"""Planning phase-one APIs. Fail closed on permissions and cross-project references."""
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.domains.identity_projects.models import Project, User, Company, Discipline, Membership, Role, Area
from app.domains.identity_projects.security import authenticated
from .workspace_models import PlanningWBS, PlanningCalendar, PlanningSchedule, PlanningActivity

router = APIRouter(prefix='/api/projects/{pid}/planning', tags=['Planning Workspace'])

def access(db, user, pid, write=False):
    """Internal Planning guard. Partner-only grants never unlock internal routes.

    Roles are checked per active membership, rather than merging all permissions
    across partner and internal memberships. This protects against a partner role
    later being accidentally granted broad Planning permissions in role setup.
    """
    project = db.get(Project, pid)
    if not project or project.organization_id != user.organization_id:
        raise HTTPException(404, 'Project not found')
    if not user.active:
        raise HTTPException(403, 'Inactive user')
    if user.organization_admin:
        return project
    required = 'planning.manage' if write else 'planning.view'
    memberships = db.query(Membership).filter_by(
        project_id=pid, user_id=user.id, active=True
    ).all()
    for membership in memberships:
        role = db.get(Role, membership.role_id)
        if not role:
            continue
        permissions = set(role.permissions or [])
        # A partner-designated role cannot become an internal Planning grant,
        # even if someone incorrectly adds planning.view/manage to the role.
        if 'planning.partner.view' in permissions:
            continue
        if required in permissions or (not write and 'planning.manage' in permissions):
            return project
    raise HTTPException(403, f'Internal {required} permission required')

def owned(db, model, id, pid):
    row=db.query(model).filter_by(id=id,project_id=pid).one_or_none()
    if not row: raise HTTPException(422,'Reference not found in this project')
    return row

def ref(db, model, id, pid, required=True):
    if id is None:
        if required: raise HTTPException(422,'Required reference missing')
        return None
    return owned(db,model,id,pid)

def save(db, row):
    db.add(row)
    try:
        db.commit();db.refresh(row)
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Duplicate code or schedule version')
    return row

def values(row, *fields): return {k:getattr(row,k) for k in fields}

class WBSInput(BaseModel):
    code:str=Field(min_length=1,max_length=80)
    name:str=Field(min_length=1,max_length=200)
    parent_id:int|None=None
    description:str=''
    company_id:int|None=None
    discipline_id:int|None=None
    location_id:int|None=None
    owner_id:int|None=None

@router.get('/wbs')
def wbs_list(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid)
    return [values(r,'id','code','name','parent_id','description','company_id','discipline_id','location_id','owner_id','active') for r in db.query(PlanningWBS).filter_by(project_id=pid).order_by(PlanningWBS.code).all()]

@router.post('/wbs',status_code=201)
def wbs_create(pid:int,body:WBSInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    if body.parent_id: ref(db,PlanningWBS,body.parent_id,pid)
    for model,id in ((Company,body.company_id),(Discipline,body.discipline_id),(Area,body.location_id),(User,body.owner_id)):
        if id is not None:
            obj=db.get(model,id)
            if not obj or (hasattr(obj,'project_id') and obj.project_id!=pid) or (hasattr(obj,'organization_id') and obj.organization_id!=user.organization_id):
                raise HTTPException(422,'Invalid company, discipline, location or owner reference')
    row=save(db,PlanningWBS(organization_id=user.organization_id,project_id=pid,**body.model_dump()))
    return values(row,'id','code','name','parent_id')

@router.patch('/wbs/{wbs_id}')
def wbs_update(pid:int,wbs_id:int,body:WBSInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    row=owned(db,PlanningWBS,wbs_id,pid)
    if body.parent_id:
        parent=ref(db,PlanningWBS,body.parent_id,pid)
        visited={row.id}
        while parent:
            if parent.id in visited: raise HTTPException(422,'Circular WBS hierarchy')
            visited.add(parent.id)
            parent=ref(db,PlanningWBS,parent.parent_id,pid) if parent.parent_id else None
    for k,v in body.model_dump().items(): setattr(row,k,v)
    save(db,row)
    return values(row,'id','code','name','parent_id')

class CalendarInput(BaseModel):
    code:str=Field(min_length=1,max_length=80)
    name:str=Field(min_length=1,max_length=200)
    timezone:str='Asia/Kolkata'
    working_days:list[int]=Field(default_factory=lambda:[0,1,2,3,4,5])
    shift_start:str='08:00'
    shift_end:str='17:00'
    holidays:list[date]=Field(default_factory=list)
    @model_validator(mode='after')
    def check(self):
        try: ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError,ValueError): raise ValueError('Unknown timezone')
        if not self.working_days or len(set(self.working_days))!=len(self.working_days) or any(d<0 or d>6 for d in self.working_days): raise ValueError('Working days must be unique values 0-6')
        for clock in (self.shift_start,self.shift_end):
            if len(clock)!=5 or clock[2]!=':' or not clock[:2].isdigit() or not clock[3:].isdigit() or int(clock[:2])>23 or int(clock[3:])>59: raise ValueError('Use HH:MM for shifts')
        if self.shift_start==self.shift_end: raise ValueError('Shift must have nonzero hours')
        return self

@router.get('/calendars')
def calendar_list(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid)
    return [values(r,'id','code','name','timezone','working_days','shift_start','shift_end','holidays','version') for r in db.query(PlanningCalendar).filter_by(project_id=pid).all()]

@router.post('/calendars',status_code=201)
def calendar_create(pid:int,body:CalendarInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    data=body.model_dump(mode='json')
    row=save(db,PlanningCalendar(organization_id=user.organization_id,project_id=pid,**data))
    return values(row,'id','code','name','version')

class ScheduleInput(BaseModel):
    name:str=Field(min_length=1,max_length=200)
    kind:str
    version:str=Field(min_length=1,max_length=50)
    data_date:date
    calendar_id:int
    description:str=''
    @field_validator('kind')
    @classmethod
    def kind_check(cls,v):
        if v not in ('Integrated','Detailed','Recovery','Scenario'): raise ValueError('Invalid schedule type')
        return v

@router.get('/schedules')
def schedule_list(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid)
    return [values(r,'id','name','kind','version','data_date','calendar_id','owner_id','status','description') for r in db.query(PlanningSchedule).filter_by(project_id=pid).order_by(PlanningSchedule.id.desc()).all()]

@router.post('/schedules',status_code=201)
def schedule_create(pid:int,body:ScheduleInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True);ref(db,PlanningCalendar,body.calendar_id,pid)
    row=save(db,PlanningSchedule(organization_id=user.organization_id,project_id=pid,owner_id=user.id,status='Draft',**body.model_dump()))
    return values(row,'id','name','kind','version','status')

class ActivityInput(BaseModel):
    code:str=Field(min_length=1,max_length=80)
    name:str=Field(min_length=1,max_length=240)
    wbs_id:int
    calendar_id:int
    activity_type:str='Task'
    company_id:int
    discipline_id:int|None=None
    owner_id:int|None=None
    location_id:int|None=None
    duration_hours:int|None=Field(default=None,ge=1)
    planned_start:date|None=None
    planned_finish:date|None=None
    progress_method:str|None=None
    source_type:str|None=None
    source_id:str|None=None
    remarks:str=''
    @model_validator(mode='after')
    def checks(self):
        if self.activity_type not in ('Task','Milestone'): raise ValueError('Only Task and Milestone leaf activities are supported in this phase')
        if self.activity_type=='Task' and self.duration_hours is None: raise ValueError('Task requires duration hours')
        if self.planned_start and self.planned_finish and self.planned_finish<self.planned_start: raise ValueError('Finish precedes start')
        if self.progress_method not in (None,'Quantity','Item','Weighted Milestone'): raise ValueError('Invalid progress method')
        if bool(self.source_type) != bool(self.source_id): raise ValueError('Source type and source ID must be supplied together')
        return self

@router.get('/schedules/{schedule_id}/activities')
def activities(pid:int,schedule_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid);ref(db,PlanningSchedule,schedule_id,pid)
    return [values(r,'id','code','name','wbs_id','calendar_id','activity_type','company_id','discipline_id','owner_id','duration_hours','planned_start','planned_finish','progress_method','source_type','source_id','remarks') for r in db.query(PlanningActivity).filter_by(project_id=pid,schedule_id=schedule_id).order_by(PlanningActivity.code).all()]

@router.post('/schedules/{schedule_id}/activities',status_code=201)
def activity_create(pid:int,schedule_id:int,body:ActivityInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    schedule=ref(db,PlanningSchedule,schedule_id,pid)
    if schedule.status!='Draft': raise HTTPException(409,'Only draft schedules may be edited')
    wbs=ref(db,PlanningWBS,body.wbs_id,pid);ref(db,PlanningCalendar,body.calendar_id,pid)
    if not wbs.active: raise HTTPException(422,'WBS is inactive')
    company=db.get(Company,body.company_id)
    if not company or company.organization_id!=user.organization_id: raise HTTPException(422,'Invalid company')
    if body.location_id: ref(db,Area,body.location_id,pid)
    if body.owner_id:
        owner=db.get(User,body.owner_id)
        if not owner or owner.organization_id!=user.organization_id or not owner.active: raise HTTPException(422,'Invalid owner')
    if body.discipline_id and not db.get(Discipline,body.discipline_id): raise HTTPException(422,'Invalid discipline')
    row=save(db,PlanningActivity(organization_id=user.organization_id,project_id=pid,schedule_id=schedule_id,**body.model_dump()))
    return values(row,'id','code','name','activity_type')

# Phase 2: draft-only scheduling and dependency management.
from .workspace_models import PlanningDependency
from .scheduling_engine import calculate, ScheduleError

class DependencyInput(BaseModel):
    predecessor_id:int
    successor_id:int
    relation:str='FS'
    lag_hours:int=Field(default=0,ge=0)
    @field_validator('relation')
    @classmethod
    def relation_check(cls,v):
        if v not in ('FS','SS','FF','SF'):raise ValueError('Relationship must be FS, SS, FF or SF')
        return v

def draft_schedule(db,pid,schedule_id):
    schedule=ref(db,PlanningSchedule,schedule_id,pid)
    if schedule.status!='Draft':raise HTTPException(409,'Scheduling changes allowed only in Draft')
    return schedule

def calculated(db,pid,schedule_id):
    sched=ref(db,PlanningSchedule,schedule_id,pid)
    activities=db.query(PlanningActivity).filter_by(project_id=pid,schedule_id=schedule_id).all()
    deps=db.query(PlanningDependency).filter_by(project_id=pid,schedule_id=schedule_id).all()
    cals={c.id:{'working_days':c.working_days,'shift_start':c.shift_start,'shift_end':c.shift_end,'holidays':c.holidays,'timezone':c.timezone,'version':c.version} for c in db.query(PlanningCalendar).filter_by(project_id=pid).all()}
    items=[values(a,'id','code','name','activity_type','duration_hours','calendar_id') for a in activities]
    links=[values(d,'predecessor_id','successor_id','relation','lag_hours') for d in deps]
    try: result=calculate(items,links,cals,sched.data_date)
    except ScheduleError as exc: raise HTTPException(422,str(exc)) from exc
    result['schedule_id']=schedule_id;result['data_date']=sched.data_date.isoformat();result['calendar_timezones']={k:v['timezone'] for k,v in cals.items()}
    result['dependencies']=[values(d,'id','predecessor_id','successor_id','relation','lag_hours') for d in deps]
    return result

@router.get('/schedules/{schedule_id}/dependencies')
def dependencies_list(pid:int,schedule_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid);ref(db,PlanningSchedule,schedule_id,pid)
    return [values(d,'id','predecessor_id','successor_id','relation','lag_hours') for d in db.query(PlanningDependency).filter_by(project_id=pid,schedule_id=schedule_id).order_by(PlanningDependency.id).all()]

@router.post('/schedules/{schedule_id}/dependencies',status_code=201)
def dependencies_create(pid:int,schedule_id:int,body:DependencyInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True);draft_schedule(db,pid,schedule_id)
    if body.predecessor_id==body.successor_id:raise HTTPException(422,'Self dependency is not allowed')
    for id in (body.predecessor_id,body.successor_id):
        a=ref(db,PlanningActivity,id,pid)
        if a.schedule_id!=schedule_id:raise HTTPException(422,'Dependency activity must belong to selected schedule')
    existing=db.query(PlanningDependency).filter_by(schedule_id=schedule_id).all()
    new={'predecessor_id':body.predecessor_id,'successor_id':body.successor_id,'relation':body.relation,'lag_hours':body.lag_hours}
    if any(d.predecessor_id==body.predecessor_id and d.successor_id==body.successor_id for d in existing):raise HTTPException(409,'Dependency already exists')
    # Validate entire network before insertion, including transitive cycles.
    deps=[values(d,'predecessor_id','successor_id','relation','lag_hours') for d in existing]+[new]
    acts=db.query(PlanningActivity).filter_by(schedule_id=schedule_id,project_id=pid).all()
    calrows=db.query(PlanningCalendar).filter_by(project_id=pid).all()
    calendars={c.id:{'working_days':c.working_days,'shift_start':c.shift_start,'shift_end':c.shift_end,'holidays':c.holidays} for c in calrows}
    try:calculate([values(a,'id','code','name','activity_type','duration_hours','calendar_id') for a in acts],deps,calendars,ref(db,PlanningSchedule,schedule_id,pid).data_date)
    except ScheduleError as exc:raise HTTPException(422,str(exc)) from exc
    d=save(db,PlanningDependency(organization_id=user.organization_id,project_id=pid,schedule_id=schedule_id,**new))
    return values(d,'id','predecessor_id','successor_id','relation','lag_hours')

@router.delete('/schedules/{schedule_id}/dependencies/{dependency_id}')
def dependency_delete(pid:int,schedule_id:int,dependency_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True);draft_schedule(db,pid,schedule_id)
    d=db.query(PlanningDependency).filter_by(id=dependency_id,project_id=pid,schedule_id=schedule_id).one_or_none()
    if not d:raise HTTPException(404,'Dependency not found')
    db.delete(d);db.commit();return {'deleted':True}

@router.get('/schedules/{schedule_id}/calculate')
def schedule_calculate(pid:int,schedule_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid)
    return calculated(db,pid,schedule_id)


# Phase 3: revision-controlled schedule publication. Approval requires a different
# organization administrator; publication snapshots are immutable after submission.
from datetime import datetime, timezone
from .workspace_models import PlanningPublication
from app.domains.identity_projects.models import Audit

class SubmitPublication(BaseModel):
    revision: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=8, max_length=2000)

class PublicationDecision(BaseModel):
    note: str = Field(min_length=5, max_length=2000)

def publication_values(row, include_snapshot=False):
    data=values(row,'id','schedule_id','revision','status','reason','submitted_by','submitted_at','reviewed_by','reviewed_at','decision_note','is_current')
    if include_snapshot:data['snapshot']=row.snapshot
    return data

@router.post('/schedules/{schedule_id}/publications',status_code=201)
def submit_publication(pid:int,schedule_id:int,body:SubmitPublication,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    schedule=draft_schedule(db,pid,schedule_id)
    if schedule.kind=='Scenario':raise HTTPException(422,'Scenario schedules cannot publish a baseline')
    computed=calculated(db,pid,schedule_id)
    activity_rows=db.query(PlanningActivity).filter_by(project_id=pid,schedule_id=schedule_id).order_by(PlanningActivity.id).all()
    if not activity_rows:raise HTTPException(422,'Cannot submit an empty schedule')
    if any(a.owner_id is None for a in activity_rows):raise HTTPException(422,'Assign an owner to every activity before submission')
    calendar_ids={a.calendar_id for a in activity_rows} | {schedule.calendar_id}
    calendar_rows=db.query(PlanningCalendar).filter(PlanningCalendar.project_id==pid,PlanningCalendar.id.in_(calendar_ids)).all()
    snapshot={'schedule':values(schedule,'id','name','kind','version','data_date','calendar_id','owner_id'),
       'activities':[values(a,'id','code','name','wbs_id','calendar_id','activity_type','company_id','discipline_id','owner_id','location_id','duration_hours','planned_start','planned_finish','progress_method','source_type','source_id') for a in activity_rows],
       'calendars':[values(c,'id','code','name','timezone','working_days','shift_start','shift_end','holidays','version') for c in calendar_rows],
       'calculation':computed}
    # JSON timestamps/dates need conversion, preserving the frozen record content.
    from fastapi.encoders import jsonable_encoder
    row=PlanningPublication(organization_id=user.organization_id,project_id=pid,schedule_id=schedule_id,revision=body.revision,reason=body.reason,snapshot=jsonable_encoder(snapshot),submitted_by=user.id)
    db.add(row)
    try:
        db.flush()
        schedule.status='Pending Review'
        db.add(Audit(organization_id=user.organization_id,actor_id=user.id,action='submit',resource='planning_publications',resource_id=row.id,project_id=pid,details={'revision':body.revision}))
        db.commit();db.refresh(row)
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Publication revision already exists')
    return publication_values(row)

@router.get('/publications')
def list_publications(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid)
    rows=db.query(PlanningPublication).filter_by(project_id=pid,organization_id=user.organization_id).order_by(PlanningPublication.id.desc()).all()
    return [publication_values(r) for r in rows]

@router.get('/publications/{publication_id}')
def get_publication(pid:int,publication_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid)
    row=db.query(PlanningPublication).filter_by(id=publication_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if not row:raise HTTPException(404,'Publication not found')
    return publication_values(row,True)

@router.post('/publications/{publication_id}/approve')
def approve_publication(pid:int,publication_id:int,body:PublicationDecision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    if not user.organization_admin:raise HTTPException(403,'Organization administrator approval required in this phase')
    row=db.query(PlanningPublication).filter_by(id=publication_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if not row:raise HTTPException(404,'Publication not found')
    if row.status!='Pending Review':raise HTTPException(409,'Only pending publications may be approved')
    if row.submitted_by==user.id:raise HTTPException(403,'Submitter cannot approve own publication')
    schedule=ref(db,PlanningSchedule,row.schedule_id,pid)
    if schedule.status!='Pending Review':raise HTTPException(409,'Schedule status changed; re-review required')
    # Mark previously current publication(s) as superseded without altering their snapshots.
    for old in db.query(PlanningPublication).filter_by(project_id=pid,is_current=True).all():old.is_current=False
    row.status='Approved';row.is_current=True;row.reviewed_by=user.id;row.reviewed_at=datetime.now(timezone.utc);row.decision_note=body.note
    schedule.status='Approved'
    db.add(Audit(organization_id=user.organization_id,actor_id=user.id,action='approve',resource='planning_publications',resource_id=row.id,project_id=pid,details={'revision':row.revision}))
    db.commit();db.refresh(row)
    return publication_values(row)

@router.post('/publications/{publication_id}/return')
def return_publication(pid:int,publication_id:int,body:PublicationDecision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    if not user.organization_admin:raise HTTPException(403,'Organization administrator review required in this phase')
    row=db.query(PlanningPublication).filter_by(id=publication_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if not row:raise HTTPException(404,'Publication not found')
    if row.status!='Pending Review':raise HTTPException(409,'Only pending publications can be returned')
    if row.submitted_by==user.id:raise HTTPException(403,'Submitter cannot review own publication')
    row.status='Returned';row.reviewed_by=user.id;row.reviewed_at=datetime.now(timezone.utc);row.decision_note=body.note
    schedule=ref(db,PlanningSchedule,row.schedule_id,pid);schedule.status='Draft'
    db.add(Audit(organization_id=user.organization_id,actor_id=user.id,action='return',resource='planning_publications',resource_id=row.id,project_id=pid,details={'revision':row.revision}))
    db.commit();db.refresh(row)
    return publication_values(row)
