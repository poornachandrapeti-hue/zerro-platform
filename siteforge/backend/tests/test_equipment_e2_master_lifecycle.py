from datetime import date
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.domains.planning_reporting.equipment_router import MasterUpdate
from app.domains.planning_reporting.equipment_master_rules import master_view, validate_master_transition

BASE=dict(ownership_type='Owned',operating_condition='Serviceable',tracking_mode='Individual',quantity=1,reason='Asset metadata reviewed')

def make(**kwargs):return MasterUpdate(**{**BASE,**kwargs})

def test_standard_metadata_and_dates():
    result=make(make='CAT',model='320',mobilized_on=date(2026,1,1),demobilized_on=date(2026,2,1))
    assert result.make=='CAT'

def test_hired_equipment_requires_reference():
    with pytest.raises(ValidationError,match='hire contract'):make(ownership_type='Hired')
    assert make(ownership_type='Hired',hire_contract_ref='HIRE-100').hire_contract_ref=='HIRE-100'

def test_demobilization_date_rejects_invalid_sequence():
    with pytest.raises(ValidationError,match='Mobilization'):make(demobilized_on=date(2026,3,1))
    with pytest.raises(ValidationError,match='Demobilization'):make(mobilized_on=date(2026,4,1),demobilized_on=date(2026,3,1))

def test_individual_asset_is_one_unit():
    with pytest.raises(ValidationError,match='quantity 1'):make(quantity=2)
    assert make(tracking_mode='QuantityManaged',quantity=5).quantity==5

def test_quantity_managed_pool_cannot_claim_serial():
    with pytest.raises(ValidationError,match='serial number'):make(tracking_mode='QuantityManaged',quantity=4,serial_number='SER-1')

def test_readback_uses_serializable_dates():
    a=SimpleNamespace(id=2,asset_code='EX-2',mobilized_on=date(2026,1,1))
    assert master_view(a)['mobilized_on']=='2026-01-01'

class Query:
    def __init__(self,has_match):self.has_match=has_match
    def filter_by(self,**kwargs):return self
    def first(self):return object() if self.has_match else None
class Session:
    def __init__(self,match):self.match=match
    def query(self,model):return Query(self.match)

def asset():
    return SimpleNamespace(id=1,organization_id=9,tracking_mode='Individual',quantity=1,
                           operating_condition='Serviceable',mobilized_on=None,demobilized_on=None)

def test_active_booking_blocks_lifecycle_changes():
    with pytest.raises(HTTPException) as ex:
        validate_master_transition(asset(),{'operating_condition':'UnderRepair'},Session(True),9)
    assert ex.value.status_code==409

def test_unbooked_asset_can_change_lifecycle():
    validate_master_transition(asset(),{'operating_condition':'UnderRepair'},Session(False),9)

def test_asset_cannot_switch_to_pool_when_allocated():
    with pytest.raises(HTTPException) as ex:
        validate_master_transition(asset(),{'tracking_mode':'QuantityManaged'},Session(True),9)
    assert ex.value.status_code == 409

def test_cross_org_master_update_rejected():
    with pytest.raises(HTTPException) as ex:
        validate_master_transition(asset(),{'make':'New'},Session(False),99)
    assert ex.value.status_code==403

def test_tool_quantity_cannot_be_edited_without_custody_ledger():
    a=asset();a.tracking_mode='QuantityManaged';a.quantity=5
    with pytest.raises(HTTPException) as ex:
        validate_master_transition(a,{'tracking_mode':'QuantityManaged','quantity':9},Session(False),9)
    assert ex.value.status_code==409

def test_restricted_equipment_is_not_confirmable():
    from app.domains.planning_reporting.equipment_rules import can_confirm
    a=asset();a.inspection_review_status='Verified';a.status='Active';a.inspection_evidence_ref='CERT-2';a.inspection_valid_through=date(2027,2,1)
    a.operating_condition='UnderRepair'
    allocation=SimpleNamespace(resource_type='Equipment',resource_ref='equipment:1',organization_id=9,
        starts_at=__import__('datetime').datetime(2026,11,1,tzinfo=__import__('datetime').timezone.utc),
        ends_at=__import__('datetime').datetime(2026,11,2,tzinfo=__import__('datetime').timezone.utc),status='Reviewed')
    ok,reason=can_confirm(a,allocation)
    assert not ok and 'condition' in reason

def test_quantity_managed_assets_cannot_be_reserved_as_unique_assets():
    from app.domains.planning_reporting.equipment_rules import can_confirm
    a=asset();a.inspection_review_status='Verified';a.status='Active';a.inspection_evidence_ref='CERT-2';a.inspection_valid_through=date(2027,2,1)
    a.tracking_mode='QuantityManaged'
    allocation=SimpleNamespace(resource_type='Equipment',resource_ref='equipment:1',organization_id=9,
        starts_at=__import__('datetime').datetime(2026,11,1,tzinfo=__import__('datetime').timezone.utc),
        ends_at=__import__('datetime').datetime(2026,11,2,tzinfo=__import__('datetime').timezone.utc),status='Reviewed')
    ok,reason=can_confirm(a,allocation)
    assert not ok and 'quantity' in reason.lower()
