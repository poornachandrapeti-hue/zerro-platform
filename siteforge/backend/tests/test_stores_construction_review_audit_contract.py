"""Audit actions must remain part of the same transaction as controlled QA review transitions."""
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / 'app/domains/stores_inventory/qa_issued_impact.py').read_text()


def _body(name):
    return SOURCE.split(f'def {name}(', 1)[1].split('\n@router.', 1)[0]


def test_created_tasks_emit_audit_with_case_and_package_scope():
    body = _body('create_construction_review_tasks')
    assert "'create_construction_impact_review'" in body
    assert "'work_package_id': package_id" in body
    assert "'inspection_case_id': case_id" in body
    assert body.index("'create_construction_impact_review'") < body.index('db.commit()')


def test_acknowledgment_audit_is_atomic_with_status_update():
    body = _body('acknowledge_construction_impact')
    assert "'acknowledge_construction_impact'" in body
    assert body.index("task.status = 'In Progress'") < body.index("'acknowledge_construction_impact'") < body.index('db.commit()')
    assert "'impact_scope_verified': False" in body


def test_qa_verification_audit_identifies_independent_reviewer():
    body = _body('verify_construction_impact')
    assert "'verify_construction_impact'" in body
    assert "'qa_reviewer_id': u.id" in body
    assert body.index("task.status = 'Completed'") < body.index("'verify_construction_impact'") < body.index('db.commit()')
