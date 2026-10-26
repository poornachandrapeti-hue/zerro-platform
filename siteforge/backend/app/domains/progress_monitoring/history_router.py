"""Explicit historical captures and read-only calculated alert indicators.

These captures represent the value at capture time, not backdated transaction
reconstructions. Never fabricate missing observations or expose scoped totals.
"""
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from .alerts_models import ProgressAlertPolicy, ProgressAlertEvent
from .alert_rules import evaluate_progress_alerts
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.models import User
from .router import dashboard, progress_scope
from .reports_router import allowed
from .history_models import ProgressObservation

router=APIRouter(prefix='/api/projects/{pid}/progress',tags=['Progress History'])

def serialize(row):
    return {'id':row.id,'data_date':row.data_date.isoformat(),
            'captured_at':row.captured_at.isoformat(),'publication_id':row.publication_id,
            'verified_percent':float(row.verified_percent),'baseline_version':row.activity_snapshot.get('baseline_revision'),
            'calculation_method':'approved weight × supervisor-verified percent'}

@router.get('/history')
def history(pid:int,publication_id:int|None=None,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    if not progress_scope(db,user,pid)['all']:
        raise HTTPException(403,'Full-scope membership is required for project-wide historical percentages')
    query=db.query(ProgressObservation).filter_by(project_id=pid,organization_id=user.organization_id)
    if publication_id is not None:query=query.filter_by(publication_id=publication_id)
    rows=query.order_by(ProgressObservation.data_date,ProgressObservation.id).limit(500).all()
    return {'observations':[serialize(r) for r in rows],
            'note':'Each value is a captured observation (not reconstructed history). Baselines are kept separate.'}

@router.post('/history/capture',status_code=201)
def capture(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    allowed(db,user,pid,'planning.manage')
    data=dashboard(pid,None,None,None,user,db)
    percent=data['stages']['construction']['percent']
    if not data.get('publication') or percent is None or data.get('exceptions'):
        raise HTTPException(422,'Complete approved, unfiltered baseline and clean source measurements required for capture')
    day=date.today(); pub=data['publication']['id']
    if db.query(ProgressObservation).filter_by(project_id=pid,publication_id=pub,data_date=day).first():
        raise HTTPException(409,'An observation is already frozen for this baseline and data date')
    row=ProgressObservation(organization_id=user.organization_id,project_id=pid,publication_id=pub,
        data_date=day,captured_by=user.id,verified_percent=percent,
        activity_snapshot={'baseline_revision':data['publication']['revision'],
            'source_cutoff':data['retrieved_at'],'measurement':data['measure'],
            'activities':data['actuals'],'calculation_method':data['calculation_method']})
    db.add(row);db.commit();db.refresh(row)
    return serialize(row)

class AlertSettings(BaseModel):
    warning_pp:float=Field(gt=0,le=100)
    critical_pp:float=Field(gt=0,le=100)
    enabled:bool=False
    recipient_ids:list[int]=Field(default_factory=list,max_length=50)
    escalate_after_hours:int=Field(default=24,ge=1,le=720)

def alert_policy(db,user,pid):
    policy=db.query(ProgressAlertPolicy).filter_by(project_id=pid,organization_id=user.organization_id).first()
    return policy

@router.get('/alerts/settings')
def settings(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    allowed(db,user,pid,'planning.view')
    policy=alert_policy(db,user,pid)
    return {'warning_pp':float(policy.warning_pp) if policy else 5,
            'critical_pp':float(policy.critical_pp) if policy else 10,
            'enabled':bool(policy.enabled) if policy else False,
            'recipient_ids':list(policy.recipient_ids or []) if policy else [],
            'escalate_after_hours':int(policy.escalate_after_hours) if policy else 24}

@router.put('/alerts/settings')
def update_settings(pid:int,body:AlertSettings,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    allowed(db,user,pid,'planning.manage')
    if body.critical_pp<=body.warning_pp:raise HTTPException(422,'Critical threshold must exceed warning threshold')
    policy=alert_policy(db,user,pid)
    if not policy:
        policy=ProgressAlertPolicy(project_id=pid,organization_id=user.organization_id,updated_by=user.id)
        db.add(policy)
    # Every recipient must currently hold unrestricted internal Progress access.
    from .reports_router import allowed as authorize
    unique_ids=list(dict.fromkeys(body.recipient_ids))
    for uid in unique_ids:
        recipient=db.get(User,uid)
        if not recipient or recipient.organization_id != user.organization_id:
            raise HTTPException(422,'Recipient is not in this organization')
        authorize(db,recipient,pid,'planning.view')
    policy.enabled=body.enabled;policy.recipient_ids=unique_ids
    policy.escalate_after_hours=body.escalate_after_hours
    policy.warning_pp=body.warning_pp;policy.critical_pp=body.critical_pp
    policy.updated_by=user.id;policy.updated_at=datetime.now(timezone.utc)
    db.commit()
    return {'warning_pp':body.warning_pp,'critical_pp':body.critical_pp,'enabled':body.enabled,'recipient_ids':unique_ids,'escalate_after_hours':body.escalate_after_hours}

def event_data(row):
    return {'id':row.id,'type':row.kind,'severity':row.severity,'message':row.message,
        'state':row.state,'first_seen':row.first_seen,'last_seen':row.last_seen,
        'acknowledged_by':row.acknowledged_by,'escalated_by':row.escalated_by}

@router.get('/alerts')
def alerts(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    data=dashboard(pid,None,None,None,user,db)
    policy=alert_policy(db,user,pid)
    warning=float(policy.warning_pp) if policy else 5
    critical=float(policy.critical_pp) if policy else 10
    warnings=evaluate_progress_alerts(data,warning,critical)
    # Read-only access never persists/project-publishes alerts. Only unrestricted
    # manage users can write a project-level register through explicit evaluation.
    return {'alerts':warnings,'threshold_pp':-warning,'critical_threshold_pp':-critical,
        'delivery':'On-demand evaluation only; no automatic notification or scheduler'}

@router.post('/alerts/evaluate')
def evaluate_and_store(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    allowed(db,user,pid,'planning.manage')
    data=dashboard(pid,None,None,None,user,db)
    policy=alert_policy(db,user,pid)
    warnings=evaluate_progress_alerts(data,float(policy.warning_pp) if policy else 5,
                                     float(policy.critical_pp) if policy else 10)
    now=datetime.now(timezone.utc)
    for warning in warnings:
        row=db.query(ProgressAlertEvent).filter_by(project_id=pid,organization_id=user.organization_id,
                     fingerprint=warning['fingerprint']).first()
        if row is None:
            row=ProgressAlertEvent(project_id=pid,organization_id=user.organization_id,
                fingerprint=warning['fingerprint'],kind=warning['type'],
                severity=warning['severity'],message=warning['message'],state='Open',
                first_seen=now,last_seen=now)
            db.add(row)
        else:
            row.last_seen=now;row.message=warning['message'];row.severity=warning['severity']
    db.commit()
    return {'evaluated':len(warnings),'message':'On-demand evaluation completed. No notifications dispatched.'}

@router.get('/alerts/register')
def alert_register(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    allowed(db,user,pid,'planning.view')
    rows=db.query(ProgressAlertEvent).filter_by(project_id=pid,organization_id=user.organization_id).order_by(ProgressAlertEvent.id.desc()).limit(200).all()
    return {'items':[event_data(row) for row in rows]}

@router.post('/alerts/register/{alert_id}/acknowledge')
def acknowledge(pid:int,alert_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    allowed(db,user,pid,'planning.manage')
    row=db.query(ProgressAlertEvent).filter_by(id=alert_id,project_id=pid,organization_id=user.organization_id).first()
    if row is None:raise HTTPException(404,'Alert not found')
    if row.state!='Open':raise HTTPException(409,'Only open alerts may be acknowledged')
    row.state='Acknowledged';row.acknowledged_by=user.id;row.acknowledged_at=datetime.now(timezone.utc)
    db.commit()
    return event_data(row)

@router.post('/alerts/register/{alert_id}/escalate')
def escalate(pid:int,alert_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    allowed(db,user,pid,'planning.manage')
    row=db.query(ProgressAlertEvent).filter_by(id=alert_id,project_id=pid,organization_id=user.organization_id).first()
    if row is None:raise HTTPException(404,'Alert not found')
    if row.state=='Escalated':raise HTTPException(409,'Alert already escalated')
    row.state='Escalated';row.escalated_by=user.id;row.escalated_at=datetime.now(timezone.utc)
    db.commit()
    return event_data(row)
