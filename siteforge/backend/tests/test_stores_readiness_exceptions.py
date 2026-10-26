from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import ast
source = (Path(__file__).resolve().parents[1] / 'app/domains/stores_inventory/material_requests.py').read_text()
node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'material_readiness_blockers')
exec(compile(ast.Module(body=[node], type_ignores=[]), '<isolated>', 'exec'), {'Decimal': Decimal, 'date': date}, namespace := {})
f = namespace['material_readiness_blockers']

def test_no_unverified_available_stock():
    flags=f(demand_quantity='100',active_reserved='40', issued_quantity='20', required_date=date.today()+timedelta(days=10), po_commitments=[])
    assert 'QA_CLEARANCE_NOT_VERIFIED' in flags
    assert 'LOT_STOCK_BALANCE_NOT_VERIFIED' in flags
    assert 'APPROVED_REQUEST_NOT_FULLY_ALLOCATED' in flags

def test_delivery_after_need():
    flags=f(demand_quantity=100,active_reserved=100,issued_quantity=0,required_date=date.today()+timedelta(days=2),po_commitments=[{'promised_date':(date.today()+timedelta(days=5)).isoformat()}])
    assert 'PO_PROMISES_AFTER_MATERIAL_REQUIRED_DATE' in flags
    assert 'PO_DELIVERY_NOT_VERIFIED' in flags

def test_invalid_overallocation():
    flags=f(demand_quantity=10,active_reserved=8,issued_quantity=5,required_date=date.today()+timedelta(days=1),po_commitments=[])
    assert 'ALLOCATION_DATA_REVIEW_REQUIRED' in flags
