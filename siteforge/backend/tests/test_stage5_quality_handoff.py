"""Regression checks for explicit, guarded Quality-to-Stores handoff."""
from pathlib import Path


def test_handoff_endpoint_preserves_stock_and_lot_boundaries():
    source = Path(__file__).parents[1] / "app/domains/stores_inventory/router.py"
    text = source.read_text()
    block = text.split('def reconcile_approved_quality_case(', 1)[1]
    assert 'quality_handoff' in block
    assert 'Quality Revoked' in block
    assert 'Existing Stores decisions require manual reconciliation' in block
    assert 'stock_posted": False' in block
    assert 'lot_release_enabled": False' in block

def test_handoff_has_explicit_quality_and_version_gates():
    source = Path(__file__).parents[1] / "app/domains/stores_inventory/router.py"
    block = source.read_text().split('def reconcile_approved_quality_case(', 1)[1]
    assert 'case.version != expected_version' in block
    assert '_totals(db, receipt_line_id)' in block
    assert 'Outstanding Quality inspection prevents handoff' in block
