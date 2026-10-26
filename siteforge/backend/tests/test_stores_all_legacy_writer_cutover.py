"""Fail-closed regression checks for legacy stock writer cutover."""
import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "app/domains/supply_chain/stock.py"
TREE = ast.parse(SRC.read_text())
WRITERS = ("accept_receipt", "reserve_stock", "issue_stock", "return_stock", "cancel_posting")

def test_every_legacy_writer_checks_cutover_first():
    functions = {n.name:n for n in TREE.body if isinstance(n, ast.FunctionDef)}
    for name in WRITERS:
        fn=functions[name]
        assert isinstance(fn.body[0], ast.Expr), name
        first=fn.body[0].value
        assert isinstance(first, ast.Call), name
        assert isinstance(first.func, ast.Name) and first.func.id == "_require_legacy_writer_enabled", name

def test_cutover_gate_fails_closed():
    functions = {n.name:n for n in TREE.body if isinstance(n, ast.FunctionDef)}
    guard=functions["_require_legacy_writer_enabled"]
    assert any(isinstance(n, ast.Raise) for n in ast.walk(guard))
    assert "STORES_LOT_WRITER_CUTOVER" in ast.get_source_segment(SRC.read_text(), guard)

def test_no_new_balances_or_ledgers_created():
    assert not any(isinstance(n, ast.ClassDef) and n.name in ("StockBalance", "StockPosting") for n in TREE.body)
