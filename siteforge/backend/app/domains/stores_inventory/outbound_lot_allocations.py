"""Historical outbound lot attribution. Never posts stock or grants QA release."""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated, permitted
from app.domains.identity_projects.router import audit, commit
from app.domains.supply_chain.models import StockPosting, StockPostingLine
from .router import receipt_access
from .models import StoresReceiptLot, StoresPostingLotAllocation, StoresOutboundLotAllocation

router = APIRouter(prefix="/api/projects/{pid}/stores", tags=["Stores & Inventory"])

class OutboundLotIn(BaseModel):
    posting_line_id: int
    receipt_lot_id: int
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    reason: str = Field(min_length=10, max_length=2000)

def validate_outbound_allocation(kind, quantity, line_qty, line_allocated, source_lot_qty, source_lot_allocated):
    q = Decimal(str(quantity))
    if kind not in ("Issue", "Return") or q <= 0:
        raise ValueError("Only positive posted Issue/Return quantities can be attributed")
    if q + Decimal(str(line_allocated)) > Decimal(str(line_qty)):
        raise ValueError("Outbound line allocation exceeds posted quantity")
    if q + Decimal(str(source_lot_allocated)) > Decimal(str(source_lot_qty)):
        raise ValueError("Allocation exceeds source-lot provenance capacity")

@router.post("/outbound-lot-allocations", status_code=201)
def create_outbound_lot_allocation(pid: int, data: OutboundLotIn, u: User = Depends(authenticated),
                                   db: Session = Depends(get_db)):
    project = receipt_access(db, u, pid, edit=True)
    permitted(db, u, project, "procurement.stock.edit")
    line = db.query(StockPostingLine).filter_by(id=data.posting_line_id).with_for_update().first()
    lot = db.query(StoresReceiptLot).filter_by(id=data.receipt_lot_id, project_id=pid,
             organization_id=u.organization_id).with_for_update().first()
    if not line or not lot:
        raise HTTPException(404, "Outbound posting line or lot not found")
    posting = db.query(StockPosting).filter_by(id=line.posting_id, project_id=pid,
              organization_id=u.organization_id, status="Posted").first()
    if not posting or posting.kind not in ("Issue", "Return") or posting.warehouse_id != lot.warehouse_id:
        raise HTTPException(409, "Expected same-project/warehouse posted Issue or Return")
    # A historical Issue may have several acceptable receipt lots. Require explicit documentary
    # provenance through an already reconciled source receipt acceptance posting.
    mapped = (db.query(StoresPostingLotAllocation, StockPostingLine, StockPosting)
              .join(StockPostingLine, StockPostingLine.id == StoresPostingLotAllocation.stock_posting_line_id)
              .join(StockPosting, StockPosting.id == StockPostingLine.posting_id)
              .filter(StoresPostingLotAllocation.receipt_lot_id == lot.id,
                      StoresPostingLotAllocation.project_id == pid,
                      StoresPostingLotAllocation.organization_id == u.organization_id,
                      StockPosting.status == "Posted", StockPosting.kind == "Accept",
                      StockPostingLine.item_id == line.item_id, StockPostingLine.unit == line.unit).all())
    if not mapped:
        raise HTTPException(409, "No validated receipt-acceptance lot provenance for this item/unit")
    source_total = sum((Decimal(str(m.quantity)) for m, _, _ in mapped), Decimal(0))
    existing_line = db.query(func.coalesce(func.sum(StoresOutboundLotAllocation.quantity), 0)).filter_by(
          stock_posting_line_id=line.id).scalar()
    # Returned quantities must be linked to an original posted Issue line, not inferred from item only.
    if posting.kind == "Return":
        issue_line = db.query(StockPostingLine).filter_by(id=line.source_line_id).first() if line.source_line_id else None
        issue = db.query(StockPosting).filter_by(id=issue_line.posting_id, project_id=pid,
                 organization_id=u.organization_id, kind="Issue", status="Posted").first() if issue_line else None
        if not issue or issue_line.item_id != line.item_id or issue_line.unit != line.unit:
            raise HTTPException(409, "Return must reference a posted matching Issue line")
        source_allocated = db.query(func.coalesce(func.sum(StoresOutboundLotAllocation.quantity), 0)).filter_by(
             stock_posting_line_id=issue_line.id, receipt_lot_id=lot.id).scalar()
        prior_returns = (db.query(func.coalesce(func.sum(StoresOutboundLotAllocation.quantity), 0))
            .join(StockPostingLine, StoresOutboundLotAllocation.stock_posting_line_id == StockPostingLine.id)
            .join(StockPosting, StockPosting.id == StockPostingLine.posting_id)
            .filter(StockPostingLine.source_line_id == issue_line.id,
                    StoresOutboundLotAllocation.receipt_lot_id == lot.id,
                    StockPosting.kind == "Return", StockPosting.status == "Posted").scalar())
        available_source = Decimal(str(source_allocated)) - Decimal(str(prior_returns))
        source_used = 0
    else:
        source_used = (db.query(func.coalesce(func.sum(StoresOutboundLotAllocation.quantity), 0))
            .join(StockPostingLine, StockPostingLine.id == StoresOutboundLotAllocation.stock_posting_line_id)
            .join(StockPosting, StockPosting.id == StockPostingLine.posting_id)
            .filter(StoresOutboundLotAllocation.receipt_lot_id == lot.id,
                    StoresOutboundLotAllocation.project_id == pid, StockPosting.kind == "Issue",
                    StockPosting.status == "Posted").scalar())
        available_source = source_total
    try:
        validate_outbound_allocation(posting.kind, data.quantity, line.quantity, existing_line,
                                     available_source, source_used)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    record = StoresOutboundLotAllocation(organization_id=u.organization_id, project_id=pid,
             stock_posting_line_id=line.id, receipt_lot_id=lot.id, quantity=data.quantity,
             reason=data.reason.strip(), created_by=u.id)
    db.add(record)
    try:
        db.flush()
        audit(db, u, "create", "stores_outbound_lot_allocations", record.id, project_id=pid)
        commit(db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Outbound posting line is already attributed to this lot")
    return {"id": record.id, "quantity": str(record.quantity), "lot_issue_enabled": False}

@router.get("/outbound-lot-allocations")
def list_outbound_lot_allocations(pid: int, receipt_lot_id: int | None = None,
                                  u: User = Depends(authenticated), db: Session = Depends(get_db)):
    receipt_access(db, u, pid)
    q = db.query(StoresOutboundLotAllocation).filter_by(project_id=pid, organization_id=u.organization_id)
    if receipt_lot_id is not None:
        q = q.filter_by(receipt_lot_id=receipt_lot_id)
    rows = q.order_by(StoresOutboundLotAllocation.id.desc()).limit(500).all()
    return {"records": [{"id": row.id, "posting_line_id": row.stock_posting_line_id,
            "receipt_lot_id": row.receipt_lot_id, "quantity": str(row.quantity),
            "reason": row.reason} for row in rows],
            "warning": "Historical provenance only; no physical balances or new lot issues are enabled."}
