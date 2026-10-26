"""Allocate approved issue requests to lots without creating new procurement demand.

The existing feature gate on reserve_lot remains mandatory. Caller owns commit/rollback.
"""
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select, func
from app.domains.supply_chain.models import MaterialRequirement, RequirementLine, GoodsReceiptLine
from app.domains.supply_chain import stock
from .models import StoresMaterialRequest, StoresLotReservation, StoresReceiptLot
from .lot_reservations import reserve_lot, _enabled


def _amount(value):
    return Decimal(str(value or 0))


def remaining_demand(approved, allocated):
    return max(Decimal('0'), _amount(approved) - _amount(allocated))


def allocate_request(db, user, project, *, request_id, lot_id, quantity, request_key):
    _enabled()  # no bypass of disabled legacy/lot issue controls
    stock._stores(db, user, project)
    qty = _amount(quantity)
    if not qty.is_finite() or qty <= 0 or qty.as_tuple().exponent < -3:
        raise HTTPException(422, 'Allocation quantity must be positive with at most 3 decimals')
    # Serialize allocations for the same material issue request.
    request = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.id == request_id,
        StoresMaterialRequest.project_id == project.id,
        StoresMaterialRequest.organization_id == user.organization_id).with_for_update()).scalar_one_or_none()
    if not request:
        raise HTTPException(404, 'Material issue request not found')
    if request.status != 'Approved' or not request.requirement_line_id:
        raise HTTPException(409, 'Only approved requests linked to canonical demand can be allocated')
    req_line = db.get(RequirementLine, request.requirement_line_id)
    parent = db.get(MaterialRequirement, req_line.requirement_id) if req_line else None
    if not parent or parent.project_id != project.id or parent.organization_id != user.organization_id or parent.status != 'Approved' or parent.impact_state == 'Review required':
        raise HTTPException(409, 'Canonical requirement is no longer approved')
    # A previously approved Stores request may become stale after a change to
    # the canonical Procurement line. Recheck its item, unit and WBS scope
    # before reserving any stock; do not create parallel demand.
    if (not req_line or req_line.item_id != request.item_id or
            req_line.unit != request.base_unit or
            (req_line.planning_wbs_id is not None and
             req_line.planning_wbs_id != request.planning_wbs_id)):
        raise HTTPException(409, 'Canonical requirement line no longer matches material allocation scope')
    if not Decimal(str(req_line.quantity)).is_finite() or Decimal(str(req_line.quantity)) <= 0:
        raise HTTPException(409, 'Canonical requirement line quantity is invalid')
    lot = db.execute(select(StoresReceiptLot).where(
        StoresReceiptLot.id == lot_id, StoresReceiptLot.project_id == project.id,
        StoresReceiptLot.organization_id == user.organization_id).with_for_update()).scalar_one_or_none()
    if not lot:
        raise HTTPException(404, 'Receipt lot not found in project')
    receipt_line = db.get(GoodsReceiptLine, lot.goods_receipt_line_id)
    item, unit = stock._receipt_item(db, receipt_line) if receipt_line else (None, None)
    if not item or item.id != request.item_id or unit != request.base_unit:
        raise HTTPException(422, 'Lot material/unit differs from approved issue request')
    key = request_key.strip()
    if not key:
        raise HTTPException(422, 'Reservation key required')
    existing = db.execute(select(StoresLotReservation).where(
        StoresLotReservation.project_id == project.id,
        StoresLotReservation.request_key == key).with_for_update()).scalar_one_or_none()
    if existing:
        if existing.material_request_id != request.id or existing.receipt_lot_id != lot_id or _amount(existing.quantity) != qty:
            raise HTTPException(409, 'Reservation key already used for different allocation')
        return {'material_request_id': request.id, 'reservation_id': existing.id,
                'status': existing.status, 'remaining_quantity': str(existing.remaining_quantity), 'replayed': True}
    # Released allocations no longer consume demand; issued material still does.
    from .allocation_lifecycle import request_summary
    summary = request_summary(db, request)
    if summary['overcommitted']:
        raise HTTPException(409, 'Existing allocations exceed approved issue quantity')
    if qty > _amount(summary['unallocated_quantity']):
        raise HTTPException(409, 'Allocation exceeds outstanding issue request quantity')
    # Existing service locks balance, verifies lot QA/expiry, stock, availability, provenance and scope.
    result = reserve_lot(db, user, project, lot_id=lot_id, quantity=qty, request_key=key,
                         work_package_id=request.work_package_id, planning_wbs_id=request.planning_wbs_id)
    reservation = db.get(StoresLotReservation, result['reservation_id'])
    reservation.material_request_id = request.id
    reservation.requirement_line_id = request.requirement_line_id
    db.flush()
    return {'material_request_id': request.id, **result, 'replayed': False}
