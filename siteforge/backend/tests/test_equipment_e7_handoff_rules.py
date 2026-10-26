from datetime import datetime, timezone, timedelta
from types import SimpleNamespace as NS
import pytest
from fastapi import HTTPException
from app.domains.planning_reporting.equipment_e7_handoff_rules import validate_hire_handoff, validate_spares_handoff

T=datetime(2026,11,1,tzinfo=timezone.utc)
asset=NS(id=7, organization_id=1, project_id=11, ownership_type='Hired', hire_contract_ref='H-20')
contract=NS(organization_id=1, project_id=11, reference='H-20', status='Approved', starts_at=T, ends_at=T+timedelta(days=30), currency='INR', approved_rate='1250.00')
req=NS(organization_id=1, project_id=11, reference='REQ-9', status='Approved', remaining_quantity='4.000')

def hire(**overrides):
    args=dict(asset=asset,contract=contract,org_id=1,project_id=11,period_start=T,period_end=T+timedelta(days=1),rate='1250.00',currency='INR',evidence_ref='signed ticket',request_key='hire-1')
    args.update(overrides)
    return validate_hire_handoff(**args)

def spares(**overrides):
    args=dict(asset=asset, stores_requirement=req,org_id=1,project_id=11,quantity='2',request_key='spare-1')
    args.update(overrides)
    return validate_spares_handoff(**args)

def test_hire_is_unposted_and_traceable():
    result=hire()
    assert result['status']=='UnpostedProposal' and result['posting_verified'] is False
    assert result['contract_ref']=='H-20' and result['approved_rate']=='1250.00'

@pytest.mark.parametrize('change', [
    {'asset':NS(**{**asset.__dict__,'ownership_type':'Owned'})},
    {'asset':NS(**{**asset.__dict__,'hire_contract_ref':'OTHER'})},
    {'contract':NS(**{**contract.__dict__,'status':'Draft'})},
    {'contract':NS(**{**contract.__dict__,'project_id':99})},
    {'period_end':T}, {'period_end':T+timedelta(days=40)},
    {'currency':'USD'}, {'rate':'1250.01'}, {'rate':'NaN'},
    {'evidence_ref':''}, {'request_key':''},
])
def test_hire_rejects_invalid_authority(change):
    with pytest.raises(HTTPException): hire(**change)

def test_spares_are_only_linked_not_issued():
    result=spares()
    assert result['stock_posted'] is False and result['quantity']=='2'
    assert result['stores_requirement_ref']=='REQ-9'

@pytest.mark.parametrize('change', [
    {'stores_requirement':NS(**{**req.__dict__,'status':'Pending'})},
    {'stores_requirement':NS(**{**req.__dict__,'organization_id':2})},
    {'stores_requirement':NS(**{**req.__dict__,'project_id':44})},
    {'quantity':'0'}, {'quantity':'5'}, {'quantity':'NaN'},
    {'quantity':'0.0001'}, {'request_key':''},
])
def test_spares_rejects_invalid_authority(change):
    with pytest.raises(HTTPException): spares(**change)
