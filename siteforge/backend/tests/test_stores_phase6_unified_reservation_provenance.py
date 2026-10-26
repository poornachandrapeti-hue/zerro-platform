"""Phase 6 source contracts: unified provenance is non-posting until activation."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
MODELS = (ROOT / 'app/domains/stores_inventory/models.py').read_text()
API = (ROOT / 'app/domains/stores_inventory/transfer_allocation_preview.py').read_text()
MIGRATION = (ROOT / 'migrations/versions/stores_phase6_unified_reservation_source.py').read_text()


def test_schema_exclusive_lot_source():
    assert 'ck_stores_reservation_exactly_one_lot' in MODELS
    assert 'transfer_destination_lot_id' in MODELS
    assert 'nullable=True' in MIGRATION


def test_pending_intents_do_not_change_stock():
    fn = ast.parse(API)
    route = next(n for n in fn.body if isinstance(n, ast.FunctionDef) and n.name == 'create_transfer_reservation_intent')
    code = ast.get_source_segment(API, route)
    assert "status='PendingActivation'" in code
    assert 'balance.reserved =' not in code
    assert "'stock_reserved': False" in code


def test_legacy_writers_restrict_to_active_grn():
    for filename in ('atomic_lot_issue.py', 'lot_reservation_actions.py'):
        content = (ROOT / 'app/domains/stores_inventory' / filename).read_text()
        assert 'receipt_lot_id' in content
        assert 'Active' in content


def test_migration_chains_from_destination_lots():
    assert "down_revision = 'stores_phase6_transfer_destination_lots'" in MIGRATION
    assert 'op.create_check_constraint' in MIGRATION
