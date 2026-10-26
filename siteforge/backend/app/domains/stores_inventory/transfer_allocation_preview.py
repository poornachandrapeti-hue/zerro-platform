"""Read-only transfer-derived lot allocation preview; never authorizes a stock mutation.

The existing reservation table now permits exactly one provenance type.
Transfer-intent rows remain PendingActivation and cannot change stock.
"""
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.models import User
from app.domains.supply_chain.models import StockBalance
from .material_handovers import _scope
from .models import StoresTransferDestinationLot, StoresTransferLotLineage, StoresLotReservation, StoresMaterialRequest
from .mixed_lot_allocation import mixed_lot_warehouse_balance

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Transfer Lot Allocation'])


def preview_transfer_lot(*, lot_quantity, requested_quantity, qa_status, reconciled, posted,
                         physical_available=None):
    """Fail-closed decision; no QA status alone is permission to issue."""
    blockers = []
    try:
        lot_qty = Decimal(str(lot_quantity))
        requested = Decimal(str(requested_quantity))
        if not lot_qty.is_finite() or not requested.is_finite() or lot_qty <= 0 or requested <= 0:
            raise InvalidOperation
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(422, 'Positive finite quantities are required')
    if requested > lot_qty:
        blockers.append('REQUEST_EXCEEDS_TRANSFER_LOT')
    if qa_status != 'QAAcceptedPendingActivation':
        blockers.append('DESTINATION_QA_NOT_ACCEPTED')
    if not posted:
        blockers.append('PAIRED_TRANSFER_POSTING_MISSING')
    if not reconciled:
        blockers.append('WAREHOUSE_LEDGER_NOT_RECONCILED')
    if physical_available is None:
        blockers.append('LOT_LEVEL_AVAILABLE_QUANTITY_NOT_VERIFIED')
    else:
        try:
            available = Decimal(str(physical_available))
            if not available.is_finite() or available < 0:
                raise InvalidOperation
        except (InvalidOperation, TypeError, ValueError):
            blockers.append('LOT_LEVEL_AVAILABLE_QUANTITY_INVALID')
        else:
            if requested > available:
                blockers.append('INSUFFICIENT_UNRESERVED_LOT_QUANTITY')
    blockers += ['TRANSFER_DERIVED_RESERVATION_ACTIVATION_PENDING',
                 'TRANSFER_DERIVED_ISSUE_WRITER_PENDING',
                 'LIVE_DATABASE_VALIDATION_PENDING']
    return {'requested_quantity': str(requested), 'lot_quantity': str(lot_qty),
            'reservation_allowed': False, 'issue_allowed': False,
            'physical_stock_readiness': 'Unverified', 'blockers': sorted(set(blockers))}


@router.get('/material-transfers/destination-lots/{lot_id}/allocation-preview')
def destination_allocation_preview(pid: int, lot_id: int, quantity: Decimal,
                                   u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.view')
    lot = db.execute(select(StoresTransferDestinationLot).where(
        StoresTransferDestinationLot.id == lot_id,
        StoresTransferDestinationLot.organization_id == u.organization_id,
        StoresTransferDestinationLot.destination_project_id == pid)).scalar_one_or_none()
    if lot is None:
        raise HTTPException(404, 'Destination transfer lot not found')
    lineage = db.execute(select(StoresTransferLotLineage).where(
        StoresTransferLotLineage.id == lot.lineage_id,
        StoresTransferLotLineage.organization_id == u.organization_id,
        StoresTransferLotLineage.transfer_id == lot.transfer_id)).scalar_one_or_none()
    if lineage is None:
        raise HTTPException(409, 'Transfer source provenance missing')
    # The transfer has a single source item/unit. Resolve unit from its actual
    # source GRN line rather than accepting a caller-supplied unit.
    from .models import StoresReceiptLot
    from app.domains.supply_chain.models import GoodsReceiptLine
    from app.domains.supply_chain import stock
    source_lot = db.get(StoresReceiptLot, lot.source_receipt_lot_id)
    if not source_lot or source_lot.id != lineage.source_receipt_lot_id:
        raise HTTPException(409, 'Source receipt lot provenance missing')
    receipt_line = db.get(GoodsReceiptLine, source_lot.goods_receipt_line_id)
    if not receipt_line:
        raise HTTPException(409, 'Original GRN line missing')
    item, unit = stock._receipt_item(db, receipt_line)
    if not item or item.id != lot.item_id or not unit:
        raise HTTPException(409, 'Transfer material does not match GRN source')
    balance = mixed_lot_warehouse_balance(pid, lot.destination_warehouse_id, lot.item_id, unit, u, db)
    preview = preview_transfer_lot(lot_quantity=lot.quantity, requested_quantity=quantity,
        qa_status=lot.status, posted=bool(lineage.source_posting_id and lineage.destination_posting_id),
        reconciled=balance['ledger_reconciles'])
    return {'project_id': pid, 'transfer_id': lot.transfer_id, 'destination_lot_id': lot.id,
            'warehouse_id': lot.destination_warehouse_id, 'item_id': lot.item_id,
            'unit': unit, 'ledger_reconciles': balance['ledger_reconciles'], **preview}


class TransferReservationIntentIn(BaseModel):
    destination_lot_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    request_key: str = Field(min_length=1, max_length=120)
    material_request_id: int = Field(gt=0)


def validate_pending_transfer_intent(lot, quantity):
    """Intents are not reservations and must never mutate aggregate stock."""
    from decimal import Decimal
    qty = Decimal(str(quantity))
    if not qty.is_finite() or qty <= 0 or qty > Decimal(str(lot.quantity)):
        raise HTTPException(422, 'Transfer intent quantity must be finite and within lot quantity')
    return qty


@router.post('/material-transfers/destination-lots/reservation-intents', status_code=201)
def create_transfer_reservation_intent(pid: int, data: TransferReservationIntentIn,
                                       u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Record a non-stock reservation intention in the existing reservations table.

    Not an active reservation; issue/release/reassign endpoints must not consume it.
    """
    project = _scope(db, u, pid, 'procurement.stock.reserve')
    from .idempotency_lock import lock_request_key
    from .reservation_work_scope import validate_scope
    key = data.request_key.strip()
    if not key:
        raise HTTPException(422, 'Request key cannot be blank')
    lock_request_key(db, organization_id=u.organization_id, project_id=pid,
                     key=key, namespace='lot-reservation')
    existing = db.execute(select(StoresLotReservation).where(
        StoresLotReservation.project_id == pid,
        StoresLotReservation.request_key == key).with_for_update()).scalar_one_or_none()
    if existing:
        if (existing.transfer_destination_lot_id != data.destination_lot_id or
            existing.quantity != data.quantity or existing.material_request_id != data.material_request_id):
            raise HTTPException(409, 'Reservation key already assigned to other parameters')
        return {'intent_id': existing.id, 'status': existing.status, 'stock_reserved': False}
    lot = db.execute(select(StoresTransferDestinationLot).where(
        StoresTransferDestinationLot.id == data.destination_lot_id,
        StoresTransferDestinationLot.organization_id == u.organization_id,
        StoresTransferDestinationLot.destination_project_id == pid).with_for_update()).scalar_one_or_none()
    if not lot:
        raise HTTPException(404, 'Destination lot not found')
    qty = validate_pending_transfer_intent(lot, data.quantity)
    request = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.id == data.material_request_id,
        StoresMaterialRequest.organization_id == u.organization_id,
        StoresMaterialRequest.project_id == pid).with_for_update()).scalar_one_or_none()
    if not request or request.status != 'Approved' or not request.requirement_line_id:
        raise HTTPException(409, 'Transfer intent requires an approved canonical Stores issue request')
    validate_scope(db, project, work_package_id=request.work_package_id,
                   planning_wbs_id=request.planning_wbs_id)
    # Reuse existing issue authorization so canonical Procurement demand, contractor
    # work-package release, material and unit cannot be bypassed by transfer intents.
    from .issue_authorization import require_issue_authorization
    from types import SimpleNamespace
    from .models import StoresReceiptLot
    from app.domains.supply_chain.models import GoodsReceiptLine
    from app.domains.supply_chain import stock
    source = db.get(StoresReceiptLot, lot.source_receipt_lot_id)
    receipt_line = db.get(GoodsReceiptLine, source.goods_receipt_line_id) if source else None
    if not receipt_line:
        raise HTTPException(409, 'Transfer source GRN provenance missing')
    item, unit = stock._receipt_item(db, receipt_line)
    if not item or item.id != lot.item_id or request.item_id != lot.item_id or request.base_unit != unit:
        raise HTTPException(409, 'Transfer destination lot does not match approved material demand')
    candidate = SimpleNamespace(material_request_id=request.id,
        requirement_line_id=request.requirement_line_id,
        work_package_id=request.work_package_id, planning_wbs_id=request.planning_wbs_id,
        remaining_quantity=qty)
    require_issue_authorization(db, project=project, organization_id=u.organization_id,
                                reservation=candidate, item_id=item.id, unit=unit, amount=qty)
    # Multiple independent keys must not overbook the same approved request or
    # destination lot, even though these remain non-stock reservation intents.
    existing_intents = db.execute(select(StoresLotReservation).where(
        StoresLotReservation.project_id == pid,
        StoresLotReservation.transfer_destination_lot_id == lot.id,
        StoresLotReservation.status == 'PendingActivation').with_for_update()).scalars().all()
    if sum((Decimal(str(r.quantity)) for r in existing_intents), Decimal('0')) + qty > Decimal(str(lot.quantity)):
        raise HTTPException(409, 'Transfer intent quantities exceed destination lot quantity')
    request_intents = db.execute(select(StoresLotReservation).where(
        StoresLotReservation.project_id == pid,
        StoresLotReservation.material_request_id == request.id,
        StoresLotReservation.status.in_(['PendingActivation', 'Active'])).with_for_update()).scalars().all()
    if sum((Decimal(str(r.remaining_quantity)) for r in request_intents), Decimal('0')) + qty > Decimal(str(request.requested_quantity)):
        raise HTTPException(409, 'Transfer intent exceeds approved Stores request quantity')
    # Deliberately do not mark Active and do not increase StockBalance.reserved.
    # A later activation writer must verify the approved canonical material request,
    # lot-level availability, QA and ledger concurrency in one transaction.
    row = StoresLotReservation(organization_id=u.organization_id, project_id=pid,
        receipt_lot_id=None, transfer_destination_lot_id=lot.id,
        request_key=key, material_request_id=request.id, requirement_line_id=request.requirement_line_id,
        work_package_id=request.work_package_id, planning_wbs_id=request.planning_wbs_id,
        quantity=qty, remaining_quantity=qty,
        status='PendingActivation', created_by=u.id)
    db.add(row)
    db.flush()
    result = {'intent_id': row.id, 'status': row.status, 'stock_reserved': False}
    db.commit()
    return result
