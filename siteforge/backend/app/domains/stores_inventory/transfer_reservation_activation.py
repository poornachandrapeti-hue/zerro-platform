"""Feature-gated transfer-lot reservation activation (never issues stock).

This uses the existing stock balance and reservation rows; it is disabled until
PostgreSQL concurrency/reconciliation testing and issue-writer support are complete.
"""
import os
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.models import User
from app.domains.supply_chain import stock
from app.domains.supply_chain.models import GoodsReceiptLine
from .material_handovers import _scope
from .models import (StoresLotReservation, StoresTransferDestinationLot,
                     StoresTransferLotLineage, StoresReceiptLot, StoresMaterialRequest)
from .atomic_lot_acceptance import _assert_acceptance_balance_invariants
from .transfer_qa_reconciliation import _load_pair, reconcile_transfer_pair
from .models import StoresTransfer

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Transfer Reservation Activation'])


class ActivateTransferReservationIn(BaseModel):
    version_confirm: str = Field(pattern='^ACKNOWLEDGE_PENDING_VALIDATION$')


def activation_limits(*, lot_quantity, requested, other_held, warehouse_available, approved_remaining):
    """Fail-closed numeric guard, testable without a database."""
    try:
        values = [Decimal(str(x)) for x in (lot_quantity, requested, other_held,
                                           warehouse_available, approved_remaining)]
        if not all(v.is_finite() for v in values):
            raise InvalidOperation
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(409, 'Invalid reservation or inventory quantities')
    lot, qty, held, available, approved = values
    if lot <= 0 or qty <= 0 or held < 0 or available < 0 or approved < 0:
        raise HTTPException(409, 'Inconsistent lot or reserved stock state')
    if qty + held > lot or qty > available or qty > approved:
        raise HTTPException(409, 'Insufficient lot quantity, free stock, or approved demand')
    return qty


def _activation_gate():
    if os.getenv('STORES_LOT_WRITER_CUTOVER', 'false').lower() != 'true' or \
       os.getenv('STORES_TRANSFER_RESERVATION_ACTIVATION_ENABLED', 'false').lower() != 'true':
        raise HTTPException(503, 'Transfer-derived reservations remain disabled pending PostgreSQL validation')


@router.post('/material-transfers/reservation-intents/{intent_id}/activate')
def activate_transfer_reservation(pid: int, intent_id: int, data: ActivateTransferReservationIn,
                                  u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Atomically activate an existing canonical transfer intent and aggregate reservation.

    The feature flag defaults OFF; physical issue writer remains separately disabled.
    """
    _activation_gate()
    project = _scope(db, u, pid, 'procurement.stock.reserve')
    intent = db.execute(select(StoresLotReservation).where(
        StoresLotReservation.id == intent_id, StoresLotReservation.organization_id == u.organization_id,
        StoresLotReservation.project_id == pid).with_for_update()).scalar_one_or_none()
    if intent is None or not intent.transfer_destination_lot_id or intent.receipt_lot_id is not None:
        raise HTTPException(404, 'Transfer reservation intent not found')
    if intent.status != 'PendingActivation':
        raise HTTPException(409, 'Only pending transfer reservation intents may be activated')
    lot = db.execute(select(StoresTransferDestinationLot).where(
        StoresTransferDestinationLot.id == intent.transfer_destination_lot_id,
        StoresTransferDestinationLot.organization_id == u.organization_id,
        StoresTransferDestinationLot.destination_project_id == pid).with_for_update()).scalar_one_or_none()
    if lot is None or lot.status != 'QAAcceptedPendingActivation':
        raise HTTPException(409, 'Destination lot has no current accepted QA decision')
    transfer = db.get(StoresTransfer, lot.transfer_id)
    if not transfer or transfer.project_id != pid or transfer.destination_project_id not in (None, pid):
        raise HTTPException(409, 'Cross-project stock reservation activation is not supported')
    lineage, destination, source_post, target_post, source_lines, target_lines = _load_pair(db, transfer, u.organization_id)
    reconciliation = reconcile_transfer_pair(transfer, lineage, destination, source_post,
                                             target_post, source_lines, target_lines)
    if not reconciliation['balanced']:
        raise HTTPException(409, 'Paired transfer postings are not reconciled')
    request = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.id == intent.material_request_id,
        StoresMaterialRequest.organization_id == u.organization_id,
        StoresMaterialRequest.project_id == pid).with_for_update()).scalar_one_or_none()
    if not request or request.status != 'Approved' or request.requirement_line_id != intent.requirement_line_id:
        raise HTTPException(409, 'Original canonical material demand is no longer approved')
    source = db.get(StoresReceiptLot, lot.source_receipt_lot_id)
    receipt_line = db.get(GoodsReceiptLine, source.goods_receipt_line_id) if source else None
    if not receipt_line or source.id != lineage.source_receipt_lot_id:
        raise HTTPException(409, 'Transfer source provenance missing')
    item, unit = stock._receipt_item(db, receipt_line)
    if not item or item.id != lot.item_id or item.id != request.item_id or unit != request.base_unit:
        raise HTTPException(409, 'Transfer and approved demand material/unit mismatch')
    from .issue_authorization import require_issue_authorization
    require_issue_authorization(db, project=project, organization_id=u.organization_id,
                                reservation=intent, item_id=item.id, unit=unit,
                                amount=Decimal(str(intent.remaining_quantity)))
    # Serialize changes to the destination aggregate balance and check its invariants.
    balance = stock._lock_balance(db, u, project, lot.destination_warehouse_id, item.id, unit)
    _assert_acceptance_balance_invariants(balance)
    if balance is None:
        raise HTTPException(409, 'Destination stock balance missing')
    # Do not depend on aggregate on-hand alone: other active reservations of
    # this specific transfer lot reduce its own allocation ceiling.
    active_held = db.execute(select(func.coalesce(func.sum(StoresLotReservation.remaining_quantity), 0)).where(
        StoresLotReservation.transfer_destination_lot_id == lot.id,
        StoresLotReservation.status == 'Active')).scalar_one()
    from .mixed_lot_allocation import mixed_lot_warehouse_balance
    diagnostic = mixed_lot_warehouse_balance(pid, lot.destination_warehouse_id, item.id, unit, u, db)
    if not diagnostic['ledger_reconciles']:
        raise HTTPException(409, 'Destination warehouse provenance does not reconcile')
    approved_held = db.execute(select(func.coalesce(func.sum(StoresLotReservation.remaining_quantity), 0)).where(
        StoresLotReservation.material_request_id == request.id,
        StoresLotReservation.status == 'Active')).scalar_one()
    approved_remaining = Decimal(str(request.requested_quantity)) - Decimal(str(approved_held))
    qty = activation_limits(lot_quantity=lot.quantity, requested=intent.remaining_quantity,
                            other_held=active_held, warehouse_available=stock._available(balance),
                            approved_remaining=approved_remaining)
    balance.reserved = Decimal(str(balance.reserved)) + qty
    balance.version += 1
    intent.status = 'Active'
    db.flush()
    db.commit()
    return {'reservation_id': intent.id, 'status': intent.status,
            'reserved_quantity': str(qty), 'stock_issued': False,
            'physical_stock_readiness': 'Unverified'}
