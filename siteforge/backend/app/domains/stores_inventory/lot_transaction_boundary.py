"""Transaction boundary for future lot-qualified stock movements.

This module deliberately does not post stock. It provides a database-backed,
fail-closed row-locking boundary for an atomic posting implementation. Call
within a single SQLAlchemy transaction; NEVER commit between guard and writes.
"""
from dataclasses import dataclass
from sqlalchemy import select
from .models import StoresReceiptLot
from app.domains.supply_chain.models import StockBalance, GoodsReceiptLine
from app.domains.supply_chain.stock import _receipt_item


class LotTransactionBlocked(ValueError):
    """Transaction cannot be safely prepared."""


@dataclass(frozen=True)
class LockedStockContext:
    lot_id: int
    balance_id: int
    project_id: int
    warehouse_id: int
    item_id: int
    unit: str


def lock_lot_stock(db, *, project_id: int, organization_id: int, warehouse_id: int,
                   item_id: int, lot_id: int) -> LockedStockContext:
    """Lock balance before lot in stable order. No inventory mutation occurs.

    Locks serialize competing writers *only if all stock writers cooperate*.
    An existing legacy writer that ignores this protocol is still unsafe.
    Caller must verify QA versions, allocation coverage, ownership, stock
    availability and idempotency under these locks before any atomic write.
    """
    if min(project_id, organization_id, warehouse_id, item_id, lot_id) <= 0:
        raise LotTransactionBlocked("Identifiers must be positive")
    balance = db.execute(
        select(StockBalance).where(
            StockBalance.organization_id == organization_id,
            StockBalance.project_id == project_id,
            StockBalance.warehouse_id == warehouse_id,
            StockBalance.item_id == item_id,
        ).with_for_update()
    ).scalar_one_or_none()
    if balance is None:
        raise LotTransactionBlocked("Stock balance missing; cannot post")
    lot = db.execute(
        select(StoresReceiptLot).where(
            StoresReceiptLot.id == lot_id,
            StoresReceiptLot.organization_id == organization_id,
            StoresReceiptLot.project_id == project_id,
            StoresReceiptLot.warehouse_id == warehouse_id,
        ).with_for_update()
    ).scalar_one_or_none()
    if lot is None:
        raise LotTransactionBlocked("Receipt lot missing or outside authorized stock scope")
    receipt_line = db.get(GoodsReceiptLine, lot.goods_receipt_line_id)
    if receipt_line is None:
        raise LotTransactionBlocked("Lot receipt-line provenance missing")
    receipt_item, receipt_unit = _receipt_item(db, receipt_line)
    if receipt_item is None or receipt_item.id != item_id or receipt_unit != balance.unit:
        raise LotTransactionBlocked("Lot source item or base unit does not match locked balance")
    if not balance.unit:
        raise LotTransactionBlocked("Stock base unit missing")
    return LockedStockContext(
        lot_id=lot.id, balance_id=balance.id, project_id=project_id,
        warehouse_id=warehouse_id, item_id=item_id, unit=balance.unit,
    )
