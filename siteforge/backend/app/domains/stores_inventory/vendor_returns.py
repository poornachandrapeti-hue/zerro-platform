"""Phase 6 supplier return and replacement evidence; stock posting is intentionally disabled."""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.router import audit, commit
from app.domains.supply_chain.models import Vendor, PurchaseOrder, PurchaseOrderLine, ProcurementItem, Warehouse
from .material_handovers import _scope
from .models import StoresVendorReturn

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Vendor Returns'])

class ReturnRequest(BaseModel):
    reference: str = Field(min_length=1, max_length=120)
    vendor_id: int = Field(gt=0)
    purchase_order_id: int = Field(gt=0)
    item_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    reason: str = Field(min_length=3, max_length=4000)

class Decision(BaseModel):
    version: int = Field(ge=1)
    approve: bool
    evidence: str = Field(min_length=3, max_length=4000)

class Evidence(BaseModel):
    version: int = Field(ge=1)
    evidence: str = Field(min_length=3, max_length=4000)

class Replacement(Evidence):
    replacement_reference: str = Field(min_length=1, max_length=120)


def view(r):
    return dict(id=r.id, reference=r.reference, vendor_id=r.vendor_id,
        purchase_order_id=r.purchase_order_id, item_id=r.item_id,
        warehouse_id=r.warehouse_id, quantity=str(r.quantity), reason=r.reason,
        status=r.status, version=r.version, created_by=r.created_by,
        approved_by=r.approved_by, dispatched_by=r.dispatched_by,
        vendor_ack_by=r.vendor_ack_by, replacement_recorded_by=r.replacement_recorded_by,
        replacement_reference=r.replacement_reference,
        approval_evidence=r.approval_evidence, dispatch_evidence=r.dispatch_evidence,
        vendor_ack_evidence=r.vendor_ack_evidence, replacement_evidence=r.replacement_evidence,
        inventory_posted=False, replacement_stock_verified=False)


def locked(db, pid, u, rid, version):
    r = db.execute(select(StoresVendorReturn).where(StoresVendorReturn.id == rid,
        StoresVendorReturn.project_id == pid,
        StoresVendorReturn.organization_id == u.organization_id).with_for_update()).scalar_one_or_none()
    if r is None:
        raise HTTPException(404, 'Vendor return not found')
    if r.version != version:
        raise HTTPException(409, 'Stale vendor return version')
    return r


def transition(db, u, pid, r, status, evidence_field, evidence, actor_field, action):
    setattr(r, evidence_field, evidence.strip())
    setattr(r, actor_field, u.id)
    r.status = status
    r.version += 1
    audit(db, u, action, 'stores_vendor_returns', r.id, project_id=pid)
    commit(db)
    return view(r)

@router.post('/vendor-returns', status_code=201)
def create_vendor_return(pid: int, data: ReturnRequest, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    if not data.quantity.is_finite():
        raise HTTPException(422, 'Quantity must be finite')
    vendor = db.execute(select(Vendor).where(Vendor.id == data.vendor_id,
        Vendor.organization_id == u.organization_id, Vendor.active.is_(True))).scalar_one_or_none()
    po = db.execute(select(PurchaseOrder).where(PurchaseOrder.id == data.purchase_order_id,
        PurchaseOrder.organization_id == u.organization_id, PurchaseOrder.project_id == pid,
        PurchaseOrder.vendor_id == data.vendor_id)).scalar_one_or_none()
    warehouse = db.execute(select(Warehouse).where(Warehouse.id == data.warehouse_id,
        Warehouse.organization_id == u.organization_id, Warehouse.project_id == pid,
        Warehouse.active.is_(True))).scalar_one_or_none()
    item = db.execute(select(ProcurementItem).where(ProcurementItem.id == data.item_id,
        ProcurementItem.organization_id == u.organization_id)).scalar_one_or_none()
    po_line = db.execute(select(PurchaseOrderLine.id).where(PurchaseOrderLine.purchase_order_id == data.purchase_order_id,
        PurchaseOrderLine.item_id == data.item_id)).first()
    if not all((vendor, po, warehouse, item, po_line)):
        raise HTTPException(422, 'Return must reference an active warehouse, vendor, PO and its material line')
    reference = data.reference.strip()
    if db.execute(select(StoresVendorReturn.id).where(StoresVendorReturn.project_id == pid,
        StoresVendorReturn.reference == reference)).first():
        raise HTTPException(409, 'Return reference already exists')
    r = StoresVendorReturn(organization_id=u.organization_id, project_id=pid,
        reference=reference, vendor_id=data.vendor_id, purchase_order_id=data.purchase_order_id,
        item_id=data.item_id, warehouse_id=data.warehouse_id, quantity=data.quantity,
        reason=data.reason.strip(), created_by=u.id)
    db.add(r)
    db.flush()
    audit(db, u, 'create', 'stores_vendor_returns', r.id, project_id=pid)
    commit(db)
    return view(r)

@router.get('/vendor-returns')
def list_vendor_returns(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    rows = db.execute(select(StoresVendorReturn).where(
        StoresVendorReturn.project_id == pid, StoresVendorReturn.organization_id == u.organization_id
    ).order_by(StoresVendorReturn.id.desc()).limit(500)).scalars().all()
    return [view(row) for row in rows]

@router.post('/vendor-returns/{rid}/decision')
def decide_vendor_return(pid: int, rid: int, data: Decision,
                         u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    r = locked(db, pid, u, rid, data.version)
    if r.status != 'Requested':
        raise HTTPException(409, 'Return request already decided')
    if r.created_by == u.id:
        raise HTTPException(403, 'Creator cannot approve own return')
    return transition(db, u, pid, r, 'Authorized' if data.approve else 'Rejected',
                      'approval_evidence', data.evidence, 'approved_by', 'vendor_return_decision')

@router.post('/vendor-returns/{rid}/dispatch')
def dispatch_vendor_return(pid: int, rid: int, data: Evidence,
                           u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    r = locked(db, pid, u, rid, data.version)
    if r.status != 'Authorized':
        raise HTTPException(409, 'Vendor return not authorized for dispatch')
    if r.approved_by == u.id:
        raise HTTPException(403, 'Approver cannot confirm own dispatch')
    return transition(db, u, pid, r, 'Dispatched', 'dispatch_evidence', data.evidence,
                      'dispatched_by', 'vendor_return_dispatch_evidence')

@router.post('/vendor-returns/{rid}/vendor-acknowledgment')
def acknowledge_vendor_return(pid: int, rid: int, data: Evidence,
                              u: User = Depends(authenticated), db: Session = Depends(get_db)):
    # Procurement staff can record supplier-supplied evidence; this is not vendor identity attestation.
    _scope(db, u, pid, 'procurement.stock.edit')
    r = locked(db, pid, u, rid, data.version)
    if r.status != 'Dispatched':
        raise HTTPException(409, 'Vendor return has not been dispatched')
    return transition(db, u, pid, r, 'Vendor Acknowledged', 'vendor_ack_evidence', data.evidence,
                      'vendor_ack_by', 'vendor_return_acknowledgment_recorded')

@router.post('/vendor-returns/{rid}/replacement')
def record_replacement(pid: int, rid: int, data: Replacement,
                       u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    r = locked(db, pid, u, rid, data.version)
    if r.status != 'Vendor Acknowledged':
        raise HTTPException(409, 'Supplier acknowledgment required')
    if r.vendor_ack_by == u.id:
        raise HTTPException(403, 'Acknowledgment recorder cannot independently verify replacement')
    r.replacement_reference = data.replacement_reference.strip()
    return transition(db, u, pid, r, 'Replacement Recorded', 'replacement_evidence', data.evidence,
                      'replacement_recorded_by', 'vendor_return_replacement_evidence')
