"""Read model for a single approved material issue request.

Reservations are allocations, not issues or construction progress. Releases are
recorded separately from consumption, so original reservation totals must not
be mistaken for currently committed demand.
"""
from decimal import Decimal
from sqlalchemy import select
from .models import StoresLotReservation, StoresLotReservationAction


def dec(value):
    return Decimal(str(value if value is not None else 0))


def summarize(approved_quantity, reservations, released_by_reservation):
    active = consumed = released = Decimal('0')
    details = []
    for row in reservations:
        original = dec(row.quantity)
        remaining = dec(row.remaining_quantity)
        freed = dec(released_by_reservation.get(row.id, 0))
        used = original - remaining - freed
        if min(original, remaining, freed, used) < 0 or remaining + freed > original:
            raise ValueError('Reservation history is inconsistent')
        if row.status == 'Active':
            active += remaining
        elif remaining:
            raise ValueError('Inactive reservation retains unconsumed quantity')
        consumed += used
        released += freed
        details.append(dict(id=row.id, lot_id=row.receipt_lot_id if hasattr(row, 'receipt_lot_id') else None, status=row.status,
            allocated_quantity=str(original), remaining_quantity=str(remaining),
            released_quantity=str(freed), consumed_by_issue=str(used)))
    approved = dec(approved_quantity)
    committed = active + consumed
    return dict(approved_quantity=str(approved), active_reserved_quantity=str(active),
        consumed_by_issue=str(consumed), released_quantity=str(released),
        unallocated_quantity=str(max(Decimal('0'), approved - committed)),
        overcommitted=committed > approved,
        allocated_quantity=str(active + consumed), reservations=details, allocations=details,
        note='Reservation consumption indicates Stores issue, not physical installation or earned progress.')


def request_summary(db, request):
    reservations = db.execute(select(StoresLotReservation).where(
        StoresLotReservation.organization_id == request.organization_id,
        StoresLotReservation.project_id == request.project_id,
        StoresLotReservation.material_request_id == request.id)).scalars().all()
    ids = [r.id for r in reservations]
    actions = db.execute(select(StoresLotReservationAction).where(
        StoresLotReservationAction.organization_id == request.organization_id,
        StoresLotReservationAction.project_id == request.project_id,
        StoresLotReservationAction.reservation_id.in_(ids))).scalars().all() if ids else []
    released = {}
    for action in actions:
        released[action.reservation_id] = dec(released.get(action.reservation_id)) + dec(action.quantity)
    return summarize(request.requested_quantity, reservations, released)
