"""Checkpoint 6: scoped read-only cross-module reference audit.

Not a stock ledger, inspection system, accounting posting, or billing certification.
External Zerro-R approvals require a separately authenticated integration contract.
"""
import hmac
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.config import settings
from app.domains.identity_projects.models import User, Project
from app.domains.identity_projects.security import authenticated
from .material_handovers import _scope
from .models import (StoresMaterialRequest, StoresMaterialHandover,
                     StoresMaterialReturn, StoresConstructionMaterialUsage,
                     StoresContractObligationLink)

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Phase 8 Cross-Module Audit'])


def cross_module_audit_rows(requests, handovers, returns, usages, contract_links):
    """Return exception evidence; never infer approvals, value, or quantities absent authority."""
    handovers_by_request = defaultdict(list)
    for h in handovers:
        handovers_by_request[h.material_request_id].append(h)
    returns_by_handover = defaultdict(list)
    for r in returns:
        returns_by_handover[r.handover_id].append(r)
    usages_by_handover = defaultdict(list)
    for usage in usages:
        usages_by_handover[usage.handover_id].append(usage)
    links_by_request = defaultdict(list)
    for link in contract_links:
        links_by_request[link.material_request_id].append(link)

    rows = []
    for req in requests:
        exceptions = []
        if not req.requirement_line_id:
            exceptions.append('MISSING_CANONICAL_REQUIREMENT')
        hs = handovers_by_request[req.id]
        if not hs:
            exceptions.append('NO_ISSUE_HANDOVER')
        if len(links_by_request[req.id]) > 1:
            exceptions.append('MULTIPLE_CONTRACT_REFERENCES_REVIEW')
        if not links_by_request[req.id]:
            exceptions.append('MISSING_CONTRACT_REFERENCE')
        details = []
        for h in hs:
            rs = returns_by_handover[h.id]
            us = usages_by_handover[h.id]
            local = []
            if not h.stock_posting_line_id:
                local.append('MISSING_ISSUE_POSTING_LINE')
            if any(u.item_id != req.item_id or u.work_package_id != req.work_package_id or u.unit != req.base_unit for u in us):
                local.append('USAGE_SCOPE_MISMATCH')
            if any(getattr(r, 'stock_posting_id', None) is None and r.status in ('Posted', 'Accepted') for r in rs):
                local.append('RETURN_POSTING_REVIEW_REQUIRED')
            if any(u.status != 'Verified' for u in us):
                local.append('USAGE_QA_REVIEW_REQUIRED')
            # A local Verified status is not evidence that external Zerro-R approved an inspection.
            if us:
                local.append('EXTERNAL_ZERROR_INSPECTION_NOT_ATTESTED')
            details.append({
                'handover_id': h.id, 'issue_posting_line_id': h.stock_posting_line_id,
                'handover_status': h.status,
                'return_ids': [r.id for r in rs], 'usage_ids': [u.id for u in us],
                'qa_verified_usage_ids': [u.id for u in us if u.status == 'Verified'],
                'exceptions': sorted(set(local)),
            })
            exceptions.extend(local)
        exceptions.extend(['FINANCE_COST_ATTRIBUTION_NOT_VERIFIED',
                           'BILLING_CERTIFICATION_NOT_VERIFIED'])
        rows.append({
            'material_request_id': req.id, 'request_status': req.status,
            'requirement_line_id': req.requirement_line_id,
            'work_package_id': req.work_package_id, 'planning_wbs_id': req.planning_wbs_id,
            'item_id': req.item_id, 'unit': req.base_unit,
            'contract_reference_ids': [x.id for x in links_by_request[req.id]],
            'handovers': details, 'exceptions': sorted(set(exceptions)),
            'review_state': 'Requires Review',
            'external_inspection_verified': False, 'finance_posting_created': False,
            'billing_certified': False, 'physical_stock_verified': False,
        })
    return rows


def _audit_window(db: Session, organization_id: int, pid: int, work_package_id: int | None, limit: int):
    query = select(StoresMaterialRequest).where(
        StoresMaterialRequest.organization_id == organization_id,
        StoresMaterialRequest.project_id == pid)
    if work_package_id is not None:
        query = query.where(StoresMaterialRequest.work_package_id == work_package_id)
    reqs = db.execute(query.order_by(StoresMaterialRequest.id.desc()).limit(limit)).scalars().all()
    ids = [r.id for r in reqs]
    hs = db.execute(select(StoresMaterialHandover).where(
        StoresMaterialHandover.organization_id == organization_id,
        StoresMaterialHandover.project_id == pid,
        StoresMaterialHandover.material_request_id.in_(ids))).scalars().all() if ids else []
    hids = [h.id for h in hs]
    rs = db.execute(select(StoresMaterialReturn).where(
        StoresMaterialReturn.organization_id == organization_id,
        StoresMaterialReturn.project_id == pid,
        StoresMaterialReturn.handover_id.in_(hids))).scalars().all() if hids else []
    us = db.execute(select(StoresConstructionMaterialUsage).where(
        StoresConstructionMaterialUsage.organization_id == organization_id,
        StoresConstructionMaterialUsage.project_id == pid,
        StoresConstructionMaterialUsage.handover_id.in_(hids))).scalars().all() if hids else []
    links = db.execute(select(StoresContractObligationLink).where(
        StoresContractObligationLink.organization_id == organization_id,
        StoresContractObligationLink.project_id == pid,
        StoresContractObligationLink.material_request_id.in_(ids))).scalars().all() if ids else []
    rows = cross_module_audit_rows(reqs, hs, rs, us, links)
    counts = Counter(exception for row in rows for exception in row['exceptions'])
    return {
        'records': rows, 'exception_counts': dict(counts),
        'as_of': datetime.now(timezone.utc),
        'coverage': f'Latest {limit} material requests; limited window, not a complete inventory/finance audit',
        'read_only': True, 'external_inspection_verified': False,
        'finance_posting_created': False, 'billing_certified': False,
        'note': 'No external Zerro-R attestation, authoritative valuation, earned progress, or certified billing established.',
    }


@router.get('/phase8/cross-module-audit')
def cross_module_audit(pid: int, work_package_id: int | None = None, limit: int = 200,
                       u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'stores.requests.review')
    _validate_window(work_package_id, limit)
    return _audit_window(db, u.organization_id, pid, work_package_id, limit)


def _validate_window(work_package_id, limit):
    if not 1 <= limit <= 500 or (work_package_id is not None and work_package_id <= 0):
        raise HTTPException(422, 'Invalid work-package filter or limit')


def command_center_exception_snapshot(db, organization_id, pid, work_package_id=None, limit=200):
    """Bounded snapshot; deterministic identity within a source project, never an event stream."""
    _validate_window(work_package_id, limit)
    audit = _audit_window(db, organization_id, pid, work_package_id, limit)
    return {
        'source': 'zerrobuild.stores.phase8_cross_module_audit',
        'schema_version': 1,
        'organization_id': organization_id,
        'project_id': pid,
        'work_package_id': work_package_id,
        'as_of': audit['as_of'],
        'coverage': audit['coverage'],
        'record_count': len(audit['records']),
        'exception_counts': audit['exception_counts'],
        'exception_records': [
            {'material_request_id': row['material_request_id'],
             'work_package_id': row['work_package_id'],
             'exception_codes': row['exceptions'],
             'review_state': row['review_state']}
            for row in audit['records'] if row['exceptions']
        ],
        'read_only': True,
        'external_inspection_verified': False,
        'financials_authority_verified': False,
        'billing_certified': False,
        'complete_history': False,
        'delivery_mode': 'poll_snapshot',
        'note': 'Monitoring only; no durable push, finance authority, stock adjustment or Zerro-R attestation.',
    }


@router.get('/internal-command-center/phase8-exception-snapshot')
def command_center_phase8_exception_snapshot(pid: int, request: Request,
                                            work_package_id: int | None = None, limit: int = 200,
                                            db: Session = Depends(get_db)):
    expected = settings.command_center_identity_service_key
    supplied = request.headers.get('X-ZerroR-Service-Key', '')
    if not expected or not hmac.compare_digest(expected, supplied):
        raise HTTPException(403, 'Command Center service authentication required')
    project = db.get(Project, pid)
    if project is None:
        raise HTTPException(404, 'Project not found')
    return command_center_exception_snapshot(db, project.organization_id, pid, work_package_id, limit)
