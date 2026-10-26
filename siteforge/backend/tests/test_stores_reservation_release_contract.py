"""Static guard tests; live SQL locking needs PostgreSQL integration coverage."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def test_release_is_gated_and_committed_by_router():
    service = (ROOT / 'app/domains/stores_inventory/lot_reservation_actions.py').read_text()
    router = (ROOT / 'app/domains/stores_inventory/router.py').read_text()
    assert '_enabled()' in service
    assert "@router.post('/receipt-lots/reservations/release')" in router
    assert 'commit(db)' in router.split("@router.post('/receipt-lots/reservations/release')", 1)[1]


def test_release_keeps_physical_stock_unchanged():
    service = (ROOT / 'app/domains/stores_inventory/lot_reservation_actions.py').read_text()
    assert 'balance.reserved = ' in service
    assert 'balance.on_hand =' not in service
    assert 'with_for_update()' in service
    assert 'action_key == action_key' in service


def test_migration_preserves_unique_action_key():
    migration = (ROOT / 'migrations/versions/stores_phase3_reservation_release.py').read_text()
    assert "down_revision = 'stores_phase3_lot_reservations'" in migration
    assert 'uq_stores_reservation_action_key' in migration
