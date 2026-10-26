"""Phase 5 consolidated custody overview. This is NOT a stock ledger or installation register."""
from datetime import datetime, timezone, timedelta
from fastapi import Query
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from .material_handovers import _scope
from .models import StoresMaterialHandover, StoresMaterialReturn, StoresMaterialRequest

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Phase 5 Operations'])


def build_operations_view(handovers, requests, returns, *, now=None, acknowledgment_overdue_hours=48):
    """Per-handover custody stages only; no summed quantities across different units."""
    now = now or datetime.now(timezone.utc)
    if not 1 <= acknowledgment_overdue_hours <= 720:
        raise ValueError("acknowledgment_overdue_hours must be 1..720")
    cutoff = now - timedelta(hours=acknowledgment_overdue_hours)
    request_map = {r.id: r for r in requests}
    return_map = {r.handover_id: r for r in returns}
    counts = {key: 0 for key in ('awaiting_acknowledgment', 'overdue_acknowledgments', 'discrepancies', 'escalated',
        'pending_stores_receipt', 'pending_qa', 'quarantined', 'rejected',
        'pending_bin_placement', 'pending_posting', 'ledger_posted_returns')}
    records = []
    for h in handovers:
        request = request_map.get(h.material_request_id)
        if request is None:
            continue
        ret = return_map.get(h.id)
        awaiting_ack = h.status == 'Awaiting Acknowledgment'
        dispatched_at = getattr(h, 'created_at', None)
        if dispatched_at is not None and dispatched_at.tzinfo is None:
            dispatched_at = dispatched_at.replace(tzinfo=timezone.utc)
        overdue_ack = bool(awaiting_ack and dispatched_at is not None and dispatched_at < cutoff)
        if awaiting_ack: counts['awaiting_acknowledgment'] += 1
        if overdue_ack: counts['overdue_acknowledgments'] += 1
        if h.status == 'Discrepancy': counts['discrepancies'] += 1
        if h.status == 'Escalated': counts['escalated'] += 1
        if ret:
            if ret.status == 'Submitted': counts['pending_stores_receipt'] += 1
            elif ret.status == 'Awaiting QA': counts['pending_qa'] += 1
            elif ret.status == 'QA Quarantined': counts['quarantined'] += 1
            elif ret.status == 'QA Rejected': counts['rejected'] += 1
            if ret.status == 'QA Accepted' and ret.stock_posting_id is None:
                if ret.return_location_id is None: counts['pending_bin_placement'] += 1
                else: counts['pending_posting'] += 1
            if ret.stock_posting_id is not None: counts['ledger_posted_returns'] += 1
        records.append({
            'handover_id': h.id, 'handover_reference': h.handover_reference,
            'material_request_id': h.material_request_id,
            'requirement_line_id': request.requirement_line_id,
            'work_package_id': request.work_package_id, 'planning_wbs_id': request.planning_wbs_id,
            'handover_status': h.status,
            'dispatched_at': dispatched_at.isoformat() if dispatched_at else None,
            'acknowledgment_overdue': overdue_ack, 'dispatched_quantity': str(h.dispatched_quantity),
            'contractor_received_quantity': str(h.received_quantity) if h.received_quantity is not None else None,
            'return_id': ret.id if ret else None, 'return_status': ret.status if ret else None,
            'return_requested_quantity': str(ret.requested_quantity) if ret else None,
            'return_received_quantity': str(ret.received_quantity) if ret and ret.received_quantity is not None else None,
            'return_qa_decision': ret.qa_decision if ret else None,
            'return_location_id': ret.return_location_id if ret else None,
            'return_stock_posting_id': ret.stock_posting_id if ret else None,
        })
    return {'counts': counts, 'records': records, 'record_count': len(records),
        'inventory_verified': False, 'construction_consumption_verified': False,
        'acknowledgment_overdue_hours': acknowledgment_overdue_hours,
        'coverage': 'Latest 300 handovers with source request links; legacy/unmapped movements excluded. Counts apply only to this window.',
        'note': 'Custody stages are not stock availability. Only a separately verified posted return may affect inventory; no cross-unit quantity totals.'}


@router.get('/phase5/operations-overview')
def operations_overview(pid: int, acknowledgment_overdue_hours: int = Query(48, ge=1, le=720),
    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'stores.requests.view')
    handovers = db.execute(select(StoresMaterialHandover).where(
        StoresMaterialHandover.project_id == pid,
        StoresMaterialHandover.organization_id == u.organization_id
    ).order_by(StoresMaterialHandover.id.desc()).limit(300)).scalars().all()
    ids = {h.material_request_id for h in handovers}
    requests = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.organization_id == u.organization_id,
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.id.in_(ids))).scalars().all() if ids else []
    if not u.organization_admin:
        owned = {r.id for r in requests if r.created_by == u.id}
        handovers = [h for h in handovers if h.material_request_id in owned]
        requests = [r for r in requests if r.id in owned]
    returns = db.execute(select(StoresMaterialReturn).where(
        StoresMaterialReturn.organization_id == u.organization_id,
        StoresMaterialReturn.project_id == pid,
        StoresMaterialReturn.handover_id.in_([h.id for h in handovers]))).scalars().all() if handovers else []
    result = build_operations_view(handovers, requests, returns, acknowledgment_overdue_hours=acknowledgment_overdue_hours)
    return {'as_of': datetime.now(timezone.utc).isoformat(), **result}
