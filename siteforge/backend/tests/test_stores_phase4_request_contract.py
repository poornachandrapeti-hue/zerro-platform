import ast
from decimal import Decimal
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / 'app/domains/stores_inventory'


def test_shortfall_never_negative():
    tree = ast.parse((BASE / 'material_requests.py').read_text())
    method = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'shortage')
    scope = {'Decimal': Decimal}
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<shortage>', 'exec'), scope)
    assert scope['shortage']('12.000', '5.000') == Decimal('7.000')
    assert scope['shortage']('12.000', '20.000') == Decimal('0')


def test_review_is_maker_checker_and_versioned():
    body = (BASE / 'material_requests.py').read_text()
    assert "row.created_by == u.id" in body
    assert "row.version != data.version" in body
    assert "row.status != 'Pending Approval'" in body


def test_requests_never_call_physical_posting():
    body = (BASE / 'material_requests.py').read_text()
    for forbidden in ('_post_issue(', '_post_receipt(', '_lock_balance(', 'reserve_lot('):
        assert forbidden not in body


def test_migration_follows_previous_checkpoint():
    migration = Path(__file__).resolve().parents[1] / 'migrations/versions/stores_phase4_material_requests.py'
    assert "down_revision = 'stores_phase3_work_scope_reassignment'" in migration.read_text()
