from pathlib import Path

P = Path(__file__).resolve().parents[1] / 'app/domains/stores_inventory/material_requests.py'
S = P.read_text()

def test_approval_task_closed_inside_review_transaction():
    block = S.split('def review_request(',1)[1].split('@router.get',1)[0]
    assert "_close_tasks(db, pid, 'stores.material_request.approval'" in block
    assert block.index('_close_tasks(') < block.index('commit(db)')
    assert 'validate_partner_review_scope(db, row, parent)' in block
    assert 'row.created_by == u.id' in block

def test_no_stock_writes_or_ready_claim_in_task_summary():
    block = S.split('def material_request_task_status(',1)[1]
    assert "physical_stock_readiness='Unverified'" in block
    assert 'Task.project_id == pid' in block
    assert 'Task.organization_id == u.organization_id' in block
    assert "action='stores.requests.view'" in block
    assert 'stock_posting' not in block

def test_shared_task_framework_handles_closure():
    helper = (P.parents[1] / 'coordination/service.py').read_text()
    assert 'def _close_tasks(' in helper
    assert 'if task.status in OPEN:' in helper
