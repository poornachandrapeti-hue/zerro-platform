"""Material-specific Construction usage evidence with independent QA verification.

No stock, progress, billing or inventory posting happens here.
"""
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.router import audit, commit
from app.domains.supply_chain.models import StockPostingLine, StockPosting
from .material_handovers import _scope
from .models import StoresMaterialHandover, StoresMaterialRequest, StoresMaterialReturn, StoresConstructionMaterialUsage

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Construction Material Usage'])

class UsageIn(BaseModel):
    handover_id: int = Field(gt=0)
    usage_type: str = Field(pattern='^(Consumed|Installed)$')
    quantity: Decimal = Field(gt=0, decimal_places=3)
    evidence_key: str = Field(min_length=3, max_length=120)
    evidence: str = Field(min_length=5, max_length=4000)

class VerifyIn(BaseModel):
    version: int = Field(ge=1)
    decision: str = Field(pattern='^(Verified|Rejected)$')
    note: str = Field(min_length=5, max_length=4000)


def checked_quantity(value):
    n = Decimal(str(value))
    if not n.is_finite() or n < 0:
        raise HTTPException(409, 'Invalid source material quantity')
    return n


def enforce_usage_limit(issued, posted_return, prior_usage, proposed):
    """No material can be verified as used beyond posted issue minus posted returns."""
    issued, posted_return, prior_usage, proposed = map(checked_quantity, (issued, posted_return, prior_usage, proposed))
    if posted_return > issued or prior_usage + proposed > issued - posted_return:
        raise HTTPException(409, 'Material usage exceeds outstanding issued quantity')


def record_payload(r):
    return dict(id=r.id, handover_id=r.handover_id, work_package_id=r.work_package_id,
        item_id=r.item_id, unit=r.unit, quantity=str(r.quantity), usage_type=r.usage_type,
        evidence_key=r.evidence_key, evidence=r.evidence, status=r.status,
        submitted_by=r.submitted_by, verified_by=r.verified_by,
        verification_note=r.verification_note, version=r.version,
        created_at=r.created_at, verified_at=r.verified_at,
        stock_posted=False, progress_earned=False)


def _sources(db, pid, org, handover_id):
    handover = db.execute(select(StoresMaterialHandover).where(
        StoresMaterialHandover.id == handover_id,
        StoresMaterialHandover.project_id == pid,
        StoresMaterialHandover.organization_id == org).with_for_update()).scalar_one_or_none()
    if not handover:
        raise HTTPException(404, 'Handover not found')
    request = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.id == handover.material_request_id,
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.organization_id == org)).scalar_one_or_none()
    line = db.get(StockPostingLine, handover.stock_posting_line_id)
    posting = db.get(StockPosting, line.posting_id) if line else None
    if not request or not request.work_package_id or not line or not posting or posting.organization_id != org or posting.project_id != pid or posting.kind != 'Issue' or posting.status != 'Posted' or line.item_id != request.item_id or line.unit != request.base_unit:
        raise HTTPException(409, 'Posted issue and canonical requirement references must match')
    if handover.status not in ('Acknowledged', 'Resolved') or handover.received_quantity is None:
        raise HTTPException(409, 'Contractor handover must be acknowledged without open discrepancy')
    return handover, request, line


def _available(db, handover, line):
    returns = db.execute(select(StoresMaterialReturn).where(StoresMaterialReturn.handover_id == handover.id)).scalars().all()
    posted_return = sum((checked_quantity(r.received_quantity) for r in returns if r.stock_posting_id is not None), Decimal(0))
    all_usages = db.execute(select(StoresConstructionMaterialUsage).where(
        StoresConstructionMaterialUsage.handover_id == handover.id)).scalars().all()
    verified = sum((checked_quantity(r.quantity) for r in all_usages if r.status == 'Verified'), Decimal(0))
    pending = sum((checked_quantity(r.quantity) for r in all_usages if r.status == 'Pending QA'), Decimal(0))
    return posted_return, verified, pending


@router.post('/phase5/material-usages', status_code=201)
def submit_usage(pid: int, data: UsageIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'construction.edit')
    handover, request, line = _sources(db, pid, u.organization_id, data.handover_id)
    existing = db.execute(select(StoresConstructionMaterialUsage).where(
        StoresConstructionMaterialUsage.project_id == pid,
        StoresConstructionMaterialUsage.evidence_key == data.evidence_key)).scalar_one_or_none()
    if existing:
        if (existing.handover_id, existing.usage_type, checked_quantity(existing.quantity), existing.evidence) == (data.handover_id, data.usage_type, data.quantity, data.evidence.strip()):
            return record_payload(existing)
        raise HTTPException(409, 'Evidence key already used for different material usage')
    posted_return, verified, pending = _available(db, handover, line)
    enforce_usage_limit(line.quantity, posted_return, verified + pending, data.quantity)
    record = StoresConstructionMaterialUsage(organization_id=u.organization_id, project_id=pid,
        handover_id=handover.id, work_package_id=request.work_package_id,
        item_id=line.item_id, unit=line.unit, quantity=data.quantity,
        usage_type=data.usage_type, evidence_key=data.evidence_key,
        evidence=data.evidence.strip(), submitted_by=u.id, status='Pending QA')
    db.add(record)
    db.flush()
    audit(db, u, 'stores.construction_usage.submit', 'stores_construction_material_usage', record.id,
        project_id=pid, details={'handover_id': handover.id, 'work_package_id': request.work_package_id})
    commit(db)
    return record_payload(record)


@router.post('/phase5/material-usages/{usage_id}/verify')
def verify_usage(pid: int, usage_id: int, data: VerifyIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'quality.edit')
    # Same lock order as submission: source handover first, then usage.
    source = db.execute(select(StoresConstructionMaterialUsage.handover_id).where(
        StoresConstructionMaterialUsage.id == usage_id,
        StoresConstructionMaterialUsage.project_id == pid,
        StoresConstructionMaterialUsage.organization_id == u.organization_id)).scalar_one_or_none()
    if source is None:
        raise HTTPException(404, 'Material usage not found')
    handover, request, line = _sources(db, pid, u.organization_id, source)
    record = db.execute(select(StoresConstructionMaterialUsage).where(
        StoresConstructionMaterialUsage.id == usage_id,
        StoresConstructionMaterialUsage.project_id == pid,
        StoresConstructionMaterialUsage.organization_id == u.organization_id).with_for_update()).scalar_one_or_none()
    if not record or record.status != 'Pending QA' or record.version != data.version:
        raise HTTPException(409, 'Usage record already reviewed or stale')
    if record.submitted_by == u.id:
        raise HTTPException(403, 'Independent QA reviewer required')
    posted_return, verified, pending = _available(db, handover, line)
    if data.decision == 'Verified':
        enforce_usage_limit(line.quantity, posted_return, verified, record.quantity)
    record.status = data.decision
    record.verification_note = data.note.strip()
    record.verified_by = u.id
    record.verified_at = datetime.now(timezone.utc)
    record.version += 1
    audit(db, u, 'stores.construction_usage.verify', 'stores_construction_material_usage', record.id,
        project_id=pid, details={'decision': data.decision, 'work_package_id': record.work_package_id})
    commit(db)
    return record_payload(record)


@router.get('/phase5/material-usages/qa-queue')
def list_usage_qa_queue(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Independent QA review queue; never expose other submitters to a requester."""
    _scope(db, u, pid, 'quality.edit')
    rows = db.execute(select(StoresConstructionMaterialUsage).where(
        StoresConstructionMaterialUsage.project_id == pid,
        StoresConstructionMaterialUsage.organization_id == u.organization_id,
        StoresConstructionMaterialUsage.status == 'Pending QA',
        StoresConstructionMaterialUsage.submitted_by != u.id
    ).order_by(StoresConstructionMaterialUsage.id.desc()).limit(300)).scalars().all()
    return {'records': [record_payload(r) for r in rows],
            'coverage': 'Latest 300 pending QA material usage records',
            'inventory_verified': False, 'auto_progress_earned': False}


@router.get('/phase5/material-usages')
def list_usages(pid: int, work_package_id: int | None = None,
    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'stores.requests.view')
    query = select(StoresConstructionMaterialUsage).where(
        StoresConstructionMaterialUsage.organization_id == u.organization_id,
        StoresConstructionMaterialUsage.project_id == pid)
    if work_package_id is not None:
        if work_package_id <= 0:
            raise HTTPException(422, 'Invalid work package')
        query = query.where(StoresConstructionMaterialUsage.work_package_id == work_package_id)
    # Source visibility follows creator-scope for non-admin viewers.
    if not u.organization_admin:
        query = query.where(StoresConstructionMaterialUsage.submitted_by == u.id)
    rows = db.execute(query.order_by(StoresConstructionMaterialUsage.id.desc()).limit(300)).scalars().all()
    return {'records': [record_payload(r) for r in rows], 'coverage': 'Latest 300 explicitly evidenced records',
        'inventory_verified': False, 'auto_progress_earned': False}
