"""Opt-in atomic single-lot direct issue. Disabled until legacy writers are gated.

The existing stock ledger remains the sole physical ledger. This handler only
accepts direct issue when there are no outstanding item reservations and when
ALL stock posting lines for the warehouse/item have explicit lot provenance.
The request transaction must be committed exactly once by its API caller.
"""
import os
from datetime import date
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select, func
from app.domains.supply_chain import stock
from app.domains.supply_chain.models import StockPosting, StockPostingLine, StockBalance, GoodsReceiptLine
from app.domains.supply_chain.service import _amount, _event
from app.domains.quality.findings import issue_blocked
from .models import (StoresReceiptLot, StoresInspectionCase, StoresLotQAAttribution,
                     StoresPostingLotAllocation, StoresOutboundLotAllocation, StoresLotReservation)
from .atomic_lot_acceptance import _checked_qty


def _posting_quantities(db, lot_id, kind, outbound=False):
    allocation = StoresOutboundLotAllocation if outbound else StoresPostingLotAllocation
    return _amount(db.execute(
        select(func.coalesce(func.sum(allocation.quantity), 0))
        .join(StockPostingLine, allocation.stock_posting_line_id == StockPostingLine.id)
        .join(StockPosting, StockPostingLine.posting_id == StockPosting.id)
        .where(allocation.receipt_lot_id == lot_id,
               StockPosting.kind == kind, StockPosting.status == 'Posted')
    ).scalar_one())


def _require_full_coverage(db, project, warehouse_id, item_id):
    """Fail closed if ANY posted relevant line is not fully attributed."""
    # Phase 6 destination credits are quarantined until transfer-derived lot
    # allocations are supported by BOTH reservation and issue services. The
    # warehouse aggregate includes these credits, so legacy GRN-lot availability
    # checks must not mistake them for QA-cleared receipt-lot stock.
    incoming_transfer = db.execute(
        select(StockPostingLine.id)
        .join(StockPosting, StockPosting.id == StockPostingLine.posting_id)
        .where(StockPosting.project_id == project.id,
               StockPosting.warehouse_id == warehouse_id,
               StockPosting.status == 'Posted',
               StockPosting.kind == 'TransferIn',
               StockPostingLine.item_id == item_id)
        .limit(1)
    ).scalar_one_or_none()
    if incoming_transfer is not None:
        raise HTTPException(409,
            'Transfer-derived stock is quarantined; GRN-lot reservations and issues are blocked until transfer-lot allocation is implemented')
    lines = db.execute(
        select(StockPostingLine, StockPosting.kind)
        .join(StockPosting, StockPosting.id == StockPostingLine.posting_id)
        .where(StockPosting.project_id == project.id,
               StockPosting.warehouse_id == warehouse_id,
               StockPosting.status == 'Posted',
               StockPosting.kind.in_(['Accept', 'Issue', 'Return']),
               StockPostingLine.item_id == item_id)
        .with_for_update(of=StockPostingLine)
    ).all()
    for line, kind in lines:
        allocation = StoresPostingLotAllocation if kind == 'Accept' else StoresOutboundLotAllocation
        attributed = db.execute(select(func.coalesce(func.sum(allocation.quantity), 0))
                                .where(allocation.stock_posting_line_id == line.id)).scalar_one()
        if _amount(attributed) != _amount(line.quantity):
            raise HTTPException(409, 'Posted material contains unattributed legacy movements')


def _assert_issue_balance_invariants(balance, amount, consumes_reservation):
    """Reject corrupt aggregate state before any reservation or stock decrement.

    The balance must remain physically consistent. A reservation-backed issue
    requires at least the issued quantity in the aggregate reserved column;
    otherwise its consumption would silently create negative reservations.
    """
    on_hand = _amount(balance.on_hand)
    reserved = _amount(balance.reserved)
    if on_hand < 0 or reserved < 0 or reserved > on_hand:
        raise HTTPException(409, "Inconsistent aggregate stock balance")
    if amount > on_hand:
        raise HTTPException(409, "Insufficient physical stock for issue")
    if consumes_reservation and reserved < amount:
        raise HTTPException(409, "Aggregate reservation balance cannot cover issue")


def issue_lot(db, user, project, *, lot_id, quantity, posting_number, recipient, reason, reservation_id=None):
    # Explicit rollout gate: enable ONLY after all legacy stock writers are
    # routed through the same locks and live PostgreSQL concurrency tests pass.
    if os.getenv('STORES_ATOMIC_LOT_ISSUE_ENABLED', 'false').lower() != 'true':
        raise HTTPException(503, 'Atomic lot issuing is not enabled for this deployment')
    if os.getenv("STORES_LOT_WRITER_CUTOVER", "false").lower() != "true":
        raise HTTPException(503, "Disable legacy stock writers before enabling lot issue")
    stock._stores(db, user, project)
    if reservation_id is None:
        raise HTTPException(409, "Physical issue requires an approved request-linked lot reservation")
    amount = _checked_qty(quantity)
    if not posting_number.strip() or not recipient.strip() or not reason.strip():
        raise HTTPException(422, 'Posting number, recipient and reason are required')
    from .posting_number_lock import lock_stock_posting_number
    lock_stock_posting_number(db, organization_id=user.organization_id,
                              project_id=project.id, number=posting_number)
    lot = db.execute(select(StoresReceiptLot).where(
        StoresReceiptLot.id == lot_id,
        StoresReceiptLot.organization_id == user.organization_id,
        StoresReceiptLot.project_id == project.id).with_for_update()).scalar_one_or_none()
    if lot is None:
        raise HTTPException(404, 'Lot not found')
    if lot.expiry_date and lot.expiry_date < date.today():
        raise HTTPException(409, 'Expired lot cannot be issued')
    from .preservation import require_preservation_clear
    require_preservation_clear(db, lot_id=lot.id, project_id=project.id,
                               organization_id=user.organization_id)
    line = db.get(GoodsReceiptLine, lot.goods_receipt_line_id)
    if not line:
        raise HTTPException(409, 'Source receipt line not found')
    item, unit = stock._receipt_item(db, line)
    if not item or not unit:
        raise HTTPException(409, 'Source material/unit unavailable')
    if issue_blocked(db, project.id, item.id):
        raise HTTPException(409, 'Quality hold blocks issuing')
    case = db.execute(select(StoresInspectionCase).where(
        StoresInspectionCase.goods_receipt_line_id == line.id).with_for_update()).scalar_one_or_none()
    if not case or case.status not in ('Pending Inspection', 'Disposition Recorded'):
        raise HTTPException(409, 'Current QA release required')
    qa_quantity = _amount(db.execute(select(func.coalesce(func.sum(StoresLotQAAttribution.quantity), 0))
        .where(StoresLotQAAttribution.receipt_lot_id == lot.id,
               StoresLotQAAttribution.inspection_case_id == case.id,
               StoresLotQAAttribution.disposition == 'Accepted',
               StoresLotQAAttribution.case_version_at_entry == case.version)).scalar_one())
    # Existing stock balance is locked; every Phase 5 issue must now consume
    # an approved request-linked lot reservation.
    balance = stock._lock_balance(db, user, project, lot.warehouse_id, item.id, unit)
    reservation = None
    if reservation_id is not None:
        if os.getenv("STORES_LOT_RESERVATIONS_ENABLED", "false").lower() != "true":
            raise HTTPException(503, "Lot reservation consumption is disabled")
        reservation = db.execute(select(StoresLotReservation).where(
            StoresLotReservation.id == reservation_id,
            StoresLotReservation.project_id == project.id,
            StoresLotReservation.organization_id == user.organization_id,
            StoresLotReservation.receipt_lot_id == lot.id).with_for_update()).scalar_one_or_none()
        if not reservation or reservation.status != "Active" or _amount(reservation.remaining_quantity) < amount:
            raise HTTPException(409, "No valid reservation covers this issue")
    from .issue_authorization import require_issue_authorization
    authorized_request = require_issue_authorization(
        db, project=project, organization_id=user.organization_id,
        reservation=reservation, item_id=item.id, unit=unit, amount=amount)
    _assert_issue_balance_invariants(balance, amount, reservation is not None)
    _require_full_coverage(db, project, lot.warehouse_id, item.id)
    accepted = _posting_quantities(db, lot.id, 'Accept')
    issued = _posting_quantities(db, lot.id, 'Issue', outbound=True)
    returned = _posting_quantities(db, lot.id, 'Return', outbound=True)
    if accepted > qa_quantity or returned > issued or issued > accepted:
        raise HTTPException(409, 'Lot postings or QA quantity are inconsistent')
    reserved_for_lot = _amount(db.execute(select(func.coalesce(func.sum(StoresLotReservation.remaining_quantity), 0))
        .where(StoresLotReservation.receipt_lot_id == lot.id,
               StoresLotReservation.status == "Active")).scalar_one())
    reserved_for_this_issue = amount if reservation is not None else _amount(0)
    if (amount > accepted - issued + returned - reserved_for_lot + reserved_for_this_issue
            or amount > stock._available(balance) + reserved_for_this_issue):
        raise HTTPException(409, 'Insufficient verified lot stock')
    posting = stock._save(db, user, project, 'Issue', posting_number, lot.warehouse_id,
                          reason, recipient, None, None)
    posting_line = StockPostingLine(posting_id=posting.id, item_id=item.id,
                                    quantity=amount, unit=unit)
    db.add(posting_line)
    db.flush()
    db.add(StoresOutboundLotAllocation(organization_id=user.organization_id,
        project_id=project.id, stock_posting_line_id=posting_line.id,
        receipt_lot_id=lot.id, quantity=amount,
        reason=f'Approved Stores request {authorized_request.id} / reservation {reservation.id}', created_by=user.id))
    if reservation is not None:
        reservation.remaining_quantity = _amount(reservation.remaining_quantity) - amount
        if reservation.remaining_quantity == 0:
            reservation.status = "Consumed"
        balance.reserved = _amount(balance.reserved) - amount
    balance.on_hand = _amount(balance.on_hand) - amount
    balance.version += 1
    _event(db, user, project.id, 'stock', posting.id, 'issued', recipient)
    db.flush()
    return {'posting_id': posting.id, 'posting_line_id': posting_line.id,
            'lot_id': lot.id, 'quantity': str(amount), 'unit': unit,
            'material_request_id': authorized_request.id,
            'requirement_line_id': authorized_request.requirement_line_id,
            'work_package_id': authorized_request.work_package_id}
