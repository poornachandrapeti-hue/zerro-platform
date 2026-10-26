"""Source contract checks; live database integration required before operational use."""
from pathlib import Path
from datetime import date
import ast
src = Path(__file__).resolve().parents[1] / 'app/domains/stores_inventory/material_requests.py'
tree = ast.parse(src.read_text())
names = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

def test_joins_are_defined():
    assert 'linked_procurement_commitments' in names
    assert 'schedule_alignment' in names

def test_readiness_reports_commitments_but_not_verified_stock():
    text = src.read_text()
    assert 'linked_purchase_orders=commitments' in text
    assert 'eta_verified=False' in text
    assert "overall_readiness='Unverified'" in text
    assert 'qa_eligible_stock_verified=False' in text

def test_no_inventory_write_in_readiness():
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'work_package_readiness')
    fragment = ast.get_source_segment(src.read_text(), fn)
    assert 'db.commit(' not in fragment and 'db.flush(' not in fragment

def test_ownership_and_scope():
    text=src.read_text()
    assert 'PurchaseOrder.organization_id == organization_id' in text
    assert 'PurchaseRequisition.project_id == project_id' in text
