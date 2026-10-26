from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
API=(ROOT/'app/domains/stores_inventory/stock_adjustments.py').read_text()
MODEL=(ROOT/'app/domains/stores_inventory/models.py').read_text()
MIG=(ROOT/'migrations/versions/stores_phase7_adjustment_requests.py').read_text()

def test_adjustment_routes():
    assert "'/stock-adjustment-requests'" in API
    assert "'/stock-adjustment-requests/{rid}/review'" in API

def test_count_must_be_independently_verified():
    assert "count.status!='Verified'" in API
    assert 'count.verified_by' in API

def test_approval_is_not_offered():
    assert "('Reject','RequestRecount','RecordReview')" in API
    assert "'authorized_for_posting': False" in API

def test_no_stock_posting_from_adjustment_service():
    assert 'StockPosting(' not in API
    assert 'StockBalance(' not in API

def test_one_model_migration_chain():
    assert 'class StoresStockAdjustmentRequest' in MODEL
    assert "down_revision='stores_phase7_cycle_counts'" in MIG
