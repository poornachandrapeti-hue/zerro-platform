from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / 'app/domains/stores_inventory/cycle_counts.py').read_text()
MODELS = (ROOT / 'app/domains/stores_inventory/models.py').read_text()


def test_lifecycle_endpoints_and_independent_reviewer():
    for endpoint in ("'/cycle-counts'", "'/cycle-counts/{count_id}/lines'", "'/cycle-counts/{count_id}/submit'", "'/cycle-counts/{count_id}/review'"):
        assert endpoint in API
    assert 'Independent reviewer required' in API
    assert "count.status='Verified'" in API
    assert "count.status='Submitted'" in API


def test_non_posting_and_provenance_warning():
    assert 'stock_adjustment_posted=False' in API
    assert 'not a validated on-hand stock snapshot' in API
    assert 'StockBalance(' not in API and 'StockPosting(' not in API


def test_project_and_warehouse_scope():
    assert 'StoresReceiptLot.warehouse_id==count.warehouse_id' in API
    assert 'StoresCycleCount.organization_id == org' in API
    assert 'StoresCycleCount.project_id == pid' in API


def test_models_unique_and_migration():
    assert "uq_stores_cycle_count_ref" in MODELS
    assert "uq_stores_cycle_count_lot" in MODELS
    text=(ROOT/'migrations/versions/stores_phase7_cycle_counts.py').read_text()
    assert "down_revision = 'stores_phase7_preservation'" in text
