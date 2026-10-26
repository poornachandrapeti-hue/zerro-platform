"""Phase 7 bounded operational workload monitor. Read-only; not inventory valuation."""
import hmac
from collections import Counter
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.domains.identity_projects.models import User, Project
from app.domains.identity_projects.security import authenticated
from .material_handovers import _scope
from .models import StoresPreservationPlan, StoresReceiptLot, StoresCycleCount, StoresStockAdjustmentRequest, StoresScrapCase
from .preservation import risk_status

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Phase 7 Monitoring'])
LIMIT = 500

def _workload(db, org: int, pid: int, *, today=None):
    today = today or date.today()
    plans = db.execute(select(StoresPreservationPlan, StoresReceiptLot).join(
        StoresReceiptLot, StoresReceiptLot.id == StoresPreservationPlan.receipt_lot_id).where(
        StoresPreservationPlan.organization_id == org, StoresPreservationPlan.project_id == pid,
        StoresReceiptLot.organization_id == org, StoresReceiptLot.project_id == pid
    ).order_by(StoresPreservationPlan.id.desc()).limit(LIMIT)).all()
    counts = db.execute(select(StoresCycleCount).where(
        StoresCycleCount.organization_id == org, StoresCycleCount.project_id == pid
    ).order_by(StoresCycleCount.id.desc()).limit(LIMIT)).scalars().all()
    adjustments = db.execute(select(StoresStockAdjustmentRequest).where(
        StoresStockAdjustmentRequest.organization_id == org, StoresStockAdjustmentRequest.project_id == pid
    ).order_by(StoresStockAdjustmentRequest.id.desc()).limit(LIMIT)).scalars().all()
    scraps = db.execute(select(StoresScrapCase).where(
        StoresScrapCase.organization_id == org, StoresScrapCase.project_id == pid
    ).order_by(StoresScrapCase.id.desc()).limit(LIMIT)).scalars().all()
    preservation = [dict(id=p.id, lot_id=p.receipt_lot_id, warehouse_id=l.warehouse_id,
        owner_id=p.responsible_user_id, status=risk_status(p.next_due_date,l.expiry_date,p.condition,today),
        next_due_date=p.next_due_date.isoformat()) for p,l in plans]
    return {
        'project_id': pid, 'organization_id': org,
        'as_of': datetime.now(timezone.utc).isoformat(),
        'coverage': f'Latest {LIMIT} records per workflow; not historical totals',
        'counts': {
            'preservation_needs_attention': sum(p['status'] in ('Expired','Quarantined','Overdue','Expiring Today','Due Today') for p in preservation),
            'preservation_uncovered_lots': None,
            'cycle_counts_open': sum(c.status not in ('Verified','Rejected','Cancelled') for c in counts),
            'adjustments_unresolved': sum(a.status not in ('Rejected','Cancelled') for a in adjustments),
            'scrap_cases_open': sum(s.status not in ('Rejected','Cancelled') for s in scraps),
            'scrap_disposal_evidence_recorded': sum(bool(s.disposal_reference) for s in scraps),
        },
        'preservation': preservation,
        'cycle_counts': [dict(id=c.id,reference=c.reference,warehouse_id=c.warehouse_id,status=c.status,
            scheduled_date=c.scheduled_date.isoformat()) for c in counts],
        'adjustments': [dict(id=a.id,reference=a.reference,count_id=a.count_id,status=a.status) for a in adjustments],
        'scrap_cases': [dict(id=s.id,reference=s.reference,receipt_lot_id=s.receipt_lot_id,
            classification=s.classification,status=s.status,disposal_recorded=bool(s.disposal_reference)) for s in scraps],
        'physical_stock_readiness': 'Unverified', 'stock_adjustment_posted': False,
        'stock_written_off': False, 'verified_inventory_variance': False,
        'limitations': [
            'Original receipt lots without preservation plans are not included in the preservation count.',
            'Cycle counts are not reconciled to an authoritative point-in-time lot book balance.',
            'Transfer-derived lot preservation coverage and complete issue holds are pending.',
            'No adjustment or scrap write-off is authorized by this monitor.',
        ],
    }

@router.get('/phase7/operations-monitor')
def operations_monitor(pid:int,u:User=Depends(authenticated),db:Session=Depends(get_db)):
    _scope(db,u,pid,'procurement.stock.view')
    return _workload(db,u.organization_id,pid)

@router.get('/internal-command-center/phase7-operations-monitor')
def command_center_phase7_monitor(pid:int,request:Request,db:Session=Depends(get_db)):
    expected = settings.command_center_identity_service_key
    supplied = request.headers.get('X-ZerroR-Service-Key','')
    if not expected or not hmac.compare_digest(expected,supplied):
        raise HTTPException(403,'Command Center service authentication required')
    project = db.get(Project,pid)
    if project is None:
        raise HTTPException(404,'Project not found')
    result = _workload(db,project.organization_id,pid)
    return {**result,'source':'zerrobuild.stores.phase7_operations'}
