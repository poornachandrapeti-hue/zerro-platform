"""Feature-gated lot reservation; caller commits reservation and aggregate balance together."""
import os
from datetime import date
from fastapi import HTTPException
from sqlalchemy import select, func
from app.domains.supply_chain import stock
from app.domains.supply_chain.models import GoodsReceiptLine
from app.domains.quality.findings import issue_blocked
from app.domains.supply_chain.service import _amount
from .models import StoresReceiptLot, StoresLotReservation, StoresInspectionCase, StoresLotQAAttribution
from .atomic_lot_acceptance import _checked_qty, _assert_acceptance_balance_invariants
from .atomic_lot_issue import _require_full_coverage, _posting_quantities


def _enabled():
    if os.getenv("STORES_LOT_WRITER_CUTOVER", "false").lower() != "true":
        raise HTTPException(503, "Disable legacy stock writers before enabling lot reservations")
    if os.getenv("STORES_LOT_RESERVATIONS_ENABLED", "false").lower() != "true":
        raise HTTPException(503, "Lot reservations are disabled until legacy writers are gated and concurrency is verified")


def reserve_lot(db, user, project, *, lot_id, quantity, request_key, work_package_id=None, planning_wbs_id=None):
    _enabled()
    stock._stores(db, user, project)
    qty = _checked_qty(quantity)
    key = request_key.strip()
    if not key:
        raise HTTPException(422, "Request key is required")
    from .reservation_work_scope import validate_scope
    validate_scope(db, project, work_package_id=work_package_id, planning_wbs_id=planning_wbs_id)
    # Serialize duplicate submissions BEFORE checking whether the row exists.
    # Lock is released automatically by the API-owned commit/rollback.
    from .idempotency_lock import lock_request_key
    lock_request_key(db, organization_id=user.organization_id, project_id=project.id,
                     key=key, namespace='lot-reservation')
    # Identical retries return the existing reservation; changed retry parameters are rejected.
    existing = db.execute(select(StoresLotReservation).where(
        StoresLotReservation.project_id == project.id,
        StoresLotReservation.request_key == key).with_for_update()).scalar_one_or_none()
    if existing:
        if (existing.receipt_lot_id != lot_id or _amount(existing.quantity) != qty or
            existing.work_package_id != work_package_id or existing.planning_wbs_id != planning_wbs_id):
            raise HTTPException(409, "Reservation request key already used for different parameters")
        return {"reservation_id": existing.id, "status": existing.status, "remaining_quantity": str(existing.remaining_quantity)}
    lot = db.execute(select(StoresReceiptLot).where(
        StoresReceiptLot.id == lot_id, StoresReceiptLot.project_id == project.id,
        StoresReceiptLot.organization_id == user.organization_id).with_for_update()).scalar_one_or_none()
    if lot is None:
        raise HTTPException(404, "Lot not found")
    if lot.expiry_date and lot.expiry_date < date.today():
        raise HTTPException(409, "Expired lot cannot be reserved")
    from .preservation import require_preservation_clear
    require_preservation_clear(db, lot_id=lot.id, project_id=project.id,
                               organization_id=user.organization_id)
    source = db.get(GoodsReceiptLine, lot.goods_receipt_line_id)
    if not source:
        raise HTTPException(409, "Source receipt line not found")
    item, unit = stock._receipt_item(db, source)
    if not item or not unit or issue_blocked(db, project.id, item.id):
        raise HTTPException(409, "Item is unavailable or under quality hold")
    case = db.execute(select(StoresInspectionCase).where(
        StoresInspectionCase.goods_receipt_line_id == source.id).with_for_update()).scalar_one_or_none()
    if not case or case.status not in ("Pending Inspection", "Disposition Recorded"):
        raise HTTPException(409, "Current QA release required")
    qa_qty = _amount(db.execute(select(func.coalesce(func.sum(StoresLotQAAttribution.quantity), 0)).where(
        StoresLotQAAttribution.receipt_lot_id == lot.id,
        StoresLotQAAttribution.inspection_case_id == case.id,
        StoresLotQAAttribution.disposition == "Accepted",
        StoresLotQAAttribution.case_version_at_entry == case.version)).scalar_one())
    balance = stock._lock_balance(db, user, project, lot.warehouse_id, item.id, unit)
    # A QA-cleared lot must not create a reservation against an already-corrupt
    # aggregate ledger.  Fail before any reservation row or balance mutation.
    _assert_acceptance_balance_invariants(balance)
    _require_full_coverage(db, project, lot.warehouse_id, item.id)
    accepted = _posting_quantities(db, lot.id, "Accept")
    issued = _posting_quantities(db, lot.id, "Issue", outbound=True)
    returned = _posting_quantities(db, lot.id, "Return", outbound=True)
    held = _amount(db.execute(select(func.coalesce(func.sum(StoresLotReservation.remaining_quantity), 0)).where(
        StoresLotReservation.receipt_lot_id == lot.id,
        StoresLotReservation.status == "Active")).scalar_one())
    if accepted > qa_qty or returned > issued or issued > accepted:
        raise HTTPException(409, "Lot movement or QA mismatch")
    if qty > accepted - issued + returned - held or qty > stock._available(balance):
        raise HTTPException(409, "Insufficient unreserved, QA-cleared lot stock")
    row = StoresLotReservation(organization_id=user.organization_id, project_id=project.id,
        receipt_lot_id=lot.id, request_key=key, work_package_id=work_package_id,
        planning_wbs_id=planning_wbs_id, quantity=qty, remaining_quantity=qty,
        status="Active", created_by=user.id)
    db.add(row)
    balance.reserved = _amount(balance.reserved) + qty
    balance.version += 1
    db.flush()
    return {"reservation_id": row.id, "status": row.status, "remaining_quantity": str(qty)}
