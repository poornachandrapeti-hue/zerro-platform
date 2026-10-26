"""Source-level gate; full database transaction checks remain deferred."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'app/domains/stores_inventory/vendor_returns.py').read_text()
MODEL = (ROOT / 'app/domains/stores_inventory/models.py').read_text()
MAIN = (ROOT / 'app/main.py').read_text()
MIGRATION = (ROOT / 'migrations/versions/stores_phase6_vendor_returns.py').read_text()

def test_vendor_returns_mounted():
    assert 'app.include_router(stores_vendor_returns_router)' in MAIN
    assert 'class StoresVendorReturn(Base)' in MODEL
    assert "down_revision = 'stores_phase6_custody_companies'" in MIGRATION

def test_workflow_and_version_guard():
    for route in ('/vendor-returns', '/vendor-returns/{rid}/decision', '/vendor-returns/{rid}/dispatch',
                  '/vendor-returns/{rid}/vendor-acknowledgment', '/vendor-returns/{rid}/replacement'):
        assert route in SOURCE
    assert 'with_for_update()' in SOURCE
    assert 'r.version != version' in SOURCE
    assert 'Creator cannot approve own return' in SOURCE

def test_no_duplicate_inventory_posting():
    assert 'StockPosting' not in SOURCE and 'StockBalance' not in SOURCE
    assert 'inventory_posted=False' in SOURCE
    assert 'replacement_stock_verified=False' in SOURCE

def test_po_item_vendor_validation():
    assert 'PurchaseOrderLine.item_id == data.item_id' in SOURCE
    assert 'PurchaseOrder.vendor_id == data.vendor_id' in SOURCE
    assert 'Warehouse.project_id == pid' in SOURCE
