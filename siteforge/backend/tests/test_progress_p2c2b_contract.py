"""P2C2B contract checks; DB-connected acceptance is a later checkpoint."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'app/domains/progress_monitoring'
SOURCE = (ROOT / 'p2c2_link_router.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)

def test_api_surface():
    functions = {n.name for n in TREE.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert {'propose', 'decide', 'read_link', '_source', '_rights', '_event'} <= functions

def test_independent_reviewer_and_optimistic_version():
    assert 'link.created_by == user.id' in SOURCE
    assert 'link.version != body.version' in SOURCE
    assert "link.status != 'Proposed'" in SOURCE
    assert "link.status != 'Approved'" in SOURCE

def test_scoped_source_readbacks():
    assert 'organization_id=user.organization_id' in SOURCE
    assert 'project_id=pid' in SOURCE
    assert 'activity.company_id != report.company_id' in SOURCE
    assert 'inspection.package_id != activity.package_id' in SOURCE

def test_explicit_role_grants():
    for grant in ('progress.evidence.propose', 'progress.evidence.review', 'progress.evidence.revoke', 'progress.evidence.view'):
        assert grant in SOURCE

def test_append_only_events_and_transaction_lock():
    assert "_event(db, link, 'Proposed', user.id)" in SOURCE
    assert '_event(db, link, status, user.id, link.review_note)' in SOURCE
    assert 'pg_advisory_xact_lock' in SOURCE

def test_no_derived_ledger_write():
    assert 'earned_progress' in SOURCE and 'billing_certified' in SOURCE
    assert "'earned_progress': False" in SOURCE
    assert "'billing_certified': False" in SOURCE
