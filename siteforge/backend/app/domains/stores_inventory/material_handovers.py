"""Phase 5: traceable material dispatch and receipt; never mutates the stock ledger."""
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated, permitted
from app.domains.identity_projects.router import audit, commit
from app.domains.supply_chain import service
from app.domains.supply_chain.models import StockPosting, StockPostingLine
from .models import StoresMaterialHandover, StoresOutboundLotAllocation, StoresTransferIssueAllocation, StoresLotReservation, StoresMaterialRequest

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Material Handover'])

class DispatchIn(BaseModel):
    posting_line_id: int = Field(gt=0)
    handover_reference: str = Field(min_length=1, max_length=120)
    evidence: str = Field(min_length=3, max_length=4000)

class AcknowledgeIn(BaseModel):
    version: int = Field(ge=1)
    received_quantity: Decimal = Field(ge=0, decimal_places=3)
    damaged_quantity: Decimal = Field(ge=0, decimal_places=3)
    evidence: str = Field(min_length=3, max_length=4000)
    discrepancy_note: str = Field(default='', max_length=4000)

def _scope(db, user, pid, action):
    project = service._project(db, user, pid, action=None)
    permitted(db, user, project, action)
    return project

def _payload(record):
    return dict(id=record.id, posting_line_id=record.stock_posting_line_id,
        material_request_id=record.material_request_id, quantity=str(record.dispatched_quantity),
        received_quantity=str(record.received_quantity) if record.received_quantity is not None else None,
        damaged_quantity=str(record.damaged_quantity) if record.damaged_quantity is not None else None,
        status=record.status, handover_reference=record.handover_reference,
        dispatch_evidence=record.dispatch_evidence, acknowledgment_evidence=record.acknowledgment_evidence,
        discrepancy_note=record.discrepancy_note, dispatched_by=record.dispatched_by,
        acknowledged_by=record.acknowledged_by, version=record.version,
        resolution_note=record.resolution_note, resolved_by=record.resolved_by)

def classify_discrepancy(dispatched, received, damaged, note):
    dispatched, received, damaged = map(Decimal, (str(dispatched), str(received), str(damaged)))
    if not all(n.is_finite() for n in (dispatched, received, damaged)) or dispatched <= 0 or received < 0 or damaged < 0 or received > dispatched or damaged > received:
        raise HTTPException(422, 'Invalid handover quantities')
    discrepancy = (received != dispatched or damaged > 0)
    if discrepancy and len(note.strip()) < 3:
        raise HTTPException(422, 'Shortage or damage requires a discrepancy explanation')
    return 'Discrepancy' if discrepancy else 'Acknowledged'

def resolve_handover_source(grn_allocations, transfer_allocations, line_quantity):
    """Require exactly one fully attributed, demand-authorized issued lot."""
    grn, transfer = list(grn_allocations), list(transfer_allocations)
    if len(grn) + len(transfer) != 1:
        raise HTTPException(409, 'Handover requires exactly one lot provenance allocation')
    allocation = (grn or transfer)[0]
    if Decimal(str(allocation.quantity)) != Decimal(str(line_quantity)):
        raise HTTPException(409, 'Handover allocation must cover the entire issue line')
    if transfer:
        return 'Transfer', allocation
    return 'GRN', allocation

@router.post('/material-handovers', status_code=201)
def dispatch_material(pid: int, data: DispatchIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    line = db.execute(select(StockPostingLine).where(StockPostingLine.id == data.posting_line_id).with_for_update()).scalar_one_or_none()
    posting = db.get(StockPosting, line.posting_id) if line else None
    if not posting or posting.organization_id != u.organization_id or posting.project_id != pid or posting.kind != 'Issue' or posting.status != 'Posted':
        raise HTTPException(404, 'Posted material issue line not found')
    existing = db.execute(select(StoresMaterialHandover).where(StoresMaterialHandover.stock_posting_line_id == line.id)).scalar_one_or_none()
    if existing:
        if existing.handover_reference == data.handover_reference.strip() and existing.dispatch_evidence == data.evidence.strip():
            return _payload(existing)
        raise HTTPException(409, 'This issue line already has a handover')
    # Require explicit lot provenance and a request-linked reservation. Never invent a demand reference.
    allocations = db.execute(select(StoresOutboundLotAllocation).where(
        StoresOutboundLotAllocation.stock_posting_line_id == line.id,
        StoresOutboundLotAllocation.organization_id == u.organization_id,
        StoresOutboundLotAllocation.project_id == pid)).scalars().all()
    transfer_allocations = db.execute(select(StoresTransferIssueAllocation).where(
        StoresTransferIssueAllocation.stock_posting_line_id == line.id,
        StoresTransferIssueAllocation.organization_id == u.organization_id,
        StoresTransferIssueAllocation.project_id == pid)).scalars().all()
    source, allocation = resolve_handover_source(allocations, transfer_allocations, line.quantity)
    if source == 'GRN':
        import re
        match = re.fullmatch(r'Approved Stores request (\d+) / reservation (\d+)', allocation.reason)
        if not match:
            raise HTTPException(409, 'Issue lacks approved material request traceability')
        request_id = int(match.group(1))
    else:
        reservation = db.execute(select(StoresLotReservation).where(
            StoresLotReservation.id == allocation.reservation_id,
            StoresLotReservation.organization_id == u.organization_id,
            StoresLotReservation.project_id == pid,
            StoresLotReservation.transfer_destination_lot_id == allocation.transfer_destination_lot_id,
            StoresLotReservation.receipt_lot_id.is_(None))).scalar_one_or_none()
        if not reservation or not reservation.material_request_id:
            raise HTTPException(409, 'Transfer issue lacks an approved request-linked reservation')
        request_id = reservation.material_request_id
    request = db.get(StoresMaterialRequest, request_id)
    if not request or request.organization_id != u.organization_id or request.project_id != pid or request.status != 'Approved':
        raise HTTPException(409, 'Approved source request is not available')
    handover = StoresMaterialHandover(organization_id=u.organization_id, project_id=pid,
        stock_posting_line_id=line.id, material_request_id=request.id,
        dispatched_quantity=line.quantity, handover_reference=data.handover_reference.strip(),
        dispatch_evidence=data.evidence.strip(), dispatched_by=u.id)
    db.add(handover)
    db.flush()
    audit(db, u, 'dispatch_material_handover', 'stores_material_handovers', handover.id, project_id=pid)
    commit(db)
    return _payload(handover)

@router.post('/material-handovers/{handover_id}/acknowledge')
def acknowledge_material(pid: int, handover_id: int, data: AcknowledgeIn,
    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'stores.requests.create')
    record = db.execute(select(StoresMaterialHandover).where(
        StoresMaterialHandover.id == handover_id, StoresMaterialHandover.organization_id == u.organization_id,
        StoresMaterialHandover.project_id == pid).with_for_update()).scalar_one_or_none()
    if not record:
        raise HTTPException(404, 'Handover not found')
    if record.status != 'Awaiting Acknowledgment' or record.version != data.version:
        raise HTTPException(409, 'Handover is already handled or was updated')
    if record.dispatched_by == u.id:
        raise HTTPException(403, 'Dispatcher cannot acknowledge own handover')
    req = db.get(StoresMaterialRequest, record.material_request_id)
    if not req or req.project_id != pid or req.organization_id != u.organization_id:
        raise HTTPException(409, 'Source request is unavailable')
    # Restrict to the original requester, rather than any user with permission to create requests.
    if req.created_by != u.id:
        raise HTTPException(403, 'Only the original request owner may acknowledge')
    status = classify_discrepancy(record.dispatched_quantity, data.received_quantity,
                                  data.damaged_quantity, data.discrepancy_note)
    record.received_quantity = data.received_quantity
    record.damaged_quantity = data.damaged_quantity
    record.discrepancy_note = data.discrepancy_note.strip()
    record.acknowledgment_evidence = data.evidence.strip()
    record.acknowledged_by = u.id
    record.acknowledged_at = datetime.now(timezone.utc)
    record.status = status
    record.version += 1
    audit(db, u, 'acknowledge_material_handover', 'stores_material_handovers', record.id, project_id=pid)
    commit(db)
    return _payload(record)

@router.get('/material-handovers')
def list_handovers(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'stores.requests.view')
    rows = db.execute(select(StoresMaterialHandover).where(
        StoresMaterialHandover.organization_id == u.organization_id,
        StoresMaterialHandover.project_id == pid).order_by(StoresMaterialHandover.id.desc()).limit(300)).scalars().all()
    # Non-admin requesters only see their own demand-linked handovers.
    if not u.organization_admin:
        owned = {r.id for r in db.execute(select(StoresMaterialRequest).where(
            StoresMaterialRequest.project_id == pid, StoresMaterialRequest.organization_id == u.organization_id,
            StoresMaterialRequest.created_by == u.id)).scalars().all()}
        rows = [r for r in rows if r.material_request_id in owned]
    return {'records': [_payload(r) for r in rows]}

class ResolveDiscrepancyIn(BaseModel):
    version: int = Field(ge=1)
    decision: str = Field(pattern='^(Resolved|Escalated)$')
    evidence: str = Field(min_length=3, max_length=4000)

def validate_resolution(record, reviewer_id, data):
    if record.status != 'Discrepancy' or record.version != data.version:
        raise HTTPException(409, 'Discrepancy already handled or stale version')
    if record.dispatched_by == reviewer_id or record.acknowledged_by == reviewer_id:
        raise HTTPException(403, 'Independent Stores reviewer required')
    if not data.evidence.strip() or len(data.evidence.strip()) < 3:
        raise HTTPException(422, 'Resolution evidence required')

@router.post('/material-handovers/{handover_id}/resolve')
def resolve_material_discrepancy(pid: int, handover_id: int, data: ResolveDiscrepancyIn,
    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    record = db.execute(select(StoresMaterialHandover).where(
        StoresMaterialHandover.id == handover_id,
        StoresMaterialHandover.organization_id == u.organization_id,
        StoresMaterialHandover.project_id == pid).with_for_update()).scalar_one_or_none()
    if record is None:
        raise HTTPException(404, 'Handover not found')
    validate_resolution(record, u.id, data)
    record.status = data.decision
    record.resolution_note = data.evidence.strip()
    record.resolved_by = u.id
    record.resolved_at = datetime.now(timezone.utc)
    record.version += 1
    audit(db, u, 'review_material_handover_discrepancy', 'stores_material_handovers', record.id, project_id=pid)
    commit(db)
    return _payload(record)
