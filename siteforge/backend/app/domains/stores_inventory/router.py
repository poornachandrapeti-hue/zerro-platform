"""Stores Phase 1: secured warehouse visibility and warehouse location hierarchy.

Existing GRN/stock routes remain under Procurement until migration and reconciliation.
"""
from typing import Literal
from datetime import date
from decimal import Decimal, InvalidOperation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated, permitted, holds
from app.domains.identity_projects.router import audit, commit
from app.domains.supply_chain.models import Warehouse, PurchaseOrder, PurchaseOrderLine, Vendor, ProcurementItem
from app.domains.identity_projects.models import Company
from app.domains.supply_chain import service, receipts
from app.domains.supply_chain.schemas import ReceiptIn
from .models import StoreLocation, StoresDeliveryNotice, StoresExceptionalIntake, StoresEvidence
from app.domains.engineering_documents.models import StoredFile
from app.domains.engineering_documents.files import store_file, read_file

router = APIRouter(prefix="/api/projects/{pid}/stores", tags=["Stores & Inventory"])


class LocationIn(BaseModel):
    warehouse_id: int
    parent_id: int | None = None
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    location_type: Literal["Zone", "Rack", "Bin"] = "Bin"
    restrictions: str = Field(default="", max_length=2000)
    active: bool = True


class LocationUpdate(LocationIn):
    version: int = Field(ge=1)


def project_access(db, user, pid, edit=False):
    project = service._project(db, user, pid, action=None)
    # Reuse existing permissions initially; new stores-specific RBAC needs an explicit role migration.
    if edit:
        permitted(db, user, project, "procurement.master.edit")
    elif not (user.organization_admin or holds(db, user, project, "procurement.master.edit") or holds(db, user, project, "procurement.stock.edit")):
        raise HTTPException(403, "Stores access requires an authorized internal material role")
    return project


def ensure_warehouse(db, pid, wid):
    wh = db.get(Warehouse, wid)
    if wh is None or wh.project_id != pid:
        raise HTTPException(404, "Warehouse not found in this project")
    return wh


def present(row):
    return {key: getattr(row, key) for key in (
        "id", "project_id", "warehouse_id", "parent_id", "code", "name",
        "location_type", "restrictions", "active", "version")}


def ensure_parent(db, pid, warehouse_id, parent_id, own_id=None):
    if parent_id is None:
        return
    parent = db.get(StoreLocation, parent_id)
    if parent is None or parent.project_id != pid or parent.warehouse_id != warehouse_id:
        raise HTTPException(422, "Parent location must belong to the same warehouse and project")
    if own_id is not None:
        current = parent
        visited = set()
        while current is not None:
            if current.id == own_id or current.id in visited:
                raise HTTPException(422, "Circular location hierarchy is not permitted")
            visited.add(current.id)
            current = db.get(StoreLocation, current.parent_id) if current.parent_id else None


@router.get("/warehouses")
def warehouses(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project_access(db, u, pid)
    rows = db.query(Warehouse).filter_by(project_id=pid, organization_id=u.organization_id).order_by(Warehouse.code).all()
    return [service.warehouse_payload(db, row) for row in rows]


@router.get("/locations")
def locations(pid: int, warehouse_id: int | None = None, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project_access(db, u, pid)
    q = db.query(StoreLocation).filter_by(project_id=pid, organization_id=u.organization_id)
    if warehouse_id is not None:
        ensure_warehouse(db, pid, warehouse_id)
        q = q.filter_by(warehouse_id=warehouse_id)
    return [present(row) for row in q.order_by(StoreLocation.code).all()]


@router.post("/locations", status_code=201)
def create_location(pid: int, data: LocationIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project_access(db, u, pid, edit=True)
    ensure_warehouse(db, pid, data.warehouse_id)
    ensure_parent(db, pid, data.warehouse_id, data.parent_id)
    code = data.code.strip()
    if not code or not data.name.strip():
        raise HTTPException(422, "Code and name cannot be blank")
    row = StoreLocation(organization_id=u.organization_id, project_id=pid,
        warehouse_id=data.warehouse_id, parent_id=data.parent_id, code=code,
        code_key=code.casefold(), name=data.name.strip(), location_type=data.location_type,
        restrictions=data.restrictions, active=data.active, created_by=u.id)
    db.add(row)
    db.flush()
    audit(db, u, "create", "stores_locations", row.id, project_id=pid)
    commit(db)
    return present(row)


@router.put("/locations/{location_id}")
def update_location(pid: int, location_id: int, data: LocationUpdate, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project_access(db, u, pid, edit=True)
    row = db.get(StoreLocation, location_id)
    if row is None or row.project_id != pid or row.organization_id != u.organization_id:
        raise HTTPException(404, "Location not found")
    ensure_warehouse(db, pid, data.warehouse_id)
    ensure_parent(db, pid, data.warehouse_id, data.parent_id, row.id)
    if db.query(StoreLocation).filter_by(parent_id=row.id).first() and data.warehouse_id != row.warehouse_id:
        raise HTTPException(422, "Cannot move a location with children to another warehouse")
    code = data.code.strip()
    if not code or not data.name.strip():
        raise HTTPException(422, "Code and name cannot be blank")
    result = db.execute(update(StoreLocation).where(StoreLocation.id == location_id, StoreLocation.version == data.version)
        .values(warehouse_id=data.warehouse_id, parent_id=data.parent_id,
            code=code, code_key=code.casefold(), name=data.name.strip(),
            location_type=data.location_type, restrictions=data.restrictions,
            active=data.active, modified_by=u.id, version=data.version + 1))
    if result.rowcount != 1:
        raise HTTPException(409, "Location changed; reload before saving")
    audit(db, u, "update", "stores_locations", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return present(row)


# Phase 2 bridge: Stores is the operational entry point; the original Procurement
# GoodsReceipt and GoodsReceiptLine tables remain the ONLY receipt records.
# All writes execute the existing locked PO validation and notification service.
def receipt_access(db, user, pid, edit=False):
    project = service._project(db, user, pid, action=None)
    if edit:
        permitted(db, user, project, "procurement.receipt.edit")
    elif not (user.organization_admin or holds(db, user, project, "procurement.receipt.edit") or holds(db, user, project, "procurement.stock.edit")):
        raise HTTPException(403, "Receipt access requires an authorized stores role")
    return project


@router.get("/receipt-sources")
def stores_receipt_sources(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = receipt_access(db, u, pid)
    return receipts.sources(db, project)


@router.get("/receipts")
def stores_receipt_list(pid: int, status: str = "", u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = receipt_access(db, u, pid)
    return receipts.list_receipts(db, u, project, status)


@router.get("/receipts/{receipt_id}")
def stores_receipt_detail(pid: int, receipt_id: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = receipt_access(db, u, pid)
    row = db.get(receipts.GoodsReceipt, receipt_id)
    if not row or row.project_id != project.id or row.organization_id != u.organization_id:
        raise HTTPException(404, "Receipt not found")
    return receipts.payload(db, u, project, row)


@router.post("/receipts", status_code=201)
def stores_receipt_post(pid: int, data: ReceiptIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = receipt_access(db, u, pid, edit=True)
    # Existing service locks the PO and enforces remaining quantities.
    row = receipts.create_receipt(db, u, project, data)
    audit(db, u, "create", "goods_receipts", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return receipts.payload(db, u, project, row)


# Phase 2+: a notice is NOT a goods receipt and a reviewed exceptional intake is
# NOT an inventory posting. Separate identities avoid silently accepting stock.
class NoticeLineIn(BaseModel):
    purchase_order_line_id: int
    quantity: Decimal = Field(gt=0)


class NoticeIn(BaseModel):
    number: str = Field(min_length=1, max_length=80)
    purchase_order_id: int
    expected_date: date
    delivery_note: str = Field(default="", max_length=160)
    lines: list[NoticeLineIn] = Field(min_length=1)


def _validated_notice(db, pid, data, company_id=None):
    order = db.get(PurchaseOrder, data.purchase_order_id)
    if not order or order.project_id != pid or order.status not in receipts.OPEN:
        raise HTTPException(422, "Select an active issued PO belonging to this project")
    vendor = db.get(Vendor, order.vendor_id)
    if not vendor or (company_id is not None and vendor.company_id != company_id):
        raise HTTPException(403, "PO does not belong to your supplier company")
    seen = set()
    lines = []
    for line in data.lines:
        if line.purchase_order_line_id in seen:
            raise HTTPException(422, "Duplicate PO line")
        seen.add(line.purchase_order_line_id)
        po_line = db.get(PurchaseOrderLine, line.purchase_order_line_id)
        if not po_line or po_line.purchase_order_id != order.id:
            raise HTTPException(422, "All lines must belong to the selected PO")
        # An ASN predicts delivery; it does not book inventory nor change PO remaining.
        if line.quantity > po_line.quantity:
            raise HTTPException(422, "Notice quantity cannot exceed ordered line quantity")
        lines.append({"purchase_order_line_id": po_line.id, "quantity": str(line.quantity)})
    return order, vendor, lines


def _save_notice(db, u, pid, data, company_id=None):
    order, vendor, lines = _validated_notice(db, pid, data, company_id)
    number = data.number.strip()
    if not number:
        raise HTTPException(422, "Notice number is required")
    row = StoresDeliveryNotice(organization_id=u.organization_id, project_id=pid,
        purchase_order_id=order.id, vendor_company_id=vendor.company_id,
        number=number, number_key=number.casefold(), expected_date=data.expected_date,
        delivery_note=data.delivery_note.strip(), lines=lines, created_by=u.id)
    db.add(row)
    try:
        db.flush()
        audit(db, u, "create", "stores_delivery_notices", row.id, project_id=pid)
        commit(db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Delivery notice number already exists for this project")
    return _notice_payload(row)


def _notice_payload(row):
    return {"id": row.id, "number": row.number, "purchase_order_id": row.purchase_order_id,
        "vendor_company_id": row.vendor_company_id, "expected_date": str(row.expected_date),
        "delivery_note": row.delivery_note, "lines": row.lines, "status": row.status}


@router.get("/delivery-notices")
def delivery_notices(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    receipt_access(db, u, pid)
    return [_notice_payload(x) for x in db.query(StoresDeliveryNotice).filter_by(
        project_id=pid, organization_id=u.organization_id).order_by(StoresDeliveryNotice.id.desc()).all()]


@router.post("/delivery-notices", status_code=201)
def add_delivery_notice(pid: int, data: NoticeIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    receipt_access(db, u, pid, edit=True)
    return _save_notice(db, u, pid, data)


@router.get("/exceptional-intake-options")
def exceptional_intake_options(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Return authorized master references for intake drafting; never expose costs."""
    receipt_access(db, u, pid, edit=True)
    warehouses = db.query(Warehouse).filter_by(project_id=pid, organization_id=u.organization_id, active=True).order_by(Warehouse.code).all()
    companies = db.query(Company).filter_by(organization_id=u.organization_id, active=True).order_by(Company.name).all()
    items = db.query(ProcurementItem).filter_by(organization_id=u.organization_id, active=True).order_by(ProcurementItem.code).all()
    return {"warehouses": [{"id": x.id, "code": x.code, "name": x.name} for x in warehouses],
            "companies": [{"id": x.id, "name": x.name} for x in companies],
            "items": [{"id": x.id, "code": x.code, "description": x.description,
                       "base_unit": x.base_unit, "tracking_required": x.tracking_required} for x in items]}


class IntakeLineIn(BaseModel):
    item_id: int
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=20)
    batch_or_heat: str = Field(default="", max_length=120)


class ExceptionalIntakeIn(BaseModel):
    number: str = Field(min_length=1, max_length=80)
    intake_type: Literal["Free Issue", "Non PO", "Opening Stock"]
    warehouse_id: int
    owner_company_id: int
    source_company_id: int
    reason: str = Field(min_length=5, max_length=2000)
    lines: list[IntakeLineIn] = Field(min_length=1)


def _intake_payload(row):
    return {"id": row.id, "number": row.number, "intake_type": row.intake_type,
        "warehouse_id": row.warehouse_id, "owner_company_id": row.owner_company_id,
        "source_company_id": row.source_company_id, "reason": row.reason,
        "lines": row.lines, "status": row.status, "review_note": row.review_note}


@router.get("/exceptional-intakes")
def exceptional_intakes(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    receipt_access(db, u, pid)
    return [_intake_payload(x) for x in db.query(StoresExceptionalIntake).filter_by(
        project_id=pid, organization_id=u.organization_id).order_by(StoresExceptionalIntake.id.desc()).all()]


@router.post("/exceptional-intakes", status_code=201)
def add_exceptional_intake(pid: int, data: ExceptionalIntakeIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    receipt_access(db, u, pid, edit=True)
    warehouse = ensure_warehouse(db, pid, data.warehouse_id)
    if warehouse.organization_id != u.organization_id or not warehouse.active:
        raise HTTPException(422, "Active organization warehouse required")
    for company_id in (data.owner_company_id, data.source_company_id):
        company = db.get(Company, company_id)
        if not company or company.organization_id != u.organization_id or not company.active:
            raise HTTPException(422, "Invalid company reference")
    lines = []
    for line in data.lines:
        item = db.get(ProcurementItem, line.item_id)
        if not item or item.organization_id != u.organization_id or not item.active or item.base_unit != line.unit:
            raise HTTPException(422, "Item must be active and use its base stock unit")
        lines.append({"item_id": item.id, "quantity": str(line.quantity), "unit": line.unit,
                      "batch_or_heat": line.batch_or_heat.strip()})
    if data.intake_type == "Free Issue" and data.owner_company_id == data.source_company_id:
        # Ownership and supplying party may coincide; do not infer a transfer of title.
        pass
    number = data.number.strip()
    if not number:
        raise HTTPException(422, "Intake number is required")
    row = StoresExceptionalIntake(organization_id=u.organization_id, project_id=pid,
        number=number, number_key=number.casefold(), intake_type=data.intake_type,
        warehouse_id=warehouse.id, owner_company_id=data.owner_company_id,
        source_company_id=data.source_company_id, lines=lines, reason=data.reason.strip(), created_by=u.id)
    db.add(row)
    try:
        db.flush()
        audit(db, u, "create", "stores_exceptional_intakes", row.id, project_id=pid)
        commit(db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Intake number already exists for this project")
    return _intake_payload(row)


class IntakeReview(BaseModel):
    decision: Literal["Approve", "Reject"]
    note: str = Field(min_length=5, max_length=2000)


@router.post("/exceptional-intakes/{intake_id}/review")
def review_exceptional_intake(pid: int, intake_id: int, data: IntakeReview,
                              u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = service._project(db, u, pid, action=None)
    permitted(db, u, project, "procurement.master.edit")
    row = db.execute(select(StoresExceptionalIntake).where(
        StoresExceptionalIntake.id == intake_id, StoresExceptionalIntake.project_id == pid,
        StoresExceptionalIntake.organization_id == u.organization_id).with_for_update()).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Intake not found")
    if row.status != "Pending Review":
        raise HTTPException(409, "Intake already reviewed")
    if row.created_by == u.id:
        raise HTTPException(403, "Maker cannot approve or reject own intake")
    row.status = "Approved for Processing" if data.decision == "Approve" else "Rejected"
    row.reviewed_by = u.id
    row.review_note = data.note.strip()
    audit(db, u, "review", "stores_exceptional_intakes", row.id, project_id=pid)
    commit(db)
    return _intake_payload(row)


# Evidence links refer to existing private stored_files. Evidence never posts inventory.
def _evidence_parent(db, user, pid, kind, record_id, *, write=False, partner_company_id=None):
    if kind not in ("notice", "intake", "receipt"):
        raise HTTPException(422, "Unsupported evidence document type")
    model = {"notice": StoresDeliveryNotice, "intake": StoresExceptionalIntake, "receipt": receipts.GoodsReceipt}[kind]
    row = db.get(model, record_id)
    if not row or row.project_id != pid or row.organization_id != user.organization_id:
        raise HTTPException(404, "Stores document not found")
    if partner_company_id is not None:
        if kind != "notice" or row.vendor_company_id != partner_company_id:
            raise HTTPException(403, "This document is outside your supplier scope")
        if write and row.created_by != user.id:
            raise HTTPException(403, "Only the submitting supplier user may attach evidence")
    else:
        receipt_access(db, user, pid, edit=write)
    if write and kind == "receipt" and row.status == "Cancelled":
        raise HTTPException(409, "Cancelled receipt evidence cannot be changed")
    if write and kind == "intake" and row.status != "Pending Review":
        raise HTTPException(409, "Reviewed intake evidence cannot be changed")
    return row


def _evidence_payload(link, stored):
    return {"id": link.id, "document_type": link.document_type, "document_id": link.document_id,
            "file_name": stored.original_name, "content_type": stored.content_type,
            "size": stored.size, "sha256": stored.sha256, "created_by": link.created_by}


def list_stores_evidence(db, user, pid, kind, record_id, partner_company_id=None):
    _evidence_parent(db, user, pid, kind, record_id, partner_company_id=partner_company_id)
    links = db.query(StoresEvidence).filter_by(organization_id=user.organization_id,
        project_id=pid, document_type=kind, document_id=record_id).order_by(StoresEvidence.id).all()
    return [_evidence_payload(link, db.get(StoredFile, link.file_id)) for link in links]


async def add_stores_evidence(db, user, pid, kind, record_id, upload, partner_company_id=None):
    _evidence_parent(db, user, pid, kind, record_id, write=True, partner_company_id=partner_company_id)
    # Limit reads before allocation and rely on the shared storage service's allowlist/hash.
    from app.config import settings
    data = await upload.read(settings.max_upload_bytes + 1)
    stored = store_file(db, user, upload.filename or "evidence", upload.content_type or "", data)
    link = StoresEvidence(organization_id=user.organization_id, project_id=pid,
        document_type=kind, document_id=record_id, file_id=stored.id, created_by=user.id)
    db.add(link)
    db.flush()
    audit(db, user, "attach", "stores_evidence", link.id, project_id=pid)
    commit(db)
    return _evidence_payload(link, stored)


def download_stores_evidence(db, user, pid, kind, record_id, evidence_id, partner_company_id=None):
    _evidence_parent(db, user, pid, kind, record_id, partner_company_id=partner_company_id)
    link = db.query(StoresEvidence).filter_by(id=evidence_id, organization_id=user.organization_id,
        project_id=pid, document_type=kind, document_id=record_id).one_or_none()
    if link is None:
        raise HTTPException(404, "Evidence not found")
    stored = db.get(StoredFile, link.file_id)
    if not stored or stored.organization_id != user.organization_id or stored.scan_status != "available":
        raise HTTPException(404, "Evidence not available")
    return Response(read_file(stored), media_type=stored.content_type,
        headers={"Content-Disposition": f'attachment; filename="stores-evidence-{evidence_id}"', "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/{kind}/{record_id}/evidence")
def stores_evidence_list(pid: int, kind: str, record_id: int,
                         u: User = Depends(authenticated), db: Session = Depends(get_db)):
    return list_stores_evidence(db, u, pid, kind, record_id)


@router.post("/{kind}/{record_id}/evidence", status_code=201)
async def stores_evidence_upload(pid: int, kind: str, record_id: int, upload: UploadFile = File(...),
                                 u: User = Depends(authenticated), db: Session = Depends(get_db)):
    return await add_stores_evidence(db, u, pid, kind, record_id, upload)


@router.get("/{kind}/{record_id}/evidence/{evidence_id}/download")
def stores_evidence_download(pid: int, kind: str, record_id: int, evidence_id: int,
                             u: User = Depends(authenticated), db: Session = Depends(get_db)):
    return download_stores_evidence(db, u, pid, kind, record_id, evidence_id)


# Phase 3: QA disposition tracking is isolated from the legacy Procurement stock ledger.
# The inventory posting migration is deliberately not enabled by these endpoints.
from .models import StoresInspectionCase, StoresInspectionDecision
from app.domains.supply_chain.models import GoodsReceipt, GoodsReceiptLine, StockPosting, StockPostingLine, StockBalance


class InspectionDecisionIn(BaseModel):
    disposition: Literal["Accepted", "Rejected", "Quarantined"]
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    reason: str = Field(min_length=3, max_length=2000)
    idempotency_key: str = Field(min_length=8, max_length=120)
    expected_version: int = Field(ge=1)


def qa_access(db, user, pid, edit=False):
    project = service._project(db, user, pid, action=None)
    permitted(db, user, project, "quality.edit" if edit else "quality.view")
    return project


def inspection_payload(case):
    return dict(id=case.id, goods_receipt_line_id=case.goods_receipt_line_id,
        pending_qty=str(case.pending_qty), accepted_qty=str(case.accepted_qty),
        rejected_qty=str(case.rejected_qty), quarantined_qty=str(case.quarantined_qty),
        status=case.status, version=case.version,
        inventory_release_enabled=False)


@router.post("/inspection-cases/from-grn/{grn_id}", status_code=201)
def register_grn_inspections(pid: int, grn_id: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    qa_access(db, u, pid, edit=True)
    grn = db.get(GoodsReceipt, grn_id)
    if not grn or grn.project_id != pid or grn.organization_id != u.organization_id or grn.status != "Posted":
        raise HTTPException(404, "Posted GRN not found for this project")
    rows = db.query(GoodsReceiptLine).filter_by(goods_receipt_id=grn_id).all()
    if not rows:
        raise HTTPException(422, "Receipt has no lines")
    created = []
    for line in rows:
        case = db.query(StoresInspectionCase).filter_by(goods_receipt_line_id=line.id).first()
        if case is None:
            case = StoresInspectionCase(organization_id=u.organization_id, project_id=pid,
                goods_receipt_line_id=line.id, pending_qty=line.quantity, accepted_qty=0,
                rejected_qty=0, quarantined_qty=0, created_by=u.id)
            db.add(case)
            db.flush()
            audit(db, u, "create", "stores_inspection_cases", case.id, project_id=pid)
        created.append(inspection_payload(case))
    commit(db)
    return created


@router.get("/inspection-cases")
def inspection_cases(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    qa_access(db, u, pid)
    cases = db.query(StoresInspectionCase).filter_by(project_id=pid, organization_id=u.organization_id).order_by(StoresInspectionCase.id.desc()).limit(500).all()
    return [inspection_payload(row) for row in cases]


@router.post("/inspection-cases/{case_id}/decisions")
def record_inspection_decision(pid: int, case_id: int, data: InspectionDecisionIn,
    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    qa_access(db, u, pid, edit=True)
    case = db.query(StoresInspectionCase).filter_by(id=case_id, project_id=pid,
        organization_id=u.organization_id).with_for_update().first()
    if not case:
        raise HTTPException(404, "Inspection case not found")
    previous = db.query(StoresInspectionDecision).filter_by(case_id=case.id, idempotency_key=data.idempotency_key).first()
    if previous:
        if previous.disposition != data.disposition or previous.quantity != data.quantity or previous.reason != data.reason.strip():
            raise HTTPException(409, "Idempotency key already used with different details")
        return inspection_payload(case)
    # Revocation is a terminal QA hold. A later disposition must not silently
    # restore a previously revoked case to Pending/Disposition Recorded.
    # Only a separate authorized reinspection/release workflow may do that.
    if case.status == "Quality Revoked":
        raise HTTPException(409, "Revoked QA case requires a separate reinspection and release")
    if case.version != data.expected_version:
        raise HTTPException(409, "Inspection case changed; refresh before submitting")
    if data.quantity > case.pending_qty:
        raise HTTPException(422, "Disposition quantity exceeds remaining pending quantity")
    case.pending_qty -= data.quantity
    if data.disposition == "Accepted":
        case.accepted_qty += data.quantity
    elif data.disposition == "Rejected":
        case.rejected_qty += data.quantity
    else:
        case.quarantined_qty += data.quantity
    case.status = "Pending Inspection" if case.pending_qty > 0 else "Disposition Recorded"
    case.version += 1
    db.add(StoresInspectionDecision(case_id=case.id, disposition=data.disposition,
        quantity=data.quantity, reason=data.reason.strip(), idempotency_key=data.idempotency_key,
        actor_id=u.id))
    audit(db, u, "qa_disposition", "stores_inspection_cases", case.id,
          details={"disposition": data.disposition, "quantity": str(data.quantity)}, project_id=pid)
    commit(db)
    return inspection_payload(case)


class InspectionRevocationIn(BaseModel):
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    reason: str = Field(min_length=10, max_length=2000)
    idempotency_key: str = Field(min_length=8, max_length=120)
    expected_version: int = Field(ge=1)


@router.post("/inspection-cases/{case_id}/revoke")
def revoke_inspection_acceptance(pid: int, case_id: int, data: InspectionRevocationIn,
    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Revoke QA approval without rewriting historical stock movements.

    The coarse existing balance is now blocked for future allocation/issue.
    Previously issued material requires downstream construction impact review.
    """
    qa_access(db, u, pid, edit=True)
    case = db.query(StoresInspectionCase).filter_by(id=case_id, project_id=pid,
        organization_id=u.organization_id).with_for_update().first()
    if not case:
        raise HTTPException(404, "Inspection case not found")
    prior = db.query(StoresInspectionDecision).filter_by(
        case_id=case.id, idempotency_key=data.idempotency_key).first()
    if prior:
        if (prior.disposition != "Revoked" or prior.quantity != data.quantity
                or prior.reason != data.reason.strip()):
            raise HTTPException(409, "Idempotency key used with different details")
        return inspection_payload(case)
    # A QA revocation is terminal for this inspection case. Allow identical
    # retries above, but require a new authorized reinspection for new changes.
    if case.status == "Quality Revoked":
        raise HTTPException(409, "Revoked QA case requires a separate reinspection and release")
    if case.version != data.expected_version:
        raise HTTPException(409, "Inspection case changed; refresh before submitting")
    if data.quantity > case.accepted_qty:
        raise HTTPException(422, "Cannot revoke more than currently accepted")
    case.accepted_qty -= data.quantity
    case.quarantined_qty += data.quantity
    case.status = "Quality Revoked"
    case.version += 1
    db.add(StoresInspectionDecision(case_id=case.id, disposition="Revoked",
        quantity=data.quantity, reason=data.reason.strip(),
        idempotency_key=data.idempotency_key, actor_id=u.id))
    audit(db, u, "qa_revocation", "stores_inspection_cases", case.id,
          details={"quantity": str(data.quantity), "reason": data.reason.strip(),
                   "requires_construction_impact_review": True}, project_id=pid)
    commit(db)
    return {**inspection_payload(case), "requires_construction_impact_review": True,
            "warning": "Historical issued/installed stock is not automatically recalled; manual impact review required."}


@router.get("/legacy-stock-reconciliation")
def legacy_stock_reconciliation(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Visible provisional quantities; never assert they are QA-released or available to issue."""
    project_access(db, u, pid)
    balances = db.query(StockBalance).filter_by(project_id=pid, organization_id=u.organization_id).limit(500).all()
    return {"ledger_owner": "existing Procurement stock posting service",
        "qa_release_enforced": False,
        "warning": "Legacy on-hand totals are not QA-certified. Do not treat these as accepted available stock.",
        "rows": [{"warehouse_id": b.warehouse_id, "item_id": b.item_id, "unit": b.unit,
                  "legacy_on_hand": str(b.on_hand), "legacy_reserved": str(b.reserved)} for b in balances]}


# Lot provenance is registered by Internal Stores staff and is intentionally read-only
# after registration. It does not modify the legacy warehouse/item stock balance.
from .models import StoresReceiptLot
from sqlalchemy import func


class ReceiptLotIn(BaseModel):
    goods_receipt_line_id: int
    warehouse_id: int
    location_id: int | None = None
    owner_company_id: int
    custodian_company_id: int
    lot_code: str = Field(min_length=1, max_length=100)
    batch_number: str = Field(default="", max_length=100)
    heat_number: str = Field(default="", max_length=100)
    serial_number: str = Field(default="", max_length=100)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    expiry_date: date | None = None


def lot_payload(row):
    return {"id": row.id, "goods_receipt_line_id": row.goods_receipt_line_id,
            "warehouse_id": row.warehouse_id, "location_id": row.location_id,
            "owner_company_id": row.owner_company_id, "custodian_company_id": row.custodian_company_id,
            "lot_code": row.lot_code, "batch_number": row.batch_number,
            "heat_number": row.heat_number, "serial_number": row.serial_number,
            "quantity": str(row.quantity), "expiry_date": str(row.expiry_date) if row.expiry_date else None,
            "is_stock_balance": False, "eligible_to_issue": False}


@router.post("/receipt-lots", status_code=201)
def create_receipt_lot(pid: int, data: ReceiptLotIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    receipt_access(db, u, pid, edit=True)
    receipt_line = db.query(GoodsReceiptLine).filter_by(id=data.goods_receipt_line_id).with_for_update().first()
    receipt = db.get(GoodsReceipt, receipt_line.goods_receipt_id) if receipt_line else None
    if not receipt or receipt.project_id != pid or receipt.organization_id != u.organization_id or receipt.status != "Posted":
        raise HTTPException(404, "Posted receipt line not found")
    if receipt.warehouse_id != data.warehouse_id:
        raise HTTPException(422, "Lot warehouse must match its receipt")
    ensure_warehouse(db, pid, data.warehouse_id)
    if data.location_id is not None:
        location = db.get(StoreLocation, data.location_id)
        if not location or not location.active or location.project_id != pid or location.warehouse_id != data.warehouse_id:
            raise HTTPException(422, "Choose an active location in the receipt warehouse")
    for company_id in (data.owner_company_id, data.custodian_company_id):
        company = db.get(Company, company_id)
        if not company or company.organization_id != u.organization_id:
            raise HTTPException(422, "Company must belong to the organization")
    prior_qty = db.query(func.coalesce(func.sum(StoresReceiptLot.quantity), 0)).filter_by(
        goods_receipt_line_id=receipt_line.id).scalar()
    if Decimal(prior_qty) + data.quantity > Decimal(receipt_line.quantity):
        raise HTTPException(422, "Lot quantities cannot exceed the physical receipt line")
    lot_code = data.lot_code.strip()
    if not lot_code:
        raise HTTPException(422, "Lot code cannot be blank")
    row = StoresReceiptLot(organization_id=u.organization_id, project_id=pid,
        goods_receipt_line_id=receipt_line.id, warehouse_id=data.warehouse_id,
        location_id=data.location_id, owner_company_id=data.owner_company_id,
        custodian_company_id=data.custodian_company_id, lot_code=lot_code,
        batch_number=data.batch_number.strip(), heat_number=data.heat_number.strip(),
        serial_number=data.serial_number.strip(), quantity=data.quantity,
        expiry_date=data.expiry_date, created_by=u.id)
    db.add(row)
    try:
        db.flush()
        audit(db, u, "create", "stores_receipt_lots", row.id, project_id=pid)
        commit(db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Lot code already registered on receipt line")
    return lot_payload(row)


@router.get("/receipt-lots")
def list_receipt_lots(pid: int, receipt_line_id: int | None = None,
    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    receipt_access(db, u, pid)
    query = db.query(StoresReceiptLot).filter_by(project_id=pid, organization_id=u.organization_id)
    if receipt_line_id is not None:
        query = query.filter_by(goods_receipt_line_id=receipt_line_id)
    rows = query.order_by(StoresReceiptLot.id.desc()).limit(500).all()
    return {"records": [lot_payload(row) for row in rows],
            "warning": "Provenance only. Legacy balances are not lot-scoped; no lot is cleared for issue by this endpoint."}

# Phase 3: atomic receipt-lot acceptance, deliberately distinct from live issue.
class LotAcceptanceIn(BaseModel):
    lot_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    posting_number: str = Field(min_length=1, max_length=80)


@router.post('/receipt-lots/accept-atomically', status_code=201)
def accept_receipt_lot_atomically(pid: int, data: LotAcceptanceIn,
                                  u: User = Depends(authenticated), db: Session = Depends(get_db)):
    from .atomic_lot_acceptance import accept_lot
    project = receipt_access(db, u, pid, edit=True)
    result = accept_lot(db, u, project, lot_id=data.lot_id,
                        quantity=data.quantity, posting_number=data.posting_number)
    commit(db)
    return result

# Feature-gated: disabled by default, awaiting DB integration and legacy-writer cutover.
class AtomicLotIssueIn(BaseModel):
    lot_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    posting_number: str = Field(min_length=1, max_length=80)
    recipient: str = Field(min_length=1, max_length=200)
    reservation_id: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=2000)


@router.post('/receipt-lots/issue-atomically', status_code=201)
def issue_receipt_lot_atomically(pid: int, data: AtomicLotIssueIn,
                                  u: User = Depends(authenticated), db: Session = Depends(get_db)):
    from .atomic_lot_issue import issue_lot
    project = receipt_access(db, u, pid, edit=True)
    result = issue_lot(db, u, project, lot_id=data.lot_id, quantity=data.quantity,
                       posting_number=data.posting_number, recipient=data.recipient,
                       reason=data.reason, reservation_id=data.reservation_id)
    commit(db)
    return result


class LotReserveIn(BaseModel):
    work_package_id: int | None = Field(default=None, gt=0)
    planning_wbs_id: int | None = Field(default=None, gt=0)
    lot_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    request_key: str = Field(min_length=1, max_length=120)


@router.post('/receipt-lots/reserve', status_code=201)
def reserve_receipt_lot(pid: int, data: LotReserveIn,
                        u: User = Depends(authenticated), db: Session = Depends(get_db)):
    from .lot_reservations import reserve_lot
    project = receipt_access(db, u, pid, edit=True)
    result = reserve_lot(db, u, project, lot_id=data.lot_id, quantity=data.quantity,
                         request_key=data.request_key, work_package_id=data.work_package_id, planning_wbs_id=data.planning_wbs_id)
    commit(db)
    return result


class LotReservationReleaseIn(BaseModel):
    reservation_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    action_key: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=2000)


@router.post('/receipt-lots/reservations/release')
def release_receipt_lot_reservation(pid: int, data: LotReservationReleaseIn,
                                    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    from .lot_reservation_actions import release_reservation
    project = receipt_access(db, u, pid, edit=True)
    result = release_reservation(db, u, project, reservation_id=data.reservation_id,
        quantity=data.quantity, action_key=data.action_key, reason=data.reason)
    commit(db)
    return result


class LotReservationReassignIn(BaseModel):
    reservation_id: int = Field(gt=0)
    work_package_id: int | None = Field(default=None, gt=0)
    planning_wbs_id: int | None = Field(default=None, gt=0)
    action_key: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=2000)


@router.post('/receipt-lots/reservations/reassign')
def reassign_receipt_lot_reservation(pid: int, data: LotReservationReassignIn,
                                     u: User = Depends(authenticated), db: Session = Depends(get_db)):
    from .reservation_work_scope import reassign_reservation
    project = receipt_access(db, u, pid, edit=True)
    result = reassign_reservation(db, u, project, reservation_id=data.reservation_id,
        work_package_id=data.work_package_id, planning_wbs_id=data.planning_wbs_id,
        action_key=data.action_key, reason=data.reason)
    commit(db)
    return result
