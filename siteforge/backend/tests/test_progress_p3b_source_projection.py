"""Source contract tests; DB and RBAC acceptance must follow against isolated DB."""
import ast
from pathlib import Path

P = Path(__file__).resolve().parents[1] / 'app/domains/progress_monitoring/p3b_source_projection.py'
SRC = P.read_text(encoding='utf8')


def test_parse():
    ast.parse(SRC)


def test_scoped_identity():
    assert 'progress_scope(db, user, project_id)' in SRC
    assert 'organization_id=user.organization_id' in SRC


def test_only_approved_links():
    assert "status='Approved'" in SRC
    assert "qa.status != 'Approved'" in SRC


def test_qa_state_revalidation():
    assert "'Partially Accepted'" in SRC
    assert 'qty > _dec(qa.accepted_quantity)' in SRC


def test_independent_review():
    assert 'link.created_by == link.reviewed_by' in SRC


def test_no_earned_inference():
    assert "'earned_percent': None" in SRC
    assert "'construction_verified_quantity': None" in SRC
    assert "'approved_planning_quantity': None" in SRC


def test_no_source_mutations():
    assert 'db.commit(' not in SRC
    assert 'db.add(' not in SRC
    assert 'db.delete(' not in SRC


def test_error_on_overallocation():
    assert 'accepted > _dec(line.quantity)' in SRC
