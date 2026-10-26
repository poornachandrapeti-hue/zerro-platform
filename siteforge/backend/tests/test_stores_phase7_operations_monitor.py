from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'app/domains/stores_inventory/phase7_monitor.py'
UI=ROOT.parent/'frontend/src/stores.tsx'
MAIN=ROOT/'app/main.py'

def test_monitor_separates_four_workflows():
    s=MODULE.read_text()
    for model in ('StoresPreservationPlan','StoresCycleCount','StoresStockAdjustmentRequest','StoresScrapCase'):
        assert model in s
    assert "'preservation_uncovered_lots': None" in s
    assert "'physical_stock_readiness': 'Unverified'" in s

def test_command_center_service_authentication_and_project_scope():
    s=MODULE.read_text()
    assert 'hmac.compare_digest' in s
    assert 'X-ZerroR-Service-Key' in s
    assert 'db.get(Project,pid)' in s
    assert 'project.organization_id' in s

def test_monitor_read_only_and_bounded():
    s=MODULE.read_text()
    assert 'limit(LIMIT)' in s
    assert 'db.add(' not in s and 'commit(' not in s and 'db.delete(' not in s
    assert "'stock_written_off': False" in s

def test_router_and_dashboard_mounted():
    assert 'app.include_router(stores_phase7_monitor_router)' in MAIN.read_text()
    s=UI.read_text()
    assert 'Phase 7 Operations' in s
    assert 'phase7/operations-monitor' in s
    assert 'physical stock readiness is unverified' in s.lower()
