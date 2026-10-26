"""Explicit period target register and point-in-time progress captures.
No calendar-derived contractual baseline or historical replay is invented.
"""
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from .workspace_router import access
from .workspace_models import PlanningPublication, PlanningPeriodTarget, PlanningProgressCapture
from .actuals_router import actual_progress

router=APIRouter(prefix='/api/projects/{pid}/planning',tags=['Planning Curves'])

class PeriodTarget(BaseModel):
    activity_id:int
    period_end:date
    cumulative_percent:int=Field(ge=0,le=100)
    weight_basis_points:int=Field(ge=1,le=10000)

class TargetBatch(BaseModel):
    targets:list[PeriodTarget]=Field(min_length=1,max_length=10000)

def publication(db,pid,org,pub_id):
    row=db.query(PlanningPublication).filter_by(id=pub_id,project_id=pid,organization_id=org).one_or_none()
    if not row:raise HTTPException(404,'Baseline publication not found')
    if row.status!='Approved':raise HTTPException(409,'Only approved publications support progress curves')
    return row

def validate_targets(targets,activities):
    """Require complete leaf weights and monotonic cumulative activity targets."""
    activity_ids={int(a['id']) for a in activities if a.get('activity_type') in ('Task','Milestone')}
    if not activity_ids:raise ValueError('No leaf activities in approved snapshot')
    by_activity=defaultdict(list)
    seen=set()
    for t in targets:
        key=(t.activity_id,t.period_end)
        if key in seen:raise ValueError('Duplicate activity/period target')
        seen.add(key)
        if t.activity_id not in activity_ids:raise ValueError('Target references non-baseline activity')
        by_activity[t.activity_id].append(t)
    if set(by_activity)!=activity_ids:raise ValueError('Every approved leaf activity needs a target and weight')
    weights={}
    for aid,items in by_activity.items():
        items.sort(key=lambda x:x.period_end)
        if len({t.weight_basis_points for t in items})!=1:raise ValueError('Activity weight cannot vary by period')
        if any(b.cumulative_percent<a.cumulative_percent for a,b in zip(items,items[1:])):
            raise ValueError('Cumulative targets must be nondecreasing')
        weights[aid]=items[0].weight_basis_points
    if sum(weights.values())!=10000:raise ValueError('Approved leaf weights must total exactly 10000 basis points (100%)')
    return weights

@router.post('/publications/{pub_id}/period-targets',status_code=201)
def set_targets(pid:int,pub_id:int,body:TargetBatch,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    if not user.organization_admin:raise HTTPException(403,'Org administrator required to publish period targets')
    pub=publication(db,pid,user.organization_id,pub_id)
    existing=db.query(PlanningPeriodTarget).filter_by(publication_id=pub.id).first()
    if existing:raise HTTPException(409,'Targets already frozen; publish a new baseline revision for changes')
    try:validate_targets(body.targets,pub.snapshot.get('activities',[]))
    except ValueError as ex:raise HTTPException(422,str(ex))
    for t in body.targets:
        db.add(PlanningPeriodTarget(organization_id=user.organization_id,project_id=pid,publication_id=pub.id,created_by=user.id,**t.model_dump()))
    db.commit()
    return {'publication_id':pub.id,'saved':len(body.targets),'status':'frozen','note':'Targets are explicit cumulative activity percentages and approved activity weights'}

@router.get('/publications/{pub_id}/progress-curves')
def get_curves(pid:int,pub_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid)
    pub=publication(db,pid,user.organization_id,pub_id)
    target_rows=db.query(PlanningPeriodTarget).filter_by(publication_id=pub.id,organization_id=user.organization_id,project_id=pid).order_by(PlanningPeriodTarget.period_end).all()
    captures=db.query(PlanningProgressCapture).filter_by(publication_id=pub.id,organization_id=user.organization_id,project_id=pid).order_by(PlanningProgressCapture.captured_at).limit(1000).all()
    plan=[]
    if target_rows:
        weights={x.activity_id:x.weight_basis_points for x in target_rows}
        date_points=sorted({x.period_end for x in target_rows})
        series=defaultdict(list)
        for t in target_rows:series[t.activity_id].append(t)
        for period in date_points:
            values={aid:next((t.cumulative_percent for t in reversed(points) if t.period_end<=period),0) for aid,points in series.items()}
            total=sum(Decimal(weights[aid])*Decimal(values[aid]) for aid in weights)/Decimal(10000)
            plan.append({'date':period.isoformat(),'planned_percent':float(total)})
    observed=[]
    for c in captures:
        snap=c.snapshot or {}
        observed.append({'date':c.captured_at.isoformat(),'verified_percent':snap.get('verified_percent'),
           'complete_weight_basis_points':snap.get('complete_weight_basis_points'),
           'measured_weight_basis_points':snap.get('measured_weight_basis_points'),
           'capture_id':c.id})
    return {'publication_id':pub.id,'revision':pub.revision,'plan_status':'approved_explicit_targets' if plan else 'not_available',
        'observed_status':'point_in_time_captures' if observed else 'not_available',
        'disclaimer':'Observed data are collection-time captures, not reconstructed historical actuals. Null rollups mean incomplete measurements.',
        'planned':plan,'observed':observed}

@router.post('/publications/{pub_id}/capture-progress',status_code=201)
def capture(pid:int,pub_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    pub=publication(db,pid,user.organization_id,pub_id)
    targets=db.query(PlanningPeriodTarget).filter_by(publication_id=pub.id,organization_id=user.organization_id,project_id=pid).all()
    if not targets:raise HTTPException(409,'Explicit approved period targets required before capturing weighted progress')
    weights={t.activity_id:t.weight_basis_points for t in targets}
    source=actual_progress(pid,pub.schedule_id,user,db)
    measures={a['activity_id']:a for a in source['activities']}
    weighted=Decimal(0)
    accounted=0
    details=[]
    for aid,weight in weights.items():
        row=measures.get(aid)
        measure=row.get('measurement') if row else None
        pc=measure.get('verified_percent') if measure else None
        if row and row['link_status']=='linked' and pc is not None:
            try:decimal_pc=Decimal(str(pc))
            except Exception:decimal_pc=Decimal(-1)
            if Decimal(0)<=decimal_pc<=Decimal(100):
                weighted+=Decimal(weight)*decimal_pc
                accounted+=weight
                details.append({'activity_id':aid,'weight_basis_points':weight,'verified_percent':str(decimal_pc),'link_status':'linked'})
                continue
        details.append({'activity_id':aid,'weight_basis_points':weight,'verified_percent':None,'link_status':row['link_status'] if row else 'unmapped'})
    # Unavailable if not all weighted scope has valid, authoritative measurements.
    complete=accounted==10000
    snapshot={'source_retrieved_at':source['retrieved_at'],'verified_percent':float(weighted/Decimal(10000)) if complete else None,
        'complete_weight_basis_points':10000 if complete else 0,'measured_weight_basis_points':accounted,
        'progress_basis':'verified','activity_details':details,'historical_replay':False}
    rec=PlanningProgressCapture(organization_id=user.organization_id,project_id=pid,publication_id=pub.id,captured_by=user.id,snapshot=jsonable_encoder(snapshot))
    db.add(rec);db.commit();db.refresh(rec)
    return {'id':rec.id,'captured_at':rec.captured_at,'snapshot':snapshot}
