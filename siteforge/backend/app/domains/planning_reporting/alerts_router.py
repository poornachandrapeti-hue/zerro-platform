"""On-demand planning alert evaluation and persistent, permission-checked acknowledgement.
No background processing, external notifications, or contractual criticality inference.
"""
from datetime import datetime, timezone, date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from .workspace_router import access
from .workspace_models import (PlanningAlert,PlanningAlertEvent,PlanningResourceDemand,
                               PlanningRecoveryScenario,PlanningLookaheadItem)

router=APIRouter(prefix='/api/projects/{pid}/planning',tags=['Planning Alerts'])

def serialize(alert):
    return {k:getattr(alert,k) for k in ('id','trigger_type','source_type','source_id','title','description',
       'severity','owner_id','status','first_detected_at','last_detected_at','acknowledged_at','resolved_at','resolution_note')}

def candidates(db, pid, org, today):
    """Only evidence-grounded triggers; no implicit availability or CPM assumptions."""
    for r in db.query(PlanningResourceDemand).filter_by(project_id=pid,organization_id=org).all():
        if r.confirmed_capacity is not None and r.demand_quantity>r.confirmed_capacity and r.period_end>=today:
            yield (f'resource:{r.id}','Resource shortfall','resource_demand',r.id,
                f'Resource demand exceeds confirmed capacity: {r.resource_name}',
                f'Demand {r.demand_quantity} {r.demand_unit}; confirmed {r.confirmed_capacity} {r.demand_unit}; source {r.capacity_source}',
                'Warning',r.created_by)
    cutoff=datetime.now(timezone.utc)-timedelta(days=3)
    for r in db.query(PlanningRecoveryScenario).filter_by(project_id=pid,organization_id=org,status='Pending Review').all():
        if r.created_at is not None and r.created_at.replace(tzinfo=r.created_at.tzinfo or timezone.utc)<cutoff:
            yield (f'recovery:{r.id}','Recovery review pending','recovery_scenario',r.id,
                f'Recovery proposal pending review: {r.code}',
                'Proposal has been pending since creation for more than 3 days (submission timestamp not tracked).',
                'Warning',r.created_by)
    for r in db.query(PlanningLookaheadItem).filter_by(project_id=pid,organization_id=org).all():
        if r.blocker and r.resolution_due is not None and r.resolution_due<today and r.readiness!='Ready':
            yield (f'constraint:{r.id}','Unresolved look-ahead blocker','lookahead_item',r.id,
                'Look-ahead blocker is past its resolution date',
                f'Resolution was due {r.resolution_due.isoformat()}: {r.blocker[:400]}',
                'High',r.resolution_owner_id or r.owner_id)

@router.get('/alerts')
def list_alerts(pid:int,status:str|None=None,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid)
    if status and status not in ('Open','Acknowledged','Resolved'):raise HTTPException(422,'Invalid status')
    q=db.query(PlanningAlert).filter_by(project_id=pid,organization_id=user.organization_id)
    if status:q=q.filter_by(status=status)
    return [serialize(a) for a in q.order_by(PlanningAlert.id.desc()).limit(500).all()]

@router.post('/alerts/evaluate')
def evaluate_alerts(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    now=datetime.now(timezone.utc)
    created=0;updated=0
    for key,trigger,source_type,source_id,title,description,severity,owner_id in candidates(db,pid,user.organization_id,now.date()):
        row=db.query(PlanningAlert).filter_by(project_id=pid,organization_id=user.organization_id,dedupe_key=key).one_or_none()
        if row is None:
            db.add(PlanningAlert(organization_id=user.organization_id,project_id=pid,dedupe_key=key,
              trigger_type=trigger,source_type=source_type,source_id=source_id,title=title,
              description=description,severity=severity,owner_id=owner_id,status='Open',
              first_detected_at=now,last_detected_at=now,resolution_note=''))
            created+=1
        elif row.status!='Resolved':
            row.last_detected_at=now;row.description=description;updated+=1
    db.commit()
    return {'created':created,'refreshed':updated,'message':'On-demand evaluation; no background notifications or automatic closures'}

class AlertDecision(BaseModel):
    action:str
    note:str=Field(default='',max_length=2000)

@router.post('/alerts/{alert_id}/decision')
def decide_alert(pid:int,alert_id:int,body:AlertDecision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    row=db.query(PlanningAlert).filter_by(id=alert_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if row is None:raise HTTPException(404,'Alert not found')
    if not user.organization_admin and row.owner_id!=user.id:raise HTTPException(403,'Only assigned owner or organization administrator')
    if body.action=='acknowledge' and row.status=='Open':
        row.status='Acknowledged';row.acknowledged_by=user.id;row.acknowledged_at=datetime.now(timezone.utc)
    elif body.action=='resolve' and row.status in ('Open','Acknowledged'):
        if not body.note.strip():raise HTTPException(422,'Resolution reason required')
        row.status='Resolved';row.resolved_by=user.id;row.resolved_at=datetime.now(timezone.utc);row.resolution_note=body.note
    else:raise HTTPException(409,'Invalid transition')
    db.add(PlanningAlertEvent(alert_id=row.id,organization_id=user.organization_id,project_id=pid,
        actor_id=user.id,action=body.action,note=body.note,created_at=datetime.now(timezone.utc)))
    db.commit();db.refresh(row)
    return serialize(row)

@router.get('/alerts/{alert_id}/history')
def alert_history(pid:int,alert_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid)
    if not db.query(PlanningAlert.id).filter_by(id=alert_id,project_id=pid,organization_id=user.organization_id).first():
        raise HTTPException(404,'Alert not found')
    rows=db.query(PlanningAlertEvent).filter_by(alert_id=alert_id,organization_id=user.organization_id,project_id=pid).order_by(PlanningAlertEvent.id).all()
    return [{'action':e.action,'actor_id':e.actor_id,'note':e.note,'created_at':e.created_at} for e in rows]
