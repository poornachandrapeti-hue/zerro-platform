from pathlib import Path
import ast
import types

# Test pure validation without importing the backend/database dependencies.
p = Path(__file__).resolve().parents[1] / "app/domains/stores_inventory/lot_balance_review.py"
tree = ast.parse(p.read_text())
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "review_lot")
ns = {"Decimal": __import__("decimal").Decimal}
dec_fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "dec")
exec(compile(ast.Module(body=[dec_fn, fn], type_ignores=[]), str(p), "exec"), ns)
review = ns["review_lot"]

def test_multiple_lots_never_inherit_line_qa():
    data = review(5, 5, 10, 10, 2, 0, 0, 0, 0)
    assert "QA_NOT_ATTRIBUTED_TO_INDIVIDUAL_LOT" in data["flags"]
    assert data["lot_issue_enabled"] is False
    assert data["available_to_issue"] is None

def test_partial_posting_not_releasable():
    data = review(10, 4, 10, 10, 1, 0, 0, 0, 6)
    assert "POSTING_PROVENANCE_INCOMPLETE" in data["flags"]
    assert "RECEIPT_POSTING_NOT_FULLY_ALLOCATED" in data["flags"]

def test_simple_fully_mapped_still_not_issue_enabled():
    data = review(10, 10, 10, 10, 1, 0, 0, 0, 0)
    assert data["ledger_migration_ready"] is True
    assert data["lot_issue_enabled"] is False
    assert data["physical_on_hand"] is None

def test_quality_and_expiry_block_readiness():
    data = review(10, 10, 7, 10, 1, 0, 3, 0, 0, True)
    assert "QA_NOT_FULLY_ACCEPTED" in data["flags"]
    assert "EXPIRED" in data["flags"]
