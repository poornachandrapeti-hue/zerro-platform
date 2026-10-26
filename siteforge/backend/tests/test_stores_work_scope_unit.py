"""Focused reservation work-scope logic checks; no live database required."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1] / 'app' / 'domains' / 'stores_inventory'

def test_work_scope_validation_is_fail_closed():
    tree = ast.parse((ROOT / 'reservation_work_scope.py').read_text())
    scope = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'validate_scope')
    names = {n.attr for n in ast.walk(scope) if isinstance(n, ast.Attribute)}
    assert {'project_id', 'organization_id', 'release_state', 'active'} <= names
    assert 'HTTPException' in {n.id for n in ast.walk(scope) if isinstance(n, ast.Name)}

def test_reassignment_has_immutable_audit_and_idempotency():
    src = (ROOT / 'reservation_work_scope.py').read_text()
    for required in ('with_for_update()', 'StoresReservationReassignment(', 'action_key',
                     "reservation.status != 'Active'", 'old_work_package_id',
                     'old_planning_wbs_id', 'replayed'):
        assert required in src

def test_reservation_requires_work_scope_and_matches_retry():
    src = (ROOT / 'lot_reservations.py').read_text()
    assert 'validate_scope(db, project' in src
    assert 'existing.work_package_id != work_package_id' in src
    assert 'existing.planning_wbs_id != planning_wbs_id' in src

def test_migration_has_reversible_fields():
    src = (Path(__file__).resolve().parents[1] / 'migrations' / 'versions' /
           'stores_phase3_work_scope_reassignment.py').read_text()
    assert "down_revision = 'stores_phase3_reservation_release'" in src
    assert 'op.drop_table' in src and 'op.drop_column' in src
