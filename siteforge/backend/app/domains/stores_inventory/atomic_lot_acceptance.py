"""Atomic QA-authorized lot acceptance using the EXISTING supply-chain ledger.

Call inside a request-owned transaction and commit once only after this returns.
No issue, transfer, return or reservation rights are granted by this module.
"""
import os
from decimal import Decimal
from sqlalchemy import select, func
from fastapi import HTTPException
from app.domains.supply_chain.models import (
    GoodsReceipt, GoodsReceiptLine, StockPostingLine, StockPosting, StockBalance
)
from app.domains.supply_chain import stock
from app.domains.supply_chain.service import _amount, _event
from .models import StoresReceiptLot, StoresInspectionCase, StoresLotQAAttribution, StoresPostingLotAllocation


def _checked_qty(value):
    try:
        quantity = Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        raise HTTPException(422, "Invalid quantity")
    if not quantity.is_finite() or quantity <= 0 or quantity.as_tuple().exponent < -3:
        raise HTTPException(422, "Quantity must be positive with at most 3 decimal places")
    return quantity


def _assert_acceptance_balance_invariants(balance):
    """Fail closed rather than masking an already-corrupt aggregate balance.

    Acceptance adds to on-hand but must never silently repair an existing
    negative stock or a reserved balance exceeding physical stock.
    """
    on_hand = _amount(balance.on_hand)
    reserved = _amount(balance.reserved)
    if not on_hand.is_finite() or not reserved.is_finite() or on_hand < 0 or reserved < 0 or reserved > on_hand:
        raise HTTPException(409, 'Inconsistent aggregate stock balance before acceptance')


def accept_lot(db, user, project, *, lot_id, quantity, posting_number):
    """One flushable unit: legacy accept posting + its explicit lot attribution.

    Row locks serialize this endpoint against cooperating stock writers. All
    participating callers must commit/rollback the same transaction; never
    commit between ledger and lot allocation. Existing legacy writers must
    be disabled or routed through equivalent locking before broad rollout.
    """
    if os.getenv("STORES_LOT_WRITER_CUTOVER", "false").lower() != "true":
        raise HTTPException(503, "Disable legacy stock writers before enabling lot acceptance")
    stock._stores(db, user, project)
    amount = _checked_qty(quantity)
    if not posting_number.strip():
        raise HTTPException(422, "Posting number is required")
    from .posting_number_lock import lock_stock_posting_number
    lock_stock_posting_number(db, organization_id=user.organization_id,
                              project_id=project.id, number=posting_number)
    lot = db.execute(select(StoresReceiptLot).where(
        StoresReceiptLot.id == lot_id,
        StoresReceiptLot.organization_id == user.organization_id,
        StoresReceiptLot.project_id == project.id,
    ).with_for_update()).scalar_one_or_none()
    if lot is None:
        raise HTTPException(404, "Receipt lot not found")
    line = db.execute(select(GoodsReceiptLine).where(
        GoodsReceiptLine.id == lot.goods_receipt_line_id
    ).with_for_update()).scalar_one_or_none()
    receipt = db.get(GoodsReceipt, line.goods_receipt_id) if line else None
    if receipt is None or receipt.project_id != project.id or receipt.status != "Posted" or receipt.warehouse_id != lot.warehouse_id:
        raise HTTPException(409, "Lot must belong to a posted receipt in this warehouse")
    item, unit = stock._receipt_item(db, line)
    if not item or not unit:
        raise HTTPException(409, "Material master or stock unit is missing")
    case = db.execute(select(StoresInspectionCase).where(
        StoresInspectionCase.goods_receipt_line_id == line.id
    ).with_for_update()).scalar_one_or_none()
    if case is None or case.status not in ("Pending Inspection", "Disposition Recorded"):
        raise HTTPException(409, "Current QA approval is required")
    qa_lot_approved = db.execute(select(func.coalesce(func.sum(StoresLotQAAttribution.quantity), 0)).where(
        StoresLotQAAttribution.receipt_lot_id == lot.id,
        StoresLotQAAttribution.inspection_case_id == case.id,
        StoresLotQAAttribution.disposition == "Accepted",
        StoresLotQAAttribution.case_version_at_entry == case.version,
    )).scalar_one()
    previous_lot_acceptance = db.execute(select(func.coalesce(func.sum(StoresPostingLotAllocation.quantity), 0))
        .join(StockPostingLine, StoresPostingLotAllocation.stock_posting_line_id == StockPostingLine.id)
        .join(StockPosting, StockPostingLine.posting_id == StockPosting.id)
        .where(StoresPostingLotAllocation.receipt_lot_id == lot.id,
               StockPosting.kind == "Accept", StockPosting.status == "Posted")).scalar_one()
    if amount + _amount(previous_lot_acceptance) > min(_amount(lot.quantity), _amount(qa_lot_approved)):
        raise HTTPException(409, "Requested acceptance exceeds QA-cleared, unposted lot quantity")
    # Stock balance is locked after the receipt and lot; caller must use a
    # consistent lock order for all posting paths.
    balance = stock._lock_balance(db, user, project, lot.warehouse_id, item.id, unit)
    _assert_acceptance_balance_invariants(balance)
    already_accepted_line = stock.accepted_qty(db, line.id)
    if already_accepted_line + amount > min(_amount(line.quantity), stock._qa_accept_limit(db, line.id)):
        raise HTTPException(409, "Receipt-level QA clearance or unposted quantity exceeded")
    from app.domains.quality.material import quality_accepted
    if already_accepted_line + amount > _amount(quality_accepted(db, line.id)):
        raise HTTPException(409, "Quality module has not released this quantity")
    posting = stock._save(db, user, project, "Accept", posting_number,
        lot.warehouse_id, f"Lot-qualified acceptance {lot.lot_code}", "", receipt.id, None)
    posting_line = StockPostingLine(posting_id=posting.id, item_id=item.id,
        goods_receipt_line_id=line.id, quantity=amount, unit=unit)
    db.add(posting_line)
    db.flush()
    db.add(StoresPostingLotAllocation(organization_id=user.organization_id,
        project_id=project.id, stock_posting_line_id=posting_line.id,
        receipt_lot_id=lot.id, quantity=amount,
        reason="Atomic acceptance linked to current QA attribution", created_by=user.id))
    balance.on_hand = _amount(balance.on_hand) + amount
    balance.version += 1
    _event(db, user, project.id, "stock", posting.id, "accepted", receipt.number)
    db.flush()
    return {"posting_id": posting.id, "posting_line_id": posting_line.id,
            "receipt_lot_id": lot.id, "accepted_quantity": str(amount), "unit": unit}
