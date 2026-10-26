"""Work-scope validation and auditable reassignment of active lot reservations."""
from fastapi import HTTPException
from sqlalchemy import select
from app.domains.construction.models import WorkPackage
from app.domains.planning_reporting.workspace_models import PlanningWBS
from app.domains.supply_chain import stock
from .models import StoresLotReservation, StoresReceiptLot, StoresReservationReassignment
from .lot_reservations import _enabled

def validate_scope(db, project, *, work_package_id=None, planning_wbs_id=None):
    if work_package_id is None and planning_wbs_id is None:
        raise HTTPException(422, 'Work package or planning WBS is required')
    if work_package_id is not None:
        package = db.execute(select(WorkPackage).where(WorkPackage.id == work_package_id,
            WorkPackage.project_id == project.id, WorkPackage.organization_id == project.organization_id)).scalar_one_or_none()
        if not package or package.status in ('Cancelled', 'Handed Over') or package.release_state != 'Released':
            raise HTTPException(409, 'Work package must exist in this project and be released')
    if planning_wbs_id is not None:
        wbs = db.execute(select(PlanningWBS).where(PlanningWBS.id == planning_wbs_id,
            PlanningWBS.project_id == project.id, PlanningWBS.organization_id == project.organization_id,
            PlanningWBS.active.is_(True))).scalar_one_or_none()
        if not wbs:
            raise HTTPException(409, 'Active WBS not found in this project')
    return True

def reassign_reservation(db, user, project, *, reservation_id, work_package_id, planning_wbs_id, action_key, reason):
    _enabled()
    stock._stores(db, user, project)
    action_key, reason = action_key.strip(), reason.strip()
    if not action_key or not reason:
        raise HTTPException(422, 'Action key and reason are required')
    # Reassign references only, not stock/lot. Reservation and lot identity are immutable.
    # Serialize project-unique action keys before acquiring lot/balance locks.
    # Concurrent retries must observe the committed audit action, not race its INSERT.
    from .idempotency_lock import lock_request_key
    lock_request_key(db, organization_id=user.organization_id, project_id=project.id,
                     key=action_key, namespace='lot-reservation-reassignment')
    lot_id = db.execute(select(StoresLotReservation.receipt_lot_id).where(
        StoresLotReservation.id == reservation_id, StoresLotReservation.project_id == project.id,
        StoresLotReservation.organization_id == user.organization_id)).scalar_one_or_none()
    if lot_id is None:
        raise HTTPException(404, 'Reservation not found')
    db.execute(select(StoresReceiptLot).where(StoresReceiptLot.id == lot_id,
        StoresReceiptLot.project_id == project.id,
        StoresReceiptLot.organization_id == user.organization_id).with_for_update()).scalar_one()
    reservation = db.execute(select(StoresLotReservation).where(
        StoresLotReservation.id == reservation_id, StoresLotReservation.project_id == project.id,
        StoresLotReservation.organization_id == user.organization_id).with_for_update()).scalar_one()
    previous = db.execute(select(StoresReservationReassignment).where(
        StoresReservationReassignment.project_id == project.id,
        StoresReservationReassignment.action_key == action_key)).scalar_one_or_none()
    if previous:
        if (previous.reservation_id != reservation_id or previous.new_work_package_id != work_package_id
                or previous.new_planning_wbs_id != planning_wbs_id or previous.reason != reason):
            raise HTTPException(409, 'Action key already used for different details')
        return {'reservation_id': reservation_id, 'action_id': previous.id, 'replayed': True}
    if reservation.status != 'Active':
        raise HTTPException(409, 'Only active reservations can be reassigned')
    validate_scope(db, project, work_package_id=work_package_id, planning_wbs_id=planning_wbs_id)
    if reservation.work_package_id == work_package_id and reservation.planning_wbs_id == planning_wbs_id:
        raise HTTPException(409, 'Reservation is already assigned to that work scope')
    action = StoresReservationReassignment(organization_id=user.organization_id, project_id=project.id,
        reservation_id=reservation.id, action_key=action_key,
        old_work_package_id=reservation.work_package_id, new_work_package_id=work_package_id,
        old_planning_wbs_id=reservation.planning_wbs_id, new_planning_wbs_id=planning_wbs_id,
        reason=reason, created_by=user.id)
    db.add(action)
    reservation.work_package_id = work_package_id
    reservation.planning_wbs_id = planning_wbs_id
    db.flush()
    return {'reservation_id': reservation_id, 'action_id': action.id, 'replayed': False}
