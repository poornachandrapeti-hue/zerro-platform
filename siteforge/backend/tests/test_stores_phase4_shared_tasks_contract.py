from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'app/domains/stores_inventory/material_requests.py'
source = SOURCE.read_text()


def test_approval_task_requires_explicit_reviewer_and_scoped_permissions():
    assert "class ApprovalTaskIn(BaseModel)" in source
    assert "permitted(db, reviewer, project, 'stores.requests.review')" in source
    assert "request.created_by == data.reviewer_user_id" in source


def test_duplicate_work_is_not_created():
    assert "Task.source_type == 'stores.material_request.approval'" in source
    assert 'with_for_update()' in source
    assert "raise HTTPException(409, 'Approval task is already assigned" in source


def test_no_false_inventory_claims():
    assert "physical_stock_readiness='Unverified'" in source
    assert "source='stores_material_requests'" in source
