from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'app' / 'domains'


def test_impact_review_requires_separate_ack_and_qa_verify():
    source = (ROOT / 'stores_inventory' / 'qa_issued_impact.py').read_text()
    assert '/acknowledge' in source and '/qa-verify' in source
    assert "if task.owner_id != u.id:" in source
    assert "if task.owner_id == u.id:" in source
    assert "task.status = 'In Progress'" in source
    assert "task.status = 'Completed'" in source


def test_qa_resolution_requires_current_revocation_and_acknowledgment():
    source = (ROOT / 'stores_inventory' / 'qa_issued_impact.py').read_text()
    assert "case.status != 'Quality Revoked'" in source
    assert "task.evidence.startswith('Construction acknowledgment: ')" in source
    assert source.count('task.version != data.task_version') == 2
    assert "'impact_scope_verified': False" in source


def test_shared_task_endpoint_cannot_bypass_qa_verification():
    source = (ROOT / 'coordination' / 'service.py').read_text()
    assert 'task.source_type in ("stores.qa_revocation.construction_review", "stores.material_return.exception_review")' in source
    assert 'Use Construction acknowledgment and independent QA verification workflow' in source


def test_acknowledgment_locks_and_rechecks_revoked_case_before_task():
    source = (ROOT / 'stores_inventory' / 'qa_issued_impact.py').read_text()
    body = source.split('def acknowledge_construction_impact(', 1)[1].split("@router.post('/inspection-cases/", 1)[0]
    assert 'db.query(StoresInspectionCase)' in body
    assert '.with_for_update().first()' in body
    assert "case.status != 'Quality Revoked'" in body
    assert body.index('db.query(StoresInspectionCase)') < body.index('task = _impact_task(')
    assert body.index("case.status != 'Quality Revoked'") < body.index("task.status = 'In Progress'")
