"""Read-only, request-linked material custody versus independently QA-verified use.

Never treats issued stock as installed, nor returns awaiting posting as ledger returns.
"""
from collections import defaultdict
from decimal import Decimal
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.supply_chain.models import StockPosting, StockPostingLine
from .material_handovers import _scope
from .models import (StoresMaterialRequest, StoresMaterialHandover, StoresMaterialReturn,
                     StoresConstructionMaterialUsage)
from .return_work_package_trace import build_work_package_trace, load_transfer_trace_provenance, _quantity

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Phase 5 Material Balance'])


def combine_material_balance(trace_rows, usage_rows):
    """Join exact handover IDs only; fail closed on inconsistent or unmatched quantities."""
    by_handover = defaultdict(list)
    for usage in usage_rows:
        by_handover[usage.handover_id].append(usage)
    results = []
    seen = set()
    for trace in trace_rows:
        hid = trace['handover_id']
        if hid in seen:
            raise HTTPException(409, 'Duplicate source handover')
        seen.add(hid)
        issued = _quantity(trace['issued_quantity'])
        posted = _quantity(trace['ledger_posted_return_quantity'])
        outstanding = _quantity(trace['ledger_outstanding_quantity'])
        pending_return = _quantity(trace['pending_custody_return_quantity'])
        if posted + outstanding != issued or pending_return > outstanding:
            raise HTTPException(409, 'Inconsistent issue and return source quantities')
        verified_consumed = verified_installed = pending_consumed = pending_installed = Decimal(0)
        rejected = Decimal(0)
        for usage in by_handover.pop(hid, []):
            if usage.work_package_id != trace['work_package_id'] or usage.item_id != trace['item_id'] or usage.unit != trace['unit']:
                raise HTTPException(409, 'Material evidence conflicts with original issue')
            amount = _quantity(usage.quantity)
            if usage.usage_type not in ('Consumed', 'Installed') or usage.status not in ('Verified', 'Pending QA', 'Rejected'):
                raise HTTPException(409, 'Unrecognized material evidence state')
            if usage.status == 'Rejected':
                rejected += amount
            elif usage.status == 'Verified' and usage.usage_type == 'Consumed':
                verified_consumed += amount
            elif usage.status == 'Verified':
                verified_installed += amount
            elif usage.usage_type == 'Consumed':
                pending_consumed += amount
            else:
                pending_installed += amount
        verified_total = verified_consumed + verified_installed
        pending_total = pending_consumed + pending_installed
        if verified_total + pending_total > outstanding:
            raise HTTPException(409, 'Material usage exceeds ledger outstanding issue')
        results.append({**trace,
            'verified_consumed_quantity': str(verified_consumed),
            'verified_installed_quantity': str(verified_installed),
            'pending_qa_consumed_quantity': str(pending_consumed),
            'pending_qa_installed_quantity': str(pending_installed),
            'rejected_evidence_quantity': str(rejected),
            'unallocated_outstanding_quantity': str(outstanding - verified_total - pending_total),
            'physical_inventory_verified': False,
            'construction_installation_verified': verified_installed > 0,
            'coverage': 'Exact handover-linked evidence only; excludes unmapped legacy movements'})
    if by_handover:
        raise HTTPException(409, 'Material evidence references an unmapped or non-posted handover')
    return results


def _material_balance_for_scope(pid: int, work_package_id: int | None, u: User, db: Session, *, manager_view: bool):
    _scope(db, u, pid, 'construction.view' if manager_view else 'stores.requests.view')
    if work_package_id is not None and work_package_id <= 0:
        raise HTTPException(422, 'Invalid work package ID')
    rq = select(StoresMaterialRequest).where(
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.organization_id == u.organization_id)
    if work_package_id is not None:
        rq = rq.where(StoresMaterialRequest.work_package_id == work_package_id)
    requests = db.execute(rq).scalars().all()
    # Preserve the existing source endpoint's restricted requester visibility.
    if not manager_view and not u.organization_admin:
        requests = [r for r in requests if r.created_by == u.id]
    ids = [r.id for r in requests]
    if not ids:
        return {'records': [], 'coverage': 'Request-linked records only', 'inventory_verified': False,
                'as_of': datetime.now(timezone.utc)}
    handovers = db.execute(select(StoresMaterialHandover).where(
        StoresMaterialHandover.project_id == pid,
        StoresMaterialHandover.organization_id == u.organization_id,
        StoresMaterialHandover.material_request_id.in_(ids))).scalars().all()
    if not handovers:
        return {'records': [], 'coverage': 'Request-linked records only', 'inventory_verified': False,
                'as_of': datetime.now(timezone.utc)}
    hids = [h.id for h in handovers]
    returns = db.execute(select(StoresMaterialReturn).where(
        StoresMaterialReturn.project_id == pid, StoresMaterialReturn.organization_id == u.organization_id,
        StoresMaterialReturn.handover_id.in_(hids))).scalars().all()
    lines = db.execute(select(StockPostingLine).where(
        StockPostingLine.id.in_([h.stock_posting_line_id for h in handovers]))).scalars().all()
    posting_ids = {l.posting_id for l in lines} | {r.stock_posting_id for r in returns if r.stock_posting_id is not None}
    postings = db.execute(select(StockPosting).where(
        StockPosting.id.in_(posting_ids), StockPosting.organization_id == u.organization_id,
        StockPosting.project_id == pid)).scalars().all()
    provenance = load_transfer_trace_provenance(db, pid, u.organization_id, lines, returns)
    trace = build_work_package_trace(handovers, requests, returns, lines, postings, *provenance)
    usages = db.execute(select(StoresConstructionMaterialUsage).where(
        StoresConstructionMaterialUsage.project_id == pid,
        StoresConstructionMaterialUsage.organization_id == u.organization_id,
        StoresConstructionMaterialUsage.handover_id.in_(hids))).scalars().all()
    return {'records': combine_material_balance(trace, usages),
            'coverage': 'Only authorized request-linked handovers and source-matched, QA-reviewed usage; not an exhaustive inventory balance',
            'inventory_verified': False, 'as_of': datetime.now(timezone.utc)}


@router.get('/phase5/work-package-material-balance')
def work_package_material_balance(pid: int, work_package_id: int | None = None,
    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Original requester-facing balance; no widening of request visibility."""
    return _material_balance_for_scope(pid, work_package_id, u, db, manager_view=False)


@router.get('/phase5/construction-manager-material-balance')
def construction_manager_material_balance(pid: int, work_package_id: int | None = None,
    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Read-only cross-request work-package view for project-authorized Construction users."""
    return _material_balance_for_scope(pid, work_package_id, u, db, manager_view=True)
