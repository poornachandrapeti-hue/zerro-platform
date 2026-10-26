from types import SimpleNamespace as NS
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.domains.contracts.models import Contract
from app.domains.stores_inventory.models import StoresMaterialRequest
from app.domains.supply_chain.models import MaterialRequirement, RequirementLine
from app.domains.planning_reporting.equipment_e7_authority_readback import read_hire_contract_authority, read_spares_request_authority

class FakeDB:
    def __init__(self, values): self.values=values
    def get(self, typ, ident): return self.values.get((typ,ident))

def contract(**kw):
    data=dict(id=1,organization_id=5,project_id=12,number='HIRE-01',approval_state='Approved',published_version=2,lifecycle='Active',currency='INR',effective_at=None,expires_at=None)
    data.update(kw); return NS(**data)

def test_contract_verified_but_rate_not_assumed():
    result=read_hire_contract_authority(FakeDB({(Contract,1):contract()}),contract_id=1,org_id=5,project_id=12)
    assert result['source']=='Contracts' and result['hire_rate_verified'] is False and result['finance_posted'] is False
    assert result['version']==2

@pytest.mark.parametrize('change', [{'project_id':99},{'approval_state':'Pending'}, {'published_version':None},{'currency':None},{'lifecycle':'Terminated'}])
def test_contract_fails_closed(change):
    with pytest.raises(HTTPException): read_hire_contract_authority(FakeDB({(Contract,1):contract(**change)}),contract_id=1,org_id=5,project_id=12)

def request(**kw):
    data=dict(id=3,organization_id=5,project_id=12,status='Approved',requirement_line_id=4,item_id=7,base_unit='Nos',requested_quantity=Decimal('2'),request_key='SP-3',work_package_id=8)
    data.update(kw);return NS(**data)
def line(**kw):
    data=dict(id=4,requirement_id=6,item_id=7,unit='Nos',quantity=Decimal('3'))
    data.update(kw);return NS(**data)
def header(**kw):
    data=dict(id=6,organization_id=5,project_id=12,status='Approved',impact_state='')
    data.update(kw);return NS(**data)
def db(r=None,l=None,h=None):
    return FakeDB({(StoresMaterialRequest,3):r or request(), (RequirementLine,4):l or line(), (MaterialRequirement,6):h or header()})

def test_stores_traceback_does_not_post_stock():
    x=read_spares_request_authority(db(),request_id=3,org_id=5,project_id=12)
    assert x['requirement_line_id']==4 and x['stores_request_id']==3
    assert x['stock_posted'] is False and x['remaining_stock_authorized'] is False

@pytest.mark.parametrize('mut', [lambda:db(r=request(status='Draft')),lambda:db(r=request(project_id=9)),lambda:db(r=request(item_id=8)),lambda:db(r=request(requested_quantity=Decimal('4'))),lambda:db(h=header(status='Pending')),lambda:db(h=header(impact_state='Review required')),lambda:db(l=line(unit='Kg'))])
def test_stores_fail_closed(mut):
    with pytest.raises(HTTPException):read_spares_request_authority(mut(),request_id=3,org_id=5,project_id=12)
