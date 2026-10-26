from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'app/domains/stores_inventory/material_requests.py'


def test_policy_reuses_canonical_shared_record_type():
    src = SOURCE.read_text()
    assert "ReminderPolicy.record_type == 'stores.material_request.approval'" in src
    assert "@router.get('/material-requests/approval-escalation-policy')" in src


def test_inactive_and_cross_project_escalation_rejected():
    src = SOURCE.read_text().split('def ensure_material_approval_task(', 1)[1]
    src = src.split("@router.get('/material-requests/approval-escalation-policy')",1)[0]
    assert 'not recipient.active' in src
    assert "permitted(db, recipient, project, 'stores.requests.review')" in src
    assert 'recipient.id == request.created_by' in src


def test_no_inventory_posting_or_new_notification_system():
    src = SOURCE.read_text().split('def material_approval_escalation_policy(', 1)[1]
    src = src.split("@router.get('/material-requests/command-center-approval-summary')",1)[0]
    assert 'configured=policy is not None' in src
    assert 'enabled_for_new_tasks=bool(policy)' in src
    assert 'commit(db)' not in src
