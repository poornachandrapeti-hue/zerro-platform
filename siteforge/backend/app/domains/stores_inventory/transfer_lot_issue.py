"""Feature-gated transfer-derived lot issue using the single stock ledger.

Deliberately default OFF. Requires live migration, posting-concurrency and
mixed-provenance validation before it can be activated.
"""
import os
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.models import User
from app.domains.supply_chain import stock
from app.domains.supply_chain.models import StockPosting, StockPostingLine
from app.domains.supply_chain.service import _event
from app.domains.quality.findings import issue_blocked
from .material_handovers import _scope
from .models import (StoresTransferDestinationLot, StoresLotReservation,
                     StoresTransferIssueAllocation, StoresTransfer)
from .atomic_lot_acceptance import _checked_qty, _assert_acceptance_balance_invariants
from .atomic_lot_issue import _assert_issue_balance_invariants
from .transfer_reservation_release import _transfer_unit
from .transfer_qa_reconciliation import _load_pair, reconcile_transfer_pair
from .posting_number_lock import lock_stock_posting_number
from .issue_authorization import require_issue_authorization

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Transfer Lot Issue'])

class TransferLotIssueIn(BaseModel):
    reservation_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    posting_number: str = Field(min_length=1, max_length=80)
    recipient: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=2000)


def transfer_issue_limits(*, accepted, previously_issued, other_reservations,
                          requested, active_remaining, balance_on_hand, balance_reserved):
    values = tuple(Decimal(str(x)) for x in (accepted, previously_issued, other_reservations,
                requested, active_remaining, balance_on_hand, balance_reserved))
    if not all(x.is_finite() for x in values):
        raise HTTPException(409, 'Invalid transfer issue quantities')
    accepted, issued, other, qty, remaining, onhand, reserved = values
    if min(accepted, issued, other, qty, remaining, onhand, reserved) < 0 or qty <= 0:
        raise HTTPException(409, 'Invalid transfer issue balance')
    if issued > accepted or other + qty > accepted - issued or qty > remaining:
        raise HTTPException(409, 'Insufficient transfer-derived lot balance')
    if reserved > onhand or qty > reserved or qty > onhand:
        raise HTTPException(409, 'Inconsistent destination inventory reservation')
    return qty


@router.post('/material-transfers/destination-lots/{lot_id}/issue', status_code=201)
def issue_transfer_lot(pid: int, lot_id: int, data: TransferLotIssueIn,
                       u: User = Depends(authenticated), db: Session = Depends(get_db)):
    if (os.getenv('STORES_LOT_WRITER_CUTOVER', 'false').lower() != 'true'
        or os.getenv('STORES_ATOMIC_LOT_ISSUE_ENABLED', 'false').lower() != 'true'
        or os.getenv('STORES_TRANSFER_LOT_ISSUE_ENABLED', 'false').lower() != 'true'):
        raise HTTPException(503, 'Transfer-lot material issuing is disabled pending database validation')
    project = _scope(db, u, pid, 'procurement.stock.issue')
    amount = _checked_qty(data.quantity)
    number, recipient, reason = data.posting_number.strip(), data.recipient.strip(), data.reason.strip()
    if not all((number, recipient, reason)):
        raise HTTPException(422, 'Posting number, recipient and reason required')
    lock_stock_posting_number(db, organization_id=u.organization_id, project_id=pid, number=number)
    lot = db.execute(select(StoresTransferDestinationLot).where(
        StoresTransferDestinationLot.id == lot_id,
        StoresTransferDestinationLot.organization_id == u.organization_id,
        StoresTransferDestinationLot.destination_project_id == pid).with_for_update()).scalar_one_or_none()
    if not lot or lot.status != 'QAAcceptedPendingActivation':
        raise HTTPException(409, 'Destination transfer lot requires current QA acceptance')
    transfer = db.get(StoresTransfer, lot.transfer_id)
    if not transfer or transfer.project_id != pid or transfer.destination_project_id not in (None, pid):
        raise HTTPException(409, 'Inter-project material issue not supported')
    lineage, dest, source_post, target_post, source_lines, target_lines = _load_pair(db, transfer, u.organization_id)
    if not reconcile_transfer_pair(transfer, lineage, dest, source_post, target_post, source_lines, target_lines)['balanced']:
        raise HTTPException(409, 'Transfer postings do not reconcile')
    unit = _transfer_unit(db, lot)
    if issue_blocked(db, pid, lot.item_id):
        raise HTTPException(409, 'Quality hold blocks destination issue')
    balance = stock._lock_balance(db, u, project, lot.destination_warehouse_id, lot.item_id, unit)
    if balance is None:
        raise HTTPException(409, 'Destination warehouse balance not found')
    _assert_acceptance_balance_invariants(balance)
    reservation = db.execute(select(StoresLotReservation).where(
        StoresLotReservation.id == data.reservation_id,
        StoresLotReservation.project_id == pid,
        StoresLotReservation.organization_id == u.organization_id,
        StoresLotReservation.transfer_destination_lot_id == lot.id,
        StoresLotReservation.receipt_lot_id.is_(None)).with_for_update()).scalar_one_or_none()
    if not reservation or reservation.status != 'Active':
        raise HTTPException(409, 'Active transfer reservation required')
    request = require_issue_authorization(db, project=project,
        organization_id=u.organization_id, reservation=reservation,
        item_id=lot.item_id, unit=unit, amount=amount)
    issued = db.execute(select(func.coalesce(func.sum(StoresTransferIssueAllocation.quantity), 0))
        .join(StockPostingLine, StockPostingLine.id == StoresTransferIssueAllocation.stock_posting_line_id)
        .join(StockPosting, StockPosting.id == StockPostingLine.posting_id)
        .where(StoresTransferIssueAllocation.transfer_destination_lot_id == lot.id,
               StockPosting.kind == 'Issue', StockPosting.status == 'Posted')).scalar_one()
    all_held = db.execute(select(func.coalesce(func.sum(StoresLotReservation.remaining_quantity), 0)).where(
        StoresLotReservation.transfer_destination_lot_id == lot.id,
        StoresLotReservation.status == 'Active')).scalar_one()
    other_held = Decimal(str(all_held)) - Decimal(str(reservation.remaining_quantity))
    transfer_issue_limits(accepted=lot.quantity, previously_issued=issued,
        other_reservations=other_held, requested=amount,
        active_remaining=reservation.remaining_quantity,
        balance_on_hand=balance.on_hand, balance_reserved=balance.reserved)
    from .mixed_lot_allocation import mixed_lot_warehouse_balance
    diagnostic = mixed_lot_warehouse_balance(pid, lot.destination_warehouse_id, lot.item_id, unit, u, db)
    if not diagnostic['ledger_reconciles']:
        raise HTTPException(409, 'Mixed-lot warehouse reconciliation failed')
    _assert_issue_balance_invariants(balance, amount, True)
    posting = stock._save(db, u, project, 'Issue', number, lot.destination_warehouse_id,
                          reason, recipient, None, target_post.id)
    line = StockPostingLine(posting_id=posting.id, item_id=lot.item_id, quantity=amount, unit=unit)
    db.add(line)
    db.flush()
    db.add(StoresTransferIssueAllocation(organization_id=u.organization_id, project_id=pid,
        stock_posting_line_id=line.id, transfer_destination_lot_id=lot.id,
        reservation_id=reservation.id, quantity=amount, created_by=u.id))
    reservation.remaining_quantity = Decimal(str(reservation.remaining_quantity)) - amount
    if reservation.remaining_quantity == 0:
        reservation.status = 'Consumed'
    balance.reserved = Decimal(str(balance.reserved)) - amount
    balance.on_hand = Decimal(str(balance.on_hand)) - amount
    balance.version += 1
    _event(db, u, pid, 'stock', posting.id, 'issued_transfer_lot', recipient)
    db.flush()
    db.commit()
    return {'posting_id': posting.id, 'posting_line_id': line.id,
            'transfer_destination_lot_id': lot.id, 'reservation_id': reservation.id,
            'material_request_id': request.id, 'requirement_line_id': request.requirement_line_id,
            'work_package_id': request.work_package_id, 'quantity': str(amount), 'unit': unit,
            'physical_stock_readiness': 'Unverified'}
