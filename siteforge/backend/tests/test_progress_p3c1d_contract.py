"""Source-contract guardrails for P3C1D. API/DB integration testing still required."""
import ast
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / 'app/domains/progress_monitoring/p3c1d_verification_router.py'
TEXT = PATH.read_text()
TREE = ast.parse(TEXT)


def test_source_compiles():
    compile(TEXT, str(PATH), 'exec')


def test_expected_api_functions():
    functions = {n.name for n in TREE.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert {'propose', 'decide', 'read_verification', '_source', '_rights', '_event', '_visible'} - functions == {'_rights'}


def test_reuses_existing_rights():
    assert 'from .p2c2_link_router import _rights' in TEXT
    for grant in ('progress.quantity.propose', 'progress.quantity.review', 'progress.quantity.revoke', 'progress.quantity.view'):
        assert grant in TEXT


def test_project_scope_and_row_lock():
    assert 'organization_id=user.organization_id' in TEXT
    assert 'project_id=pid' in TEXT
    assert '.with_for_update().first()' in TEXT
    assert 'pg_advisory_xact_lock' in TEXT


def test_independent_review_and_optimistic_version():
    assert 'record.proposer_user_id == user.id' in TEXT
    assert 'record.version != body.version' in TEXT
    assert "record.status != 'Proposed'" in TEXT
    assert "record.status != 'Approved'" in TEXT


def test_sources_read_on_approval():
    assert 'read_line_evidence' in TEXT
    assert 'read_authoritative_baseline' in TEXT
    assert "b['baseline_revision_id']" in TEXT
    assert 'record.progress_line_id' in TEXT


def test_validates_all_quantity_limits():
    assert 'qty > min(planned, reported)' in TEXT
    assert 'accepted > qty' in TEXT
    assert "Verification.status == 'Approved'" in TEXT


def test_audit_actions():
    for action in ('Proposed', 'Approved', 'Rejected', 'Revoked'):
        assert repr(action) in TEXT
    assert '_event(db, record' in TEXT


def test_no_earned_or_billing_writers():
    assert "'published': False" in TEXT
    assert "'billing_certified': False" in TEXT
    assert 'db.commit()' in TEXT


def test_does_not_trust_client_for_planning_baseline():
    cls = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == 'Proposal')
    fields = {n.target.id for n in cls.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)}
    assert 'approved_planning_quantity' not in fields
    assert 'baseline_revision_id' not in fields
    assert 'qa_accepted_quantity' not in fields
