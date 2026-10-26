"""Phase 6 warehouse-to-warehouse custody transfer (evidence only).

This router intentionally does not write StockPosting/StockBalance or transfer title.
Activation of physical transfers requires separately validated dual-ledger posting.
"""
from decimal import Decimal
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.identity_projects.models import User, Project, Company
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.router import audit, commit
from app.domains.supply_chain.models import Warehouse, ProcurementItem
from .material_handovers import _scope
from .models import StoresTransfer

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Transfers'])

class TransferIn(BaseModel):
    reference: str = Field(min_length=1, max_length=120)
    source_warehouse_id: int = Field(gt=0)
    destination_warehouse_id: int = Field(gt=0)
    destination_project_id: int | None = Field(default=None, gt=0)
    item_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    purpose: str = Field(min_length=3, max_length=4000)
    declared_owner_company_id: int | None = Field(default=None, gt=0)
    source_custodian_company_id: int | None = Field(default=None, gt=0)
    destination_custodian_company_id: int | None = Field(default=None, gt=0)

class CustodyConfirmationIn(BaseModel):
    version: int = Field(ge=1)
    evidence: str = Field(min_length=3, max_length=4000)

class DecisionIn(BaseModel):
    version: int = Field(ge=1)
    approve: bool
    evidence: str = Field(min_length=3, max_length=4000)

class DispatchIn(BaseModel):
    version: int = Field(ge=1)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    evidence: str = Field(min_length=3, max_length=4000)

class ResolveDiscrepancyIn(BaseModel):
    version: int = Field(ge=1)
    action: str
    evidence: str = Field(min_length=3, max_length=4000)

class DestinationAcceptIn(BaseModel):
    version: int = Field(ge=1)
    evidence: str = Field(min_length=3, max_length=4000)

class ReceiveIn(BaseModel):
    version: int = Field(ge=1)
    received_quantity: Decimal = Field(ge=0, decimal_places=3)
    damaged_quantity: Decimal = Field(ge=0, decimal_places=3)
    evidence: str = Field(min_length=3, max_length=4000)
    discrepancy_note: str = Field(default='', max_length=4000)


def valid_qty(*numbers):
    if not all(Decimal(str(n)).is_finite() for n in numbers):
        raise HTTPException(422, 'Transfer quantities must be finite')


def classify_receipt(dispatched, received, damaged, note):
    valid_qty(dispatched, received, damaged)
    d, r, b = map(lambda n: Decimal(str(n)), (dispatched, received, damaged))
    if d <= 0 or r < 0 or b < 0 or r > d or b > r:
        raise HTTPException(422, 'Invalid transfer receipt quantities')
    if (r < d or b > 0) and len(note.strip()) < 3:
        raise HTTPException(422, 'Shortage or damage requires an explanation')
    return 'Discrepancy' if (r < d or b > 0) else 'Received'


def payload(r):
    return dict(id=r.id, reference=r.reference, source_project_id=r.project_id, destination_project_id=r.destination_project_id or r.project_id,
        destination_accepted_by=r.destination_accepted_by, destination_acceptance_evidence=r.destination_acceptance_evidence,
        source_warehouse_id=r.source_warehouse_id,
        destination_warehouse_id=r.destination_warehouse_id, item_id=r.item_id,
        quantity=str(r.quantity), dispatched_quantity=str(r.dispatched_quantity) if r.dispatched_quantity is not None else None,
        received_quantity=str(r.received_quantity) if r.received_quantity is not None else None,
        damaged_quantity=str(r.damaged_quantity) if r.damaged_quantity is not None else None,
        purpose=r.purpose, status=r.status, version=r.version, created_by=r.created_by,
        approved_by=r.approved_by, dispatched_by=r.dispatched_by, received_by=r.received_by,
        approval_evidence=r.approval_evidence, dispatch_evidence=r.dispatch_evidence,
        receipt_evidence=r.receipt_evidence, discrepancy_note=r.discrepancy_note,
        discrepancy_status=r.discrepancy_status, discrepancy_resolution=r.discrepancy_resolution,
        discrepancy_resolved_by=r.discrepancy_resolved_by,
        declared_owner_company_id=r.declared_owner_company_id,
        source_custodian_company_id=r.source_custodian_company_id,
        destination_custodian_company_id=r.destination_custodian_company_id,
        custody_confirmed_by=r.custody_confirmed_by,
        custody_confirmation_evidence=r.custody_confirmation_evidence,
        custody_confirmed_at=r.custody_confirmed_at.isoformat() if r.custody_confirmed_at else None,
        ownership_verified=False, ownership_transferred=False,
        inventory_posted=False, physical_stock_readiness='Unverified')


def transfer_record(db, pid, u, tid, *, lock=False):
    q = select(StoresTransfer).where(StoresTransfer.id == tid,
        StoresTransfer.project_id == pid, StoresTransfer.organization_id == u.organization_id)
    r = db.execute(q.with_for_update() if lock else q).scalar_one_or_none()
    if r is None:
        raise HTTPException(404, 'Transfer not found')
    return r


def validate_warehouses(db, pid, destination_pid, org, src, dst):
    if src == dst:
        raise HTTPException(422, 'Source and destination warehouses must differ')
    rows = db.execute(select(Warehouse).where(Warehouse.id.in_([src, dst]),
        Warehouse.organization_id == org, Warehouse.active.is_(True))).scalars().all()
    matched = {w.id: w for w in rows}
    if (src not in matched or dst not in matched
            or matched[src].project_id != pid or matched[dst].project_id != destination_pid):
        raise HTTPException(422, 'Warehouses must be active and belong to their respective projects')

@router.post('/material-transfers', status_code=201)
def create_transfer(pid: int, data: TransferIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    valid_qty(data.quantity)
    destination_pid = data.destination_project_id or pid
    if destination_pid != pid:
        _scope(db, u, destination_pid, 'procurement.stock.edit')
        destination = db.execute(select(Project).where(Project.id == destination_pid,
            Project.organization_id == u.organization_id)).scalar_one_or_none()
        if destination is None:
            raise HTTPException(422, 'Destination project is not in source organization')
    validate_warehouses(db, pid, destination_pid, u.organization_id, data.source_warehouse_id, data.destination_warehouse_id)
    item = db.execute(select(ProcurementItem).where(ProcurementItem.id == data.item_id,
        ProcurementItem.organization_id == u.organization_id)).scalar_one_or_none()
    if item is None:
        raise HTTPException(422, 'Material item not found in organization')
    companies = (data.declared_owner_company_id, data.source_custodian_company_id,
                 data.destination_custodian_company_id)
    if any(x is not None for x in companies):
        if not all(x is not None for x in companies):
            raise HTTPException(422, 'Owner and both custodians must be declared together')
        rows = db.execute(select(Company.id).where(Company.organization_id == u.organization_id,
            Company.active.is_(True), Company.id.in_(companies))).scalars().all()
        if set(rows) != set(companies):
            raise HTTPException(422, 'Owner and custodians must be active companies in organization')
        if data.source_custodian_company_id == data.destination_custodian_company_id:
            raise HTTPException(422, 'A custody transfer requires distinct source and destination custodians')
    ref = data.reference.strip()
    if db.execute(select(StoresTransfer.id).where(StoresTransfer.project_id == pid,
        StoresTransfer.reference == ref)).first():
        raise HTTPException(409, 'Transfer reference already exists in project')
    row = StoresTransfer(organization_id=u.organization_id, project_id=pid,
        destination_project_id=destination_pid, reference=ref,
        declared_owner_company_id=data.declared_owner_company_id,
        source_custodian_company_id=data.source_custodian_company_id,
        destination_custodian_company_id=data.destination_custodian_company_id,
        source_warehouse_id=data.source_warehouse_id, destination_warehouse_id=data.destination_warehouse_id,
        item_id=data.item_id, quantity=data.quantity, purpose=data.purpose.strip(), status='Pending Approval', created_by=u.id)
    db.add(row); db.flush()
    audit(db, u, 'create_material_transfer', 'stores_transfers', row.id, project_id=pid)
    commit(db)
    return payload(row)

@router.get('/material-transfers')
def list_transfers(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    rows = db.execute(select(StoresTransfer).where(StoresTransfer.project_id == pid,
        StoresTransfer.organization_id == u.organization_id).order_by(StoresTransfer.id.desc()).limit(300)).scalars().all()
    return {'records': [payload(r) for r in rows], 'inventory_posted': False}

@router.get('/material-transfers/destination-inbox')
def destination_transfer_inbox(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    rows = db.execute(select(StoresTransfer).where(
        StoresTransfer.organization_id == u.organization_id,
        StoresTransfer.destination_project_id == pid,
        StoresTransfer.project_id != pid,
    ).order_by(StoresTransfer.id.desc()).limit(300)).scalars().all()
    return {'records': [payload(r) for r in rows], 'inventory_posted': False}

@router.post('/material-transfers/destination/{transfer_id}/accept')
def accept_destination_transfer(pid: int, transfer_id: int, data: DestinationAcceptIn,
                                u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    r = db.execute(select(StoresTransfer).where(
        StoresTransfer.id == transfer_id, StoresTransfer.organization_id == u.organization_id,
        StoresTransfer.destination_project_id == pid, StoresTransfer.project_id != pid
    ).with_for_update()).scalar_one_or_none()
    if r is None:
        raise HTTPException(404, 'Destination transfer not found')
    if r.status != 'In Transit' or r.version != data.version or r.destination_accepted_by is not None:
        raise HTTPException(409, 'In-transit transfer and current version required')
    if u.id in (r.created_by, r.approved_by, r.dispatched_by):
        raise HTTPException(403, 'Independent destination custodian required')
    r.destination_accepted_by = u.id
    r.destination_acceptance_evidence = data.evidence.strip()
    r.version += 1
    audit(db, u, 'accept_interproject_transfer_destination', 'stores_transfers', r.id, project_id=pid)
    commit(db)
    return payload(r)

@router.post('/material-transfers/destination/{transfer_id}/receive')
def receive_destination_transfer(pid: int, transfer_id: int, data: ReceiveIn,
                                 u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    r = db.execute(select(StoresTransfer).where(
        StoresTransfer.id == transfer_id, StoresTransfer.organization_id == u.organization_id,
        StoresTransfer.destination_project_id == pid, StoresTransfer.project_id != pid
    ).with_for_update()).scalar_one_or_none()
    if r is None:
        raise HTTPException(404, 'Destination transfer not found')
    if r.status != 'In Transit' or r.version != data.version or r.destination_accepted_by is None:
        raise HTTPException(409, 'Destination acceptance and current in-transit version required')
    if u.id in (r.created_by, r.approved_by, r.dispatched_by, r.destination_accepted_by):
        raise HTTPException(403, 'Independent destination receiving operator required')
    r.status = classify_receipt(r.dispatched_quantity, data.received_quantity, data.damaged_quantity, data.discrepancy_note)
    r.received_quantity = data.received_quantity
    r.damaged_quantity = data.damaged_quantity
    r.receipt_evidence = data.evidence.strip()
    r.discrepancy_note = data.discrepancy_note.strip()
    r.received_by = u.id
    r.discrepancy_status = 'Open' if r.status == 'Discrepancy' else 'Not Required'
    r.version += 1
    audit(db, u, 'receive_interproject_transfer_destination', 'stores_transfers', r.id, project_id=pid)
    commit(db)
    return payload(r)

@router.post('/material-transfers/{transfer_id}/decision')
def decide_transfer(pid: int, transfer_id: int, data: DecisionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    r = transfer_record(db, pid, u, transfer_id, lock=True)
    if r.status != 'Pending Approval' or r.version != data.version:
        raise HTTPException(409, 'Transfer is no longer awaiting approval or version is stale')
    if u.id == r.created_by:
        raise HTTPException(403, 'Transfer requester cannot approve own transfer')
    r.status = 'Approved' if data.approve else 'Rejected'
    r.approved_by = u.id; r.approval_evidence = data.evidence.strip(); r.version += 1
    audit(db, u, 'decide_material_transfer', 'stores_transfers', r.id, project_id=pid)
    commit(db)
    return payload(r)

@router.post('/material-transfers/{transfer_id}/dispatch')
def dispatch_transfer(pid: int, transfer_id: int, data: DispatchIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    r = transfer_record(db, pid, u, transfer_id, lock=True)
    if r.status != 'Approved' or r.version != data.version:
        raise HTTPException(409, 'Approved transfer and current version required')
    if u.id == r.created_by or u.id == r.approved_by:
        raise HTTPException(403, 'Independent dispatch operator required')
    valid_qty(data.quantity, r.quantity)
    if data.quantity > r.quantity:
        raise HTTPException(422, 'Dispatched quantity cannot exceed authorized quantity')
    r.dispatched_quantity = data.quantity; r.dispatched_by = u.id
    r.dispatch_evidence = data.evidence.strip(); r.status = 'In Transit'; r.version += 1
    audit(db, u, 'dispatch_material_transfer_custody', 'stores_transfers', r.id, project_id=pid)
    commit(db)
    return payload(r)

@router.post('/material-transfers/{transfer_id}/receive')
def receive_transfer(pid: int, transfer_id: int, data: ReceiveIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    r = transfer_record(db, pid, u, transfer_id, lock=True)
    if (r.destination_project_id or r.project_id) != pid:
        raise HTTPException(409, 'Inter-project receipt must use the destination project endpoint')
    if r.status != 'In Transit' or r.version != data.version:
        raise HTTPException(409, 'Dispatched transfer and current version required')
    if u.id in (r.created_by, r.approved_by, r.dispatched_by):
        raise HTTPException(403, 'Independent destination receiving operator required')
    r.status = classify_receipt(r.dispatched_quantity, data.received_quantity, data.damaged_quantity, data.discrepancy_note)
    r.received_quantity = data.received_quantity; r.damaged_quantity = data.damaged_quantity
    r.receipt_evidence = data.evidence.strip(); r.discrepancy_note = data.discrepancy_note.strip()
    r.received_by = u.id; r.discrepancy_status = 'Open' if r.status == 'Discrepancy' else 'Not Required'; r.version += 1
    audit(db, u, 'receive_material_transfer_custody', 'stores_transfers', r.id, project_id=pid)
    commit(db)
    return payload(r)

@router.post('/material-transfers/{transfer_id}/resolve-discrepancy')
def resolve_transfer_discrepancy(pid: int, transfer_id: int, data: ResolveDiscrepancyIn,
                                 u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    r = transfer_record(db, pid, u, transfer_id, lock=True)
    if r.status != 'Discrepancy' or r.discrepancy_status != 'Open' or r.version != data.version:
        raise HTTPException(409, 'Open discrepancy and current version required')
    if u.id in (r.created_by, r.approved_by, r.dispatched_by, r.received_by):
        raise HTTPException(403, 'Independent discrepancy reviewer required')
    if data.action not in ('Resolved', 'Escalated'):
        raise HTTPException(422, 'Action must be Resolved or Escalated')
    r.discrepancy_status = data.action
    r.discrepancy_resolution = data.evidence.strip()
    r.discrepancy_resolved_by = u.id
    r.version += 1
    audit(db, u, 'review_transfer_discrepancy', 'stores_transfers', r.id, project_id=pid)
    commit(db)
    return payload(r)


@router.post('/material-transfers/{transfer_id}/confirm-custody')
def confirm_transfer_custody(pid: int, transfer_id: int, data: CustodyConfirmationIn,
                             u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Confirm destination custody after recorded receipt; NEVER transfer legal title or stock."""
    _scope(db, u, pid, 'procurement.stock.edit')
    row = db.execute(select(StoresTransfer).where(
        StoresTransfer.id == transfer_id, StoresTransfer.organization_id == u.organization_id,
        StoresTransfer.destination_project_id == pid).with_for_update()).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, 'Destination transfer not found')
    if row.version != data.version or row.status not in ('Received', 'Discrepancy'):
        raise HTTPException(409, 'Current received transfer version required')
    if row.discrepancy_status in ('Open', 'Escalated'):
        raise HTTPException(409, 'Resolve receipt discrepancy before custody confirmation')
    if row.custody_confirmed_by is not None:
        raise HTTPException(409, 'Custody already confirmed')
    if row.destination_custodian_company_id is None:
        raise HTTPException(409, 'Custody company declarations are missing')
    if u.company_id != row.destination_custodian_company_id:
        raise HTTPException(403, 'Destination company custodian required')
    if u.id in (row.created_by, row.approved_by, row.dispatched_by, row.received_by):
        raise HTTPException(403, 'Independent custody confirmer required')
    row.custody_confirmed_by = u.id
    row.custody_confirmation_evidence = data.evidence.strip()
    row.custody_confirmed_at = datetime.now(timezone.utc)
    row.version += 1
    audit(db, u, 'confirm_material_transfer_destination_custody', 'stores_transfers', row.id, project_id=pid)
    commit(db)
    return payload(row)
