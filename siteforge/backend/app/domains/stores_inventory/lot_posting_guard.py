"""Fail-closed validation for a future atomic lot-qualified stock posting path.

This is not a stock posting service. Caller must hold database locks on the
warehouse/item balance, source lot and relevant active allocations, and must
write both the existing ledger posting and lot attribution in one transaction.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from datetime import date


@dataclass(frozen=True)
class LotIssueSnapshot:
    lot_id: int
    project_id: int
    warehouse_id: int
    item_id: int
    owner_company_id: int
    stock_unit: str
    posted_receipt_quantity: Decimal
    posted_issue_quantity: Decimal
    posted_return_quantity: Decimal
    qa_accepted_quantity: Decimal
    reserved_lot_quantity: Decimal
    expiry_date: date | None
    qa_current: bool
    condition: str
    posting_coverage_complete: bool
    legacy_balance_reconciled: bool


class LotPostingBlocked(ValueError):
    pass


def _qty(value):
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise LotPostingBlocked("Quantity is invalid") from exc
    if not quantity.is_finite() or quantity <= 0 or quantity.as_tuple().exponent < -3:
        raise LotPostingBlocked("Quantity must be positive with at most three decimal places")
    return quantity


def verify_issue(snapshot: LotIssueSnapshot, *, quantity, project_id, warehouse_id,
                 item_id, owner_company_id, stock_unit, today: date | None = None):
    """Pure guard; never returns authorization to write outside a locked transaction."""
    requested = _qty(quantity)
    if (snapshot.project_id, snapshot.warehouse_id, snapshot.item_id, snapshot.owner_company_id) != (
        project_id, warehouse_id, item_id, owner_company_id
    ):
        raise LotPostingBlocked("Lot project, warehouse, item or owner mismatch")
    if stock_unit != snapshot.stock_unit:
        raise LotPostingBlocked("Lot unit mismatch")
    if not snapshot.posting_coverage_complete or not snapshot.legacy_balance_reconciled:
        raise LotPostingBlocked("Legacy ledger and lot allocations have not been reconciled")
    if not snapshot.qa_current or snapshot.condition != "Serviceable":
        raise LotPostingBlocked("QA decision or physical condition does not permit issue")
    if snapshot.expiry_date and snapshot.expiry_date < (today or date.today()):
        raise LotPostingBlocked("Lot expired")
    receipts = Decimal(str(snapshot.posted_receipt_quantity))
    issues = Decimal(str(snapshot.posted_issue_quantity))
    returns = Decimal(str(snapshot.posted_return_quantity))
    accepted = Decimal(str(snapshot.qa_accepted_quantity))
    reserved = Decimal(str(snapshot.reserved_lot_quantity))
    if min(receipts, issues, returns, accepted, reserved) < 0:
        raise LotPostingBlocked("Negative quantity in lot snapshot")
    if issues > receipts or returns > issues or accepted < receipts:
        raise LotPostingBlocked("Lot movement or QA reconciliation failed")
    on_hand = receipts - issues + returns
    available = on_hand - reserved
    if available < requested:
        raise LotPostingBlocked("Insufficient unreserved lot quantity")
    return {"lot_id": snapshot.lot_id, "requested": requested,
            "on_hand": on_hand, "available_before_issue": available,
            "available_after_issue": available - requested}
