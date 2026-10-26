"""Authorization-checked, side-effect-free schedule forecast preview."""
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from .workspace_router import access, ref, values
from .workspace_models import PlanningSchedule, PlanningActivity, PlanningDependency, PlanningCalendar
from .forecast_engine import preview
from .forecast_models import PlanningForecastRevision
from .scheduling_engine import ScheduleError
from .forecast_reconciliation import reconcile
from .productivity_recommendations import estimate_remaining
from .productivity_history import summarize_daily_lines
from .labor_productivity import calculate_labor_productivity
from .actuals_router import actual_progress

router=APIRouter(prefix='/api/projects/{pid}/planning',tags=['Planning Forecast Preview'])

class RemainingInput(BaseModel):
    activity_id: int
    completed: bool = False
    remaining_hours: float | None = Field(default=None, ge=0, le=100000)
    @model_validator(mode='after')
    def valid(self):
        if not self.completed and self.remaining_hours is None:
            raise ValueError('Remaining hours are required for unfinished activities')
        return self

class ForecastInput(BaseModel):
    data_date: date
    activities: list[RemainingInput] = Field(min_length=1,max_length=2000)

@router.post('/schedules/{schedule_id}/forecast-preview')
def forecast_preview(pid:int,schedule_id:int,body:ForecastInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,write=True)
    sched=ref(db,PlanningSchedule,schedule_id,pid)
    rows=db.query(PlanningActivity).filter_by(project_id=pid,schedule_id=schedule_id,organization_id=user.organization_id).all()
    if len(rows)>2000:raise HTTPException(422,'Schedule exceeds supported preview limit')
    deps=db.query(PlanningDependency).filter_by(project_id=pid,schedule_id=schedule_id,organization_id=user.organization_id).all()
    calendars={c.id:{'working_days':c.working_days,'shift_start':c.shift_start,'shift_end':c.shift_end,'holidays':c.holidays,'timezone':c.timezone,'version':c.version} for c in db.query(PlanningCalendar).filter_by(project_id=pid,organization_id=user.organization_id).all()}
    updates={}
    for a in body.activities:
        if a.activity_id in updates:raise HTTPException(422,'Duplicate forecast activity input')
        updates[a.activity_id]={'completed':a.completed,'remaining_hours':a.remaining_hours}
    try:
        result=preview([values(a,'id','code','name','activity_type','duration_hours','calendar_id') for a in rows],
            [values(d,'predecessor_id','successor_id','relation','lag_hours') for d in deps],calendars,body.data_date,updates)
    except ScheduleError as exc:raise HTTPException(422,str(exc)) from exc
    result['schedule_id']=sched.id
    result['schedule_status']=sched.status
    result['schedule_version']=sched.version
    return result


class ForecastDecision(BaseModel):
    action: str
    note: str = Field(default='', max_length=2000)

@router.post('/schedules/{schedule_id}/forecast-revisions', status_code=201)
def save_forecast_revision(pid:int,schedule_id:int,body:ForecastInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    """Recalculate on the server, save immutable planner inputs and result; no baseline modifications."""
    checked = forecast_preview(pid,schedule_id,body,user,db)
    try:
        latest=db.query(func.max(PlanningForecastRevision.revision)).filter_by(
            organization_id=user.organization_id,project_id=pid,schedule_id=schedule_id).scalar() or 0
        row=PlanningForecastRevision(organization_id=user.organization_id,project_id=pid,schedule_id=schedule_id,
            revision=latest+1,data_date=body.data_date,status='Draft',
            inputs=body.model_dump(mode='json'),result=checked,submitted_by=user.id)
        db.add(row);db.commit();db.refresh(row)
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Concurrent forecast revision; retry')
    return {'id':row.id,'revision':row.revision,'status':row.status,'data_date':row.data_date,'basis':checked.get('basis')}

@router.get('/schedules/{schedule_id}/forecast-revisions')
def list_forecast_revisions(pid:int,schedule_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid)
    ref(db,PlanningSchedule,schedule_id,pid)
    rows=db.query(PlanningForecastRevision).filter_by(organization_id=user.organization_id,
        project_id=pid,schedule_id=schedule_id).order_by(PlanningForecastRevision.revision.desc()).limit(100).all()
    return [{'id':r.id,'revision':r.revision,'status':r.status,'data_date':r.data_date,
        'created_at':r.created_at,'reviewed_at':r.reviewed_at,
        'forecast_finish':r.result.get('project_finish'), 'basis':r.result.get('basis')} for r in rows]

@router.get('/schedules/{schedule_id}/forecast-revisions/{revision_id}')
def get_forecast_revision(pid:int,schedule_id:int,revision_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid)
    row=db.query(PlanningForecastRevision).filter_by(id=revision_id,organization_id=user.organization_id,
        project_id=pid,schedule_id=schedule_id).one_or_none()
    if not row:raise HTTPException(404,'Forecast revision not found')
    return {'id':row.id,'revision':row.revision,'status':row.status,'data_date':row.data_date,
        'result':row.result,'inputs':row.inputs,'review_note':row.review_note}

@router.post('/schedules/{schedule_id}/forecast-revisions/{revision_id}/decision')
def decide_forecast_revision(pid:int,schedule_id:int,revision_id:int,body:ForecastDecision,
        user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,write=True)
    row=db.query(PlanningForecastRevision).filter_by(id=revision_id,organization_id=user.organization_id,
        project_id=pid,schedule_id=schedule_id).with_for_update().one_or_none()
    if not row:raise HTTPException(404,'Forecast revision not found')
    action=body.action.strip().lower()
    if action=='submit' and row.status=='Draft':
        if row.submitted_by != user.id:raise HTTPException(403,'Only the author may submit')
        row.status='Pending Review'
    elif action in ('approve','return','reject') and row.status=='Pending Review':
        if not user.organization_admin:raise HTTPException(403,'Independent organization administrator approval required')
        if row.submitted_by == user.id:raise HTTPException(403,'Self approval prohibited')
        row.status={'approve':'Approved','return':'Returned','reject':'Rejected'}[action]
        row.reviewed_by=user.id;row.reviewed_at=datetime.now(timezone.utc)
    else:raise HTTPException(409,'Invalid forecast transition')
    row.review_note=body.note
    db.commit()
    return {'id':row.id,'revision':row.revision,'status':row.status}


@router.get('/schedules/{schedule_id}/forecast-revisions/{revision_id}/reconciliation')
def forecast_revision_reconciliation(pid:int,schedule_id:int,revision_id:int,
        user:User=Depends(authenticated),db:Session=Depends(get_db)):
    """Read-only diagnostic, never modifies the saved revision or source actuals."""
    access(db,user,pid)
    ref(db,PlanningSchedule,schedule_id,pid)
    row=db.query(PlanningForecastRevision).filter_by(id=revision_id,
        organization_id=user.organization_id,project_id=pid,schedule_id=schedule_id).one_or_none()
    if row is None:raise HTTPException(404,'Forecast revision not found')
    actual=actual_progress(pid,schedule_id,user,db)
    comparisons=reconcile((row.inputs or {}).get('activities') or [],actual['activities'])
    return {'revision':row.revision,'status':row.status,'forecast_data_date':row.data_date.isoformat(),
        'source_retrieved_at':actual['retrieved_at'],'source_basis':actual['basis'],
        'reconciliation':comparisons,'note':'This check does not retroactively verify saved forecast assumptions.'}


class ProductivityInput(BaseModel):
    activity_id: int
    productivity_units_per_hour: float = Field(gt=0, le=1000000000)
    quantity_unit: str = Field(min_length=1, max_length=40)

class ProductivityRequest(BaseModel):
    activities: list[ProductivityInput] = Field(min_length=1, max_length=2000)

@router.post('/schedules/{schedule_id}/remaining-duration-recommendations')
def remaining_duration_recommendations(pid:int,schedule_id:int,body:ProductivityRequest,
        user:User=Depends(authenticated),db:Session=Depends(get_db)):
    """Read-only estimates; no forecast, baseline, or Construction records are changed."""
    access(db,user,pid,write=True)
    ref(db,PlanningSchedule,schedule_id,pid)
    current=actual_progress(pid,schedule_id,user,db)
    lookup={row['activity_id']:row for row in current['activities']}
    seen=set()
    output=[]
    for item in body.activities:
        if item.activity_id in seen:
            raise HTTPException(422,'Duplicate activity productivity input')
        seen.add(item.activity_id)
        if item.activity_id not in lookup:
            raise HTTPException(422,'Activity is not part of this schedule')
        recommendation=estimate_remaining(lookup[item.activity_id],item.productivity_units_per_hour,item.quantity_unit)
        output.append({'activity_id':item.activity_id,
                       'activity_code':lookup[item.activity_id]['activity_code'],**recommendation})
    return {'schedule_id':schedule_id,'current_source_retrieved_at':current['retrieved_at'],
            'historical_as_of_reconciliation':False,'persists_changes':False,
            'requires_planner_review':True,'activities':output}


@router.get('/schedules/{schedule_id}/productivity-history')
def productivity_history(pid:int,schedule_id:int,data_date:date,window_days:int=28,
        user:User=Depends(authenticated),db:Session=Depends(get_db)):
    """Retrospective daily output from currently approved Construction reports; no writes."""
    from datetime import date as date_cls
    from app.domains.construction.models import ConstructionActivity, WorkPackage, ProgressLine, ProgressReport
    from .workspace_models import PlanningActivity
    from .actuals_router import actual_progress
    if window_days < 7 or window_days > 90:
        raise HTTPException(422,'Window must be between 7 and 90 days')
    if data_date > date_cls.today():
        raise HTTPException(422,'Future reporting data date is not allowed')
    access(db,user,pid)
    ref(db,PlanningSchedule,schedule_id,pid)
    linked=actual_progress(pid,schedule_id,user,db)
    results=[]
    for entry in linked['activities']:
        if entry['link_status']!='linked' or not entry.get('source'):
            results.append({'activity_id':entry['activity_id'],'activity_code':entry['activity_code'],
                'status':'unavailable','reason':'Construction source is missing, unverified or not uniquely mapped'})
            continue
        measure=entry.get('measurement') or {}
        if measure.get('method') not in ('Quantity','Quantity-based','Quantity based'):
            results.append({'activity_id':entry['activity_id'],'activity_code':entry['activity_code'],
                'status':'unavailable','reason':'Historical quantity trend is supported only for quantity-measured activities'})
            continue
        sid=entry['source']['construction_activity_id']
        rows=(db.query(ProgressReport.report_date,ProgressLine.quantity,ProgressLine.reverses_line_id,
                       ProgressLine.rework,ProgressLine.unit,ProgressReport.status)
             .join(ProgressReport,ProgressReport.id==ProgressLine.report_id)
             .filter(ProgressLine.activity_id==sid,ProgressReport.project_id==pid,
                     ProgressReport.organization_id==user.organization_id,
                     ProgressReport.report_date<=data_date)
             .all())
        normalized=[(r[0],r[1],bool(r[2]),bool(r[3]),r[4],r[5]=='Approved') for r in rows]
        summary=summarize_daily_lines(normalized,measure.get('unit') or '',data_date,window_days)
        results.append({'activity_id':entry['activity_id'],'activity_code':entry['activity_code'],**summary})
    return {'schedule_id':schedule_id,'data_date':data_date.isoformat(),'window_days':window_days,
        'basis':'Retrospective work-date trend from currently approved reports; historical approval state unavailable',
        'historical_as_of_reconstruction':False,'automatic_forecast_changes':False,'activities':results}


@router.get('/schedules/{schedule_id}/labor-productivity')
def labor_productivity(pid:int,schedule_id:int,data_date:date,window_days:int=28,
        user:User=Depends(authenticated),db:Session=Depends(get_db)):
    """Read-only retrospective activity-booked labor-hours. Project Planning RBAC applies."""
    from datetime import date as date_cls
    from app.domains.construction.models import ProgressLine, ProgressReport, ProgressLabour
    if not 7<=window_days<=90:raise HTTPException(422,'Window must be between 7 and 90 days')
    if data_date>date_cls.today():raise HTTPException(422,'Future data dates are not supported')
    access(db,user,pid)
    ref(db,PlanningSchedule,schedule_id,pid)
    actual=actual_progress(pid,schedule_id,user,db)
    results=[]
    for activity in actual['activities']:
        entry={'activity_id':activity['activity_id'],'activity_code':activity['activity_code']}
        if activity.get('link_status')!='linked' or not activity.get('source'):
            results.append({**entry,'status':'unavailable','reason':'No authorized, uniquely mapped Construction source'});continue
        measurement=activity.get('measurement') or {}
        if measurement.get('method') not in ('Quantity','Quantity-based','Quantity based'):
            results.append({**entry,'status':'unavailable','reason':'Quantity-based source required'});continue
        unit=measurement.get('unit') or ''
        source_id=activity['source']['construction_activity_id']
        from_date=data_date-__import__('datetime').timedelta(days=window_days-1)
        rows=(db.query(ProgressLine.id,ProgressReport.report_date,ProgressLine.quantity,ProgressLine.unit,
                       ProgressReport.status,ProgressLine.rework,ProgressLine.reverses_line_id,
                       ProgressLabour.productive_minutes,ProgressLabour.idle_minutes)
              .join(ProgressReport,ProgressReport.id==ProgressLine.report_id)
              .outerjoin(ProgressLabour,ProgressLabour.line_id==ProgressLine.id)
              .filter(ProgressLine.activity_id==source_id,ProgressReport.project_id==pid,
                      ProgressReport.organization_id==user.organization_id,
                      ProgressReport.report_date>=from_date,ProgressReport.report_date<=data_date)
              .all())
        normalized=[(r[0],r[1],r[2],r[3],r[4]=='Approved',bool(r[5]),bool(r[6]),r[7],r[8]) for r in rows]
        results.append({**entry,**calculate_labor_productivity(normalized,unit,data_date,window_days)})
    return {'schedule_id':schedule_id,'data_date':data_date.isoformat(),'window_days':window_days,
        'basis':'Retrospective currently-approved Construction activity labor lines, not HR attendance or historical approval-as-of',
        'forecast_changes':False,'activities':results}

@router.get('/schedules/{schedule_id}/equipment-productivity')
def equipment_productivity(pid:int,schedule_id:int,data_date:date,window_days:int=28,
        user:User=Depends(authenticated),db:Session=Depends(get_db)):
    """Read-only retrospective activity-equipment-hour rate; no forecast writes."""
    from datetime import date as date_cls, timedelta
    from app.domains.construction.models import ProgressLine, ProgressReport
    from .equipment_productivity import calculate_equipment_productivity
    if not 7 <= window_days <= 90:
        raise HTTPException(422, 'Window must be between 7 and 90 days')
    if data_date > date_cls.today():
        raise HTTPException(422, 'Future data dates are not supported')
    access(db,user,pid)
    ref(db,PlanningSchedule,schedule_id,pid)
    actual=actual_progress(pid,schedule_id,user,db)
    results=[]
    for activity in actual['activities']:
        entry={'activity_id':activity['activity_id'],'activity_code':activity['activity_code']}
        if activity.get('link_status')!='linked' or not activity.get('source'):
            results.append({**entry,'status':'unavailable','reason':'No authorized, uniquely mapped Construction source'});continue
        measurement=activity.get('measurement') or {}
        if measurement.get('method') not in ('Quantity','Quantity-based','Quantity based'):
            results.append({**entry,'status':'unavailable','reason':'Quantity-based source required'});continue
        unit=measurement.get('unit') or ''
        source_id=activity['source']['construction_activity_id']
        rows=(db.query(ProgressLine.id,ProgressReport.report_date,ProgressLine.quantity,ProgressLine.unit,
                       ProgressReport.status,ProgressLine.rework,ProgressLine.reverses_line_id,
                       ProgressLine.equipment_hours)
              .join(ProgressReport,ProgressReport.id==ProgressLine.report_id)
              .filter(ProgressLine.activity_id==source_id,ProgressReport.project_id==pid,
                      ProgressReport.organization_id==user.organization_id,
                      ProgressReport.report_date>=data_date-timedelta(days=window_days-1),
                      ProgressReport.report_date<=data_date).all())
        normalized=[(r[0],r[1],r[2],r[3],r[4]=='Approved',bool(r[5]),bool(r[6]),r[7]) for r in rows]
        results.append({**entry,**calculate_equipment_productivity(normalized,unit,data_date,window_days)})
    return {'schedule_id':schedule_id,'data_date':data_date.isoformat(),'window_days':window_days,
            'basis':'Retrospective currently-approved Construction activity equipment-hour entries; '
                    'not a verified equipment utilization or historical approval-as-of record',
            'forecast_changes':False,'activities':results}


class ResourceScenarioItem(BaseModel):
    activity_id: int
    quantity_unit: str = Field(min_length=1, max_length=40)
    labor_rate: float | None = Field(default=None, gt=0)
    workers: float | None = Field(default=None, gt=0)
    labor_hours_per_worker_day: float | None = Field(default=None, gt=0, le=24)
    equipment_rate: float | None = Field(default=None, gt=0)
    equipment_count: float | None = Field(default=None, gt=0)
    equipment_hours_per_unit_day: float | None = Field(default=None, gt=0, le=24)

class ResourceScenarioRequest(BaseModel):
    activities: list[ResourceScenarioItem] = Field(min_length=1, max_length=2000)

@router.post('/schedules/{schedule_id}/resource-scenario-preview')
def resource_scenario_preview(pid:int,schedule_id:int,body:ResourceScenarioRequest,
        user:User=Depends(authenticated),db:Session=Depends(get_db)):
    """Read-only scenario. Never saves resource allocations or modifies forecast revisions."""
    from .resource_scenario import resource_scenario
    access(db,user,pid,write=True)
    ref(db,PlanningSchedule,schedule_id,pid)
    current=actual_progress(pid,schedule_id,user,db)
    lookup={r['activity_id']:r for r in current['activities']}
    seen=set()
    results=[]
    for row in body.activities:
        if row.activity_id in seen:raise HTTPException(422,'Duplicate activity resource scenario')
        seen.add(row.activity_id)
        if row.activity_id not in lookup:raise HTTPException(422,'Activity is not part of this schedule')
        source=lookup[row.activity_id]
        result=resource_scenario(source,unit=row.quantity_unit,
            labor_rate=row.labor_rate,workers=row.workers,
            labor_hours_per_worker_day=row.labor_hours_per_worker_day,
            equipment_rate=row.equipment_rate,equipment_count=row.equipment_count,
            equipment_hours_per_unit_day=row.equipment_hours_per_unit_day)
        results.append({'activity_id':row.activity_id,'activity_code':source['activity_code'],**result})
    return {'schedule_id':schedule_id,'source_retrieved_at':current['retrieved_at'],
        'persisted':False,'updates_approved_forecast':False,'uses_confirmed_availability':False,
        'activities':results}

# Phase 27: compare planner's forecast windows with confirmed reservation windows.
# This reports coverage evidence only; it does not perform resource-constrained CPM.
class ResourceWindow(BaseModel):
    activity_id: int
    starts_at: datetime
    ends_at: datetime
    @model_validator(mode='after')
    def check_window(self):
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None or self.starts_at >= self.ends_at:
            raise ValueError('A valid timezone-aware forecast window is required')
        return self

class ResourceCoverageRequest(BaseModel):
    activities: list[ResourceWindow] = Field(min_length=1, max_length=2000)

@router.post('/schedules/{schedule_id}/resource-coverage-preview')
def resource_coverage_preview(pid: int, schedule_id: int, body: ResourceCoverageRequest,
                              user: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Check resource reservation coverage without changing plans or publication."""
    from .workspace_models import PlanningResourceAllocation, PlanningResourceDemand, PlanningEquipmentAsset
    from .resource_coverage import coverage
    from .resource_capacity import equipment_demand_evidence
    access(db, user, pid, write=True)
    ref(db, PlanningSchedule, schedule_id, pid)
    ids = [a.activity_id for a in body.activities]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, 'Duplicate activity windows')
    existing = db.query(PlanningActivity.id).filter_by(
        organization_id=user.organization_id, project_id=pid, schedule_id=schedule_id
    ).all()
    allowed = {a[0] for a in existing}
    if set(ids) - allowed:
        raise HTTPException(422, 'Activity does not belong to selected schedule')
    reservations = db.query(PlanningResourceAllocation).filter_by(
        organization_id=user.organization_id, project_id=pid, schedule_id=schedule_id
    ).all()
    demands = db.query(PlanningResourceDemand).filter_by(
        organization_id=user.organization_id, project_id=pid, schedule_id=schedule_id
    ).all()
    assets = db.query(PlanningEquipmentAsset).filter_by(organization_id=user.organization_id).all()
    rows = []
    for item in body.activities:
        capacity = equipment_demand_evidence(item.activity_id, item.starts_at, item.ends_at, reservations, demands, assets=assets)
        rows.append({'resource_demand_evidence': capacity, 'activity_id': item.activity_id,
                     'starts_at': item.starts_at.isoformat(), 'ends_at': item.ends_at.isoformat(),
                     'coverage': coverage(item.activity_id, item.starts_at, item.ends_at, reservations)})
    return {'schedule_id': schedule_id, 'basis': 'TYPE_MATCHED_REGISTERED_EQUIPMENT_RESERVATION_EVIDENCE_V3',
            'is_resource_leveled_cpm': False, 'future_headcount_verified': False,
            'approved_baseline_unchanged': True, 'forecast_revision_saved': False,
            'note': 'Only registered assets with matching equipment types, reviewed current inspection evidence, and complete confirmed booking windows count toward unit-demand. Booking counts do not verify equipment operating capacity, future workforce headcount, safety authorization or resource-leveled schedule dates.',
            'activities': rows}
