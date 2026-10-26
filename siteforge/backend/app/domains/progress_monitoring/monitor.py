"""Opt-in Progress scans integrated into the existing coordination worker.

No alert is delivered to an unverified project member. A configured scan owner
must retain unrestricted Progress manage permission for the scan to proceed.
"""
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from .alerts_models import ProgressAlertPolicy, ProgressAlertEvent
from .alert_rules import evaluate_progress_alerts
from .router import dashboard
from .reports_router import allowed
from app.domains.identity_projects.models import User
from app.domains.coordination.jobs import notify

SCAN_INTERVAL=timedelta(hours=1)

def due_for_scan(policy, now):
    if not policy.enabled:return False
    return policy.last_scanned_at is None or now - _aware(policy.last_scanned_at) >= SCAN_INTERVAL

def _aware(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

def authorized_recipients(db, policy):
    result=[]
    for uid in dict.fromkeys(policy.recipient_ids or []):
        user=db.get(User,uid)
        if not user or user.organization_id!=policy.organization_id:continue
        try:allowed(db,user,policy.project_id,'planning.view')
        except HTTPException:continue
        result.append(user)
    return result

def scan(db, now=None):
    now=now or datetime.now(timezone.utc)
    checked=0
    policies=db.query(ProgressAlertPolicy).filter_by(enabled=True).all()
    for policy in policies:
        if not due_for_scan(policy,now):continue
        owner=db.get(User,policy.updated_by)
        if not owner or owner.organization_id!=policy.organization_id:continue
        try:allowed(db,owner,policy.project_id,'planning.manage')
        except HTTPException:continue
        # Fail closed and roll back this project when the source is unavailable.
        try:
            data=dashboard(policy.project_id,None,None,None,owner,db)
            if data.get('visibility')!='project':continue
            warnings=evaluate_progress_alerts(data,float(policy.warning_pp),float(policy.critical_pp))
            recipients=authorized_recipients(db,policy)
            active=set()
            for warning in warnings:
                key=warning['fingerprint'];active.add(key)
                row=db.query(ProgressAlertEvent).filter_by(project_id=policy.project_id,organization_id=policy.organization_id,fingerprint=key).first()
                is_new=row is None
                if is_new:
                    row=ProgressAlertEvent(project_id=policy.project_id,organization_id=policy.organization_id,fingerprint=key,kind=warning['type'],severity=warning['severity'],message=warning['message'],state='Open',first_seen=now,last_seen=now)
                    db.add(row);db.flush()
                else:
                    row.last_seen=now;row.severity=warning['severity'];row.message=warning['message']
                if is_new:
                    for recipient in recipients:
                        notify(db,recipient,'Progress alert',row.message,f'progress:{row.id}:opened:{recipient.id}',policy.project_id,f'/projects/{policy.project_id}/progress')
                if row.state=='Open' and now-_aware(row.first_seen)>=timedelta(hours=policy.escalate_after_hours):
                    row.state='Escalated';row.escalated_at=now
                    for recipient in recipients:
                        notify(db,recipient,'Progress alert escalated',row.message,f'progress:{row.id}:escalated:{recipient.id}',policy.project_id,f'/projects/{policy.project_id}/progress')
            # Do not silently close old alerts: resolution requires an audited action.
            policy.last_scanned_at=now
            db.commit();checked+=1
        except Exception:
            db.rollback()
            continue
    return checked
