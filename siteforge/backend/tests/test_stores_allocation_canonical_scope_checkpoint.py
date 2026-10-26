"""Source-level regression gates for canonical Procurement line allocation."""
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'app/domains/stores_inventory/request_allocation.py'


def test_fail_closed_against_changed_canonical_line():
    source = SOURCE.read_text()
    assert 'req_line.item_id != request.item_id' in source
    assert 'req_line.unit != request.base_unit' in source
    assert 'req_line.planning_wbs_id != request.planning_wbs_id' in source
    assert 'Canonical requirement line no longer matches material allocation scope' in source


def test_invalid_numeric_quantities_do_not_reach_reservation():
    source = SOURCE.read_text()
    assert 'not qty.is_finite()' in source
    assert 'Decimal(str(req_line.quantity)).is_finite()' in source


def test_existing_ledger_and_reservation_writer_remain_authoritative():
    source = SOURCE.read_text()
    assert 'reserve_lot(db, user, project,' in source
    assert 'reservation.material_request_id = request.id' in source
    assert 'db.flush()' in source
