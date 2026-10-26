"""Phase 3 transaction preparation regression checks (no live database)."""
import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'app/domains/stores_inventory/lot_transaction_boundary.py'


def test_stock_balance_and_lot_are_locked():
    content = SOURCE.read_text()
    assert content.count('.with_for_update()') == 2
    assert 'StockBalance.organization_id == organization_id' in content
    assert 'StoresReceiptLot.organization_id == organization_id' in content


def test_receipt_provenance_is_verified():
    content = SOURCE.read_text()
    assert '_receipt_item(db, receipt_line)' in content
    assert 'receipt_item.id != item_id' in content
    assert 'receipt_unit != balance.unit' in content


def test_boundary_has_no_posting_side_effect():
    tree = ast.parse(SOURCE.read_text())
    calls = [node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
    assert not set(calls).intersection({'commit', 'add', 'delete', 'flush'})


def test_scope_filters_and_no_mutations():
    content = SOURCE.read_text()
    assert 'StockBalance.project_id == project_id' in content
    assert 'StoresReceiptLot.project_id == project_id' in content
    assert 'StockBalance.warehouse_id == warehouse_id' in content
    assert 'StoresReceiptLot.warehouse_id == warehouse_id' in content
