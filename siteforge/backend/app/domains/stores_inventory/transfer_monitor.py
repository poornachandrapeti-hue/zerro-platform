"""Read-only Phase 6 transfer custody monitor; not a physical inventory KPI."""
import hmac
from collections import Counter
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.config import settings
from app.domains.identity_projects.models import Project, User
from app.domains.identity_projects.security import authenticated
from .material_handovers import _scope
from .models import StoresTransfer

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Transfer Monitoring'])


def summarize_transfers(rows, *, as_of=None, overdue_hours=48):
    if overdue_hours < 1 or overdue_hours > 720:
        raise HTTPException(422, 'overdue_hours must be between 1 and 720')
    now = as_of or datetime.now(timezone.utc)
    counts = Counter()
    details = []
    for row in rows:
        status = row.status
        counts['total'] += 1
        counts['in_transit'] += (status == 'In Transit')
        counts['pending_approval'] += (status == 'Pending Approval')
        counts['open_discrepancy'] += (row.discrepancy_status in ('Open', 'Escalated'))
        counts['pending_custody_confirmation'] += (status in ('Received', 'Discrepancy') and row.custody_confirmed_by is None)
        created = row.created_at
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        # Created-at is a conservative proxy; dispatch timestamp isn't persisted yet.
        age_hours = max(0, (now - created).total_seconds() / 3600) if created else None
        overdue = status == 'In Transit' and age_hours is not None and age_hours >= overdue_hours
        counts['overdue_in_transit'] += overdue
        details.append({'id':row.id,'reference':row.reference,'source_project_id':row.project_id,
            'destination_project_id':row.destination_project_id or row.project_id,
            'source_warehouse_id':row.source_warehouse_id,'destination_warehouse_id':row.destination_warehouse_id,
            'item_id':row.item_id,'status':status,'discrepancy_status':row.discrepancy_status,
            'custody_confirmed':row.custody_confirmed_by is not None,'receipt_overdue_proxy':overdue,
            'age_hours_since_request':round(age_hours,1) if age_hours is not None else None,
            'inventory_posted':False})
    return {'as_of':now.isoformat(),'counts':dict(counts), 'records':details,
        'record_count':len(details),'coverage':'latest_500_source_project_transfers',
        'aging_basis':'request_created_at_proxy_not_dispatch_time',
        'physical_stock_readiness':'Unverified','inventory_verified':False,'read_only':True}


def _monitor(db, organization_id, pid, overdue_hours):
    rows = db.execute(select(StoresTransfer).where(StoresTransfer.organization_id == organization_id,
        StoresTransfer.project_id == pid).order_by(StoresTransfer.id.desc()).limit(500)).scalars().all()
    return summarize_transfers(rows, overdue_hours=overdue_hours)

@router.get('/material-transfers/monitor')
def transfer_monitor(pid:int, overdue_hours:int=48, u:User=Depends(authenticated), db:Session=Depends(get_db)):
    _scope(db,u,pid,'procurement.stock.edit')
    return _monitor(db,u.organization_id,pid,overdue_hours)

@router.get('/internal-command-center/transfer-monitor')
def command_center_transfer_monitor(pid:int, request:Request, overdue_hours:int=48, db:Session=Depends(get_db)):
    expected=settings.command_center_identity_service_key
    supplied=request.headers.get('X-ZerroR-Service-Key','')
    if not expected or not hmac.compare_digest(expected,supplied):
        raise HTTPException(403,'Command Center service authentication required')
    project=db.get(Project,pid)
    if project is None:
        raise HTTPException(404,'Project not found')
    result=_monitor(db,project.organization_id,pid,overdue_hours)
    return {**result,'organization_id':project.organization_id,'project_id':pid,
        'source':'zerrobuild.stores.transfer_custody'}
