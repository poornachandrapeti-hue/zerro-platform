"""Manual legacy posting provenance; never mutates ledger or issues stock."""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated, permitted
from app.domains.identity_projects.router import audit, commit
from app.domains.supply_chain.models import StockPosting, StockPostingLine, GoodsReceiptLine, GoodsReceipt
from .router import receipt_access
from .models import StoresReceiptLot, StoresPostingLotAllocation

router = APIRouter(prefix="/api/projects/{pid}/stores", tags=["Stores & Inventory"])

class PostingLotIn(BaseModel):
    posting_line_id: int
    receipt_lot_id: int
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    reason: str = Field(min_length=10, max_length=2000)


def check_allocation(requested, posting_qty, allocated_posting, lot_qty, allocated_lot):
    requested = Decimal(str(requested))
    if requested <= 0 or requested + Decimal(str(allocated_posting)) > Decimal(str(posting_qty)):
        raise ValueError("Allocation exceeds existing posting line")
    if requested + Decimal(str(allocated_lot)) > Decimal(str(lot_qty)):
        raise ValueError("Allocation exceeds registered receipt lot")
    return True

@router.post("/posting-lot-allocations", status_code=201)
def create_posting_lot_allocation(pid: int, data: PostingLotIn,
    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = receipt_access(db, u, pid, edit=True)
    # A separate reconciler permission would be preferable to broad receipt-edit.
    permitted(db, u, project, "procurement.stock.edit")
    posting_line = db.query(StockPostingLine).filter_by(id=data.posting_line_id).with_for_update().first()
    lot = db.query(StoresReceiptLot).filter_by(id=data.receipt_lot_id, project_id=pid,
        organization_id=u.organization_id).with_for_update().first()
    if not posting_line or not lot:
        raise HTTPException(404, "Posting line or receipt lot not found")
    posting = db.query(StockPosting).filter_by(id=posting_line.posting_id, project_id=pid,
        organization_id=u.organization_id).first()
    receipt_line = db.query(GoodsReceiptLine).filter_by(id=lot.goods_receipt_line_id).first()
    receipt = db.query(GoodsReceipt).filter_by(id=receipt_line.goods_receipt_id, project_id=pid,
        organization_id=u.organization_id).first() if receipt_line else None
    if not posting or not receipt or posting.status != "Posted":
        raise HTTPException(409, "Requires a posted same-project provenance source")
    if (posting.kind != "Accept" or posting_line.goods_receipt_line_id != lot.goods_receipt_line_id
        or posting.goods_receipt_id != receipt.id or posting.warehouse_id != lot.warehouse_id):
        raise HTTPException(409, "Allocation must match a receipt acceptance posting and its GRN line")
    # Do not infer QA approval. This administrative mapping does not clear material for issue.
    line_total = db.query(func.coalesce(func.sum(StoresPostingLotAllocation.quantity), 0)).filter_by(
        stock_posting_line_id=posting_line.id).scalar()
    lot_total = db.query(func.coalesce(func.sum(StoresPostingLotAllocation.quantity), 0)).filter_by(
        receipt_lot_id=lot.id).scalar()
    try:
        check_allocation(data.quantity, posting_line.quantity, line_total, lot.quantity, lot_total)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    record = StoresPostingLotAllocation(organization_id=u.organization_id, project_id=pid,
        stock_posting_line_id=posting_line.id, receipt_lot_id=lot.id, quantity=data.quantity,
        reason=data.reason.strip(), created_by=u.id)
    db.add(record)
    try:
        db.flush()
        audit(db, u, "create", "stores_posting_lot_allocations", record.id, project_id=pid)
        commit(db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Posting line is already linked to that lot")
    return {"id": record.id, "lot_issue_enabled": False, "quantity": str(record.quantity)}

@router.get("/posting-lot-allocations")
def list_posting_lot_allocations(pid: int, receipt_lot_id: int | None = None,
    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    receipt_access(db, u, pid)
    q = db.query(StoresPostingLotAllocation).filter_by(project_id=pid, organization_id=u.organization_id)
    if receipt_lot_id is not None:
        q = q.filter_by(receipt_lot_id=receipt_lot_id)
    records = q.order_by(StoresPostingLotAllocation.id.desc()).limit(500).all()
    return {"records": [{"id": x.id, "posting_line_id": x.stock_posting_line_id,
         "receipt_lot_id": x.receipt_lot_id, "quantity": str(x.quantity),
         "reason": x.reason, "created_at": x.created_at.isoformat()} for x in records],
        "warning": "Provenance allocation only. QA release and lot-specific issues are NOT enabled."}
