"""Lightweight source-contract regressions; database integration is tested separately."""
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PARTNER = (BASE/'app/domains/partner_portal/material_issue_requests.py').read_text()
REQUEST = (BASE/'app/domains/stores_inventory/material_requests.py').read_text()


def test_partner_request_company_scope():
    assert 'req.company_id != company_id' in PARTNER
    assert 'WorkPackage.company_id == company_id' in PARTNER
    assert 'StoresMaterialRequest.requester_company_id==company.id' in PARTNER


def test_requirement_work_package_link():
    assert 'WorkPackageRequirement.package_id == wp.id' in PARTNER
    assert 'WorkPackageRequirement.requirement_id == req.id' in PARTNER
    assert "req.status != 'Approved'" in PARTNER


def test_canonical_quantity_lock():
    assert 'with_for_update()' in PARTNER
    assert 'used + data.quantity > Decimal(str(line.quantity))' in PARTNER
    assert 'StoresMaterialRequest.requirement_line_id==line.id' in PARTNER


def test_partner_is_not_stock_issuer():
    assert 'receipt-lots/issue-atomically' not in PARTNER
    assert "row.status='Pending Approval'" in PARTNER
    assert 'allocate_request(' not in PARTNER


def test_shared_requirement_internal_flow_retained():
    assert 'requirement_line_id: int' in REQUEST
    assert "parent.status != 'Approved'" in REQUEST
