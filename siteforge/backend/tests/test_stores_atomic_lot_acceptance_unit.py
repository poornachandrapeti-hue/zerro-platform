import ast
from pathlib import Path
from fastapi import HTTPException
import pytest
from app.domains.stores_inventory.atomic_lot_acceptance import _checked_qty

@pytest.mark.parametrize('input_value', ['0', '-1', '1.0001', 'NaN', 'Infinity', 'abc'])
def test_quantity_rejected(input_value):
    with pytest.raises(HTTPException):
        _checked_qty(input_value)

def test_quantity_accepted():
    assert str(_checked_qty('1.250')) == '1.250'

def test_atomic_service_has_no_commit_or_independent_stock_ledger():
    p = Path(__file__).parents[1] / 'app/domains/stores_inventory/atomic_lot_acceptance.py'
    tree = ast.parse(p.read_text())
    names = [n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)]
    assert 'commit' not in names
    assert 'StockPostingLine' in p.read_text()
    assert 'StoresPostingLotAllocation' in p.read_text()
