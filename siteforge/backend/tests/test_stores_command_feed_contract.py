from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'app/domains/stores_inventory/material_requests.py'

def test_feed_is_service_authenticated():
    text = SOURCE.read_text()
    fn = text.split('def internal_stores_approval_workload(', 1)[1]
    assert "settings.command_center_identity_service_key" in fn
    assert 'hmac.compare_digest' in fn
    assert 'if not expected or not' in fn
    assert "HTTPException(403" in fn

def test_feed_scopes_org_and_project():
    text = SOURCE.read_text().split('def internal_stores_approval_workload(', 1)[1]
    assert 'StoresMaterialRequest.project_id == pid' in text
    assert 'StoresMaterialRequest.organization_id == project.organization_id' in text
    assert 'Task.organization_id == project.organization_id' in text

def test_feed_never_claims_ready_stock():
    text = SOURCE.read_text().split('def internal_stores_approval_workload(', 1)[1]
    assert "'physical_stock_readiness': 'Unverified'" in text
    assert "'inventory_available_quantity': None" in text
    assert "'verified_shortage_quantity': None" in text
    assert 'db.add(' not in text
    assert 'commit(db)' not in text
