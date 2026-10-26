"""Feature-gated reservation release, guarded by the same balance/lot locks as posting.

Does not create a physical movement. Must be called in an API-managed transaction.
"""
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from app.domains.supply_chain import stock
from app.domains.supply_chain.service import _amount, _event
from app.domains.supply_chain.models import GoodsReceiptLine
from .models import StoresLotReservation, StoresReceiptLot, StoresLotReservationAction
from .lot_reservations import _enabled
from .atomic_lot_acceptance import _checked_qty


def release_reservation(db, user, project, *, reservation_id, quantity, action_key, reason):
    _enabled()
    stock._stores(db, user, project)
    action_key = action_key.strip()
    reason = reason.strip()
    if not action_key or not reason:
        raise HTTPException(422, 'Action key and reason are required')
    qty = _checked_qty(quantity)
    # Serialize project-unique action keys before acquiring lot/balance locks.
    # Concurrent retries must observe the committed audit action, not race its INSERT.
    from .idempotency_lock import lock_request_key
    lock_request_key(db, organization_id=user.organization_id, project_id=project.id,
                     key=action_key, namespace='lot-reservation-release')
    # Acquire in the same order as the issue writer: lot -> balance -> reservation.
    reservation_ref = db.execute(select(StoresLotReservation.receipt_lot_id).where(
        StoresLotReservation.id == reservation_id,
        StoresLotReservation.organization_id == user.organization_id,
        StoresLotReservation.project_id == project.id)).scalar_one_or_none()
    if reservation_ref is None:
        raise HTTPException(404, 'Reservation not found')
    lot = db.execute(select(StoresReceiptLot).where(
        StoresReceiptLot.id == reservation_ref,
        StoresReceiptLot.organization_id == user.organization_id,
        StoresReceiptLot.project_id == project.id).with_for_update()).scalar_one_or_none()
    if lot is None:
        raise HTTPException(409, 'Reservation lot is missing')
    source = db.get(GoodsReceiptLine, lot.goods_receipt_line_id)
    if source is None:
        raise HTTPException(409, 'Receipt line is missing')
    item, unit = stock._receipt_item(db, source)
    if item is None or unit is None:
        raise HTTPException(409, 'Receipt material is unavailable')
    balance = stock._lock_balance(db, user, project, lot.warehouse_id, item.id, unit)
    reservation = db.execute(select(StoresLotReservation).where(
        StoresLotReservation.id == reservation_id,
        StoresLotReservation.organization_id == user.organization_id,
        StoresLotReservation.project_id == project.id,
        StoresLotReservation.receipt_lot_id == lot.id).with_for_update()).scalar_one_or_none()
    if reservation is None:
        raise HTTPException(404, 'Reservation not found')
    previous = db.execute(select(StoresLotReservationAction).where(
        StoresLotReservationAction.project_id == project.id,
        StoresLotReservationAction.action_key == action_key).with_for_update()).scalar_one_or_none()
    if previous is not None:
        if (previous.reservation_id != reservation.id or
            _amount(previous.quantity) != qty or previous.reason != reason):
            raise HTTPException(409, 'Action key was already used with different details')
        return {'reservation_id': reservation.id, 'action_id': previous.id,
                'status': reservation.status, 'remaining_quantity': str(reservation.remaining_quantity), 'replayed': True}
    if reservation.status != 'Active' or qty > _amount(reservation.remaining_quantity):
        raise HTTPException(409, 'Reservation is not active or has insufficient remaining quantity')
    if _amount(balance.reserved) < qty:
        raise HTTPException(409, 'Aggregate reservation balance is inconsistent')
    reservation.remaining_quantity = _amount(reservation.remaining_quantity) - qty
    if reservation.remaining_quantity == Decimal('0'):
        reservation.status = 'Released'
    balance.reserved = _amount(balance.reserved) - qty
    balance.version += 1
    action = StoresLotReservationAction(organization_id=user.organization_id,
        project_id=project.id, reservation_id=reservation.id, action_key=action_key,
        quantity=qty, reason=reason, created_by=user.id)
    db.add(action)
    db.flush()
    _event(db, user, project.id, 'stores_reservation', reservation.id, 'released', reason)
    return {'reservation_id': reservation.id, 'action_id': action.id,
            'status': reservation.status, 'remaining_quantity': str(reservation.remaining_quantity), 'replayed': False}
