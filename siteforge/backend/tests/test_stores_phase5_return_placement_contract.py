from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SOURCE = (BASE/'app/domains/stores_inventory/material_returns.py').read_text()
MODEL = (BASE/'app/domains/stores_inventory/models.py').read_text()
UI = (BASE.parent/'frontend/src/stores.tsx').read_text()

def test_return_bin_is_not_second_stock_ledger():
    assert "def set_return_placement" in SOURCE
    section = SOURCE.split('def set_return_placement', 1)[1].split('@router.get', 1)[0]
    assert 'balance.on_hand' not in section
    assert "record.return_location_id = location.id" in section

def test_only_active_original_warehouse_bin():
    assert 'location.location_type != \'Bin\'' in SOURCE
    assert 'location.warehouse_id != warehouse_id' in SOURCE
    assert "_return_source_warehouse(db, pid, u.organization_id, record)" in SOURCE

def test_posting_requires_location_and_remains_gated():
    assert "_require_return_posting_gate()" in SOURCE
    assert "if r.return_location_id is None" in SOURCE
    assert 'return_location_id:' in MODEL

def test_ui_reconciliation_and_placement():
    assert '/material-returns/reconciliation' in UI
    assert '/placement' in UI
    assert 'Post return (feature-gated)' in UI
