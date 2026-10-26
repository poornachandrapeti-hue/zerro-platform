"""Phase 6 discrepancy and UI contract tests; no live DB required."""
from pathlib import Path
import inspect
from app.domains.stores_inventory import transfers
from app.domains.stores_inventory.models import StoresTransfer


def test_review_is_independent_and_versioned():
    src = inspect.getsource(transfers.resolve_transfer_discrepancy)
    assert 'r.version != data.version' in src
    assert 'r.received_by' in src and 'r.dispatched_by' in src
    assert "('Resolved', 'Escalated')" in src
    assert "audit(db, u, 'review_transfer_discrepancy'" in src


def test_transfer_discrepancy_route_and_fields():
    assert hasattr(StoresTransfer, 'discrepancy_status')
    assert hasattr(StoresTransfer, 'discrepancy_resolved_by')
    assert any(r.path.endswith('/resolve-discrepancy') for r in transfers.router.routes)


def test_custody_only_and_new_ui():
    src = inspect.getsource(transfers)
    assert 'StockPosting(' not in src
    assert 'StockBalance(' not in src
    ui = Path(__file__).resolve().parents[2] / 'frontend/src/stores.tsx'
    contents = ui.read_text()
    for value in ('Material Transfers', 'submitTransfer', 'advanceTransfer', 'resolve-discrepancy', 'Confirm receipt'):
        assert value in contents
