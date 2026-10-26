from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from app.domains.stores_inventory.phase8_planning_readiness import planning_exception_flags


def test_planning_flags_dont_claim_physical_shortage():
    today = date(2026, 10, 24)
    flags = planning_exception_flags(required_date=today + timedelta(days=3),
        planned_start=today + timedelta(days=1), request_status='Approved',
        allocation_blockers=['APPROVED_REQUEST_NOT_FULLY_ALLOCATED'], po_commitments=[{'promised_date':'2026-10-31'}], today=today)
    assert 'MATERIAL_REQUIRED_AFTER_WORK_PACKAGE_START' in flags
    assert 'ALL_PO_PROMISES_AFTER_REQUIRED_DATE' in flags
    assert 'DEMAND_ALLOCATION_INCOMPLETE' in flags
    assert all('STOCK_SHORTAGE' not in x for x in flags)


def test_unapproved_unplanned_without_po():
    today = date(2026, 10, 24)
    flags = planning_exception_flags(required_date=today, planned_start=None,
        request_status='Pending Approval', allocation_blockers=[], po_commitments=[], today=today)
    assert {'STORES_REQUEST_NOT_APPROVED', 'WORK_PACKAGE_START_NOT_PLANNED',
            'NO_LINKED_PROCUREMENT_COMMITMENT'} <= set(flags)


def test_router_mounted_and_advisory():
    main = (Path(__file__).parents[1] / 'app/main.py').read_text()
    source = (Path(__file__).parents[1] / 'app/domains/stores_inventory/phase8_planning_readiness.py').read_text()
    assert 'app.include_router(stores_phase8_planning_readiness_router)' in main
    assert "physical_stock_readiness='Unverified'" in source
    assert 'construction_progress_credited=False' in source
