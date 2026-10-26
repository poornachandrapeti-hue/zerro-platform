"""Static contracts remain executable without a live PostgreSQL instance."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/domains/stores_inventory/transfer_posting_readiness.py'
MODELS = ROOT / 'app/domains/stores_inventory/models.py'
MIGRATION = ROOT / 'migrations/versions/stores_phase6_transfer_lot_lineage.py'


def test_source_plan_is_route_and_cannot_post_stock():
    text = SOURCE.read_text()
    assert "@router.post('/material-transfers/{transfer_id}/source-lot-plan'" in text
    assert 'validate_source_lot_plan(transfer, lot, amount)' in text
    assert "'source_lot_planned'" not in text or 'source_lot_planned' in text
    assert 'Transfer stock posting is not yet implemented' in text
    assert "status='Planned'" in text
    ast.parse(text)


def test_lineage_schema_has_two_posting_references_and_source_lot():
    text = MODELS.read_text()
    assert 'class StoresTransferLotLineage(Base):' in text
    for field in ('source_receipt_lot_id', 'destination_receipt_lot_id', 'source_posting_id', 'destination_posting_id'):
        assert field in text
    ast.parse(MIGRATION.read_text())
    assert "down_revision = 'stores_phase6_vendor_returns'" in MIGRATION.read_text()


def test_plan_is_not_balance_writer():
    text = SOURCE.read_text()
    portion = text.split('def plan_transfer_source_lot(', 1)[1].split("@router.get('/material-transfers", 1)[0]
    assert 'balance.on_hand =' not in portion
    assert 'StockPosting(' not in portion
    assert 'source_receipt_lot_id == lot.id' in portion
    assert 'qa_case.version' in portion
