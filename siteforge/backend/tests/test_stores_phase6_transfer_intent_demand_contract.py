"""Source contract gate for transfer intent's mandatory canonical-demand binding."""
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'app/domains/stores_inventory/transfer_allocation_preview.py'


def test_transfer_intent_requires_canonical_request():
    source = SOURCE.read_text()
    assert 'material_request_id: int = Field(gt=0)' in source
    assert "request.status != 'Approved'" in source
    assert 'require_issue_authorization(db,' in source
    assert 'material_request_id=request.id, requirement_line_id=request.requirement_line_id' in source


def test_intents_cannot_double_allocate_and_never_reserve_stock():
    source = SOURCE.read_text()
    assert 'Transfer intent quantities exceed destination lot quantity' in source
    assert 'Transfer intent exceeds approved Stores request quantity' in source
    assert "status='PendingActivation'" in source
    assert "'stock_reserved': False" in source
    assert 'StockBalance.reserved' in source
