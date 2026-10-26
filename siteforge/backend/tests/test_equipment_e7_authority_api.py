from types import SimpleNamespace as NS
import pytest
from fastapi import HTTPException
from app.domains.planning_reporting import equipment_e7_authority_api as api
from app.domains.planning_reporting.workspace_models import PlanningEquipmentAsset

class DB:
    def __init__(self, asset): self.asset=asset
    def get(self, cls, pk):
        return self.asset if cls is PlanningEquipmentAsset and pk == 7 else None

def asset(**kw):
    x=dict(id=7,organization_id=3,project_id=5,ownership_type='Hired',hire_contract_ref='HI-1')
    x.update(kw)
    return NS(**x)

@pytest.fixture(autouse=True)
def scope(monkeypatch):
    monkeypatch.setattr(api,'equipment_access',lambda db,user,pid: None)

def user(org=3): return NS(organization_id=org)

def test_hire_readback_scoped_and_unposted(monkeypatch):
    monkeypatch.setattr(api,'read_hire_contract_authority',lambda *args,**kw: {'reference':'HI-1','hire_rate_verified':False})
    result=api.verify_hire_contract(5,7,20,user(),DB(asset()))
    assert result['handoff_created'] is False and result['finance_posted'] is False
    assert result['authority']['hire_rate_verified'] is False

def test_contract_reference_mismatch_blocks(monkeypatch):
    monkeypatch.setattr(api,'read_hire_contract_authority',lambda *args,**kw: {'reference':'DIFFERENT'})
    with pytest.raises(HTTPException) as exc: api.verify_hire_contract(5,7,20,user(),DB(asset()))
    assert exc.value.status_code == 409

@pytest.mark.parametrize('candidate', [asset(project_id=6),asset(organization_id=99),None])
def test_scope_refuses_wrong_asset(candidate):
    with pytest.raises(HTTPException) as exc: api.verify_spares_request(5,7,1,user(),DB(candidate))
    assert exc.value.status_code == 404

def test_unprivileged_user_is_blocked(monkeypatch):
    def deny(*args): raise HTTPException(403,'Denied')
    monkeypatch.setattr(api,'equipment_access',deny)
    with pytest.raises(HTTPException) as exc: api.verify_spares_request(5,7,1,user(),DB(asset()))
    assert exc.value.status_code == 403

def test_non_hired_asset_rejected():
    with pytest.raises(HTTPException) as exc: api.verify_hire_contract(5,7,1,user(),DB(asset(ownership_type='Owned')))
    assert exc.value.status_code == 409

def test_spares_readback_no_ledger_write(monkeypatch):
    monkeypatch.setattr(api,'read_spares_request_authority',lambda *args,**kw:{'stores_request_id':11,'stock_posted':False})
    result=api.verify_spares_request(5,7,11,user(),DB(asset()))
    assert result['authority']['stores_request_id']==11
    assert result['handoff_created'] is False and result['stock_posted'] is False

def test_authority_readback_failure_propagated(monkeypatch):
    def blocked(*args,**kw): raise HTTPException(409,'Unapproved')
    monkeypatch.setattr(api,'read_spares_request_authority',blocked)
    with pytest.raises(HTTPException) as exc: api.verify_spares_request(5,7,11,user(),DB(asset()))
    assert exc.value.status_code==409
