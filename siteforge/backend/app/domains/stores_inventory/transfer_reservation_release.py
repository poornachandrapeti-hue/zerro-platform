"""Transfer-derived reservation release; no issue or physical movement.

The feature is default-off until live PostgreSQL integration has been validated.
"""
import os
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.models import User
from app.domains.supply_chain import stock
from app.domains.supply_chain.service import _event
from .material_handovers import _scope
from .models import StoresLotReservation, StoresTransferDestinationLot, StoresLotReservationAction
from .atomic_lot_acceptance import _checked_qty, _assert_acceptance_balance_invariants
from .idempotency_lock import lock_request_key

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Transfer Reservation Release'])

class ReleaseTransferReservationIn(BaseModel):
    quantity: Decimal = Field(gt=0, decimal_places=3)
    action_key: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=2000)


def release_policy(status, remaining, quantity, reserved_balance=None):
    qty = _checked_qty(quantity)
    rem = Decimal(str(remaining))
    if not rem.is_finite() or rem < 0 or qty > rem or status not in ('Active', 'PendingActivation'):
        raise HTTPException(409, 'Reservation cannot be released in this state or quantity')
    if status == 'Active':
        held = Decimal(str(reserved_balance))
        if not held.is_finite() or held < qty:
            raise HTTPException(409, 'Aggregate reserved balance is inconsistent')
    return qty


@router.post('/material-transfers/reservation-intents/{intent_id}/release')
def release_transfer_reservation(pid: int, intent_id: int, data: ReleaseTransferReservationIn,
                                 u: User = Depends(authenticated), db: Session = Depends(get_db)):
    if os.getenv('STORES_TRANSFER_RESERVATION_RELEASE_ENABLED', 'false').lower() != 'true':
        raise HTTPException(503, 'Transfer reservation release is disabled pending PostgreSQL validation')
    project = _scope(db, u, pid, 'procurement.stock.reserve')
    key, reason = data.action_key.strip(), data.reason.strip()
    if not key or not reason:
        raise HTTPException(422, 'Action key and reason are required')
    lock_request_key(db, organization_id=u.organization_id, project_id=pid,
                     key=key, namespace='lot-reservation-release')
    # Lock destination lot first, then aggregate balance, then reservation. This
    # matches the source-lot release/issue lock ordering as closely as possible.
    lot_id = db.execute(select(StoresLotReservation.transfer_destination_lot_id).where(
        StoresLotReservation.id == intent_id, StoresLotReservation.project_id == pid,
        StoresLotReservation.organization_id == u.organization_id)).scalar_one_or_none()
    if lot_id is None:
        raise HTTPException(404, 'Transfer reservation not found')
    lot = db.execute(select(StoresTransferDestinationLot).where(
        StoresTransferDestinationLot.id == lot_id,
        StoresTransferDestinationLot.destination_project_id == pid,
        StoresTransferDestinationLot.organization_id == u.organization_id).with_for_update()).scalar_one_or_none()
    if lot is None:
        raise HTTPException(409, 'Transfer destination lot missing')
    balance = stock._lock_balance(db, u, project, lot.destination_warehouse_id, lot.item_id,
                                  _transfer_unit(db, lot))
    intent = db.execute(select(StoresLotReservation).where(
        StoresLotReservation.id == intent_id, StoresLotReservation.project_id == pid,
        StoresLotReservation.organization_id == u.organization_id,
        StoresLotReservation.transfer_destination_lot_id == lot.id,
        StoresLotReservation.receipt_lot_id.is_(None)).with_for_update()).scalar_one_or_none()
    if intent is None:
        raise HTTPException(404, 'Transfer reservation not found')
    prior = db.execute(select(StoresLotReservationAction).where(
        StoresLotReservationAction.project_id == pid,
        StoresLotReservationAction.action_key == key).with_for_update()).scalar_one_or_none()
    qty = _checked_qty(data.quantity)
    if prior is not None:
        if prior.reservation_id != intent.id or Decimal(str(prior.quantity)) != qty or prior.reason != reason:
            raise HTTPException(409, 'Action key used with different release details')
        return {'reservation_id': intent.id, 'action_id': prior.id, 'status': intent.status,
                'remaining_quantity': str(intent.remaining_quantity), 'replayed': True, 'stock_issued': False}
    if balance is None and intent.status == 'Active':
        raise HTTPException(409, 'Destination stock balance missing')
    if balance is not None:
        _assert_acceptance_balance_invariants(balance)
    qty = release_policy(intent.status, intent.remaining_quantity, qty,
                         getattr(balance, 'reserved', None))
    was_active = intent.status == 'Active'
    intent.remaining_quantity = Decimal(str(intent.remaining_quantity)) - qty
    if intent.remaining_quantity == 0:
        intent.status = 'Released'
    if balance is not None and was_active:
        balance.reserved = Decimal(str(balance.reserved)) - qty
        balance.version += 1
    action = StoresLotReservationAction(organization_id=u.organization_id, project_id=pid,
        reservation_id=intent.id, action_key=key, quantity=qty, reason=reason, created_by=u.id)
    db.add(action)
    db.flush()
    _event(db, u, pid, 'stores_reservation', intent.id, 'released', reason)
    db.commit()
    return {'reservation_id': intent.id, 'action_id': action.id, 'status': intent.status,
            'remaining_quantity': str(intent.remaining_quantity), 'replayed': False, 'stock_issued': False}


def _transfer_unit(db, lot):
    from .models import StoresReceiptLot
    from app.domains.supply_chain.models import GoodsReceiptLine
    source = db.get(StoresReceiptLot, lot.source_receipt_lot_id)
    line = db.get(GoodsReceiptLine, source.goods_receipt_line_id) if source else None
    item, unit = stock._receipt_item(db, line) if line else (None, None)
    if item is None or item.id != lot.item_id or not unit:
        raise HTTPException(409, 'Transfer origin material/unit provenance missing')
    return unit
