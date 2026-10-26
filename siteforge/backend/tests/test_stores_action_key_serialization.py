"""Guard against reintroducing the duplicate-action-key race in Stores handlers."""
import inspect
from app.domains.stores_inventory.lot_reservation_actions import release_reservation
from app.domains.stores_inventory.reservation_work_scope import reassign_reservation


def test_release_action_lock_precedes_row_locks():
    source = inspect.getsource(release_reservation)
    assert "namespace='lot-reservation-release'" in source
    assert source.index('lock_request_key(db,') < source.index('with_for_update()')
    assert source.index('lock_request_key(db,') < source.index('StoresLotReservationAction.action_key == action_key')


def test_reassignment_action_lock_precedes_row_locks():
    source = inspect.getsource(reassign_reservation)
    assert "namespace='lot-reservation-reassignment'" in source
    assert source.index('lock_request_key(db,') < source.index('with_for_update()')
    assert source.index('lock_request_key(db,') < source.index('StoresReservationReassignment.action_key == action_key')
