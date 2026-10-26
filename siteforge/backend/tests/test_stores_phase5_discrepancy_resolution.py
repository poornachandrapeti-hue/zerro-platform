from types import SimpleNamespace
from fastapi import HTTPException
import pytest
from app.domains.stores_inventory.material_handovers import ResolveDiscrepancyIn, validate_resolution

def test_independent_review_success():
    row=SimpleNamespace(status='Discrepancy',version=2,dispatched_by=1,acknowledged_by=2)
    validate_resolution(row,3,ResolveDiscrepancyIn(version=2,decision='Resolved',evidence='Verified replacement delivery'))

@pytest.mark.parametrize('status,version,reviewer', [('Acknowledged',2,3),('Resolved',2,3),('Discrepancy',3,3),('Discrepancy',2,1),('Discrepancy',2,2)])
def test_reject_invalid_review(status,version,reviewer):
    row=SimpleNamespace(status=status,version=version,dispatched_by=1,acknowledged_by=2)
    with pytest.raises(HTTPException): validate_resolution(row,reviewer,ResolveDiscrepancyIn(version=2,decision='Resolved',evidence='Verified resolution'))

def test_no_ledger_fields_in_resolution():
    from app.domains.stores_inventory.models import StoresMaterialHandover
    assert hasattr(StoresMaterialHandover, 'resolution_note')
    assert not hasattr(StoresMaterialHandover, 'on_hand')
    with pytest.raises(Exception): ResolveDiscrepancyIn(version=1,decision='Stock Adjusted',evidence='x')

def test_partner_route_company_scope():
    import inspect
    from app.domains.partner_portal.material_issue_requests import partner_material_handovers, partner_acknowledge_handover
    source=inspect.getsource(partner_material_handovers)
    assert 'requester_company_id == company.id' in source
    assert 'created_by == u.id' in source
    source=inspect.getsource(partner_acknowledge_handover)
    assert 'requester_company_id == company.id' in source
    assert 'classify_discrepancy' in source
