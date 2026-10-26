from types import SimpleNamespace as Obj
from datetime import date
import pytest
from fastapi import HTTPException
from app.domains.planning_reporting.equipment_maintenance_rules import start_work_order, advance_work_order, may_start_equipment

def asset(**changes):
    obj={'status':'Active','tracking_mode':'Individual','operating_condition':'Serviceable'}
    obj.update(changes)
    return Obj(**obj)

def order(**changes):
    obj={'status':'Reported','created_by':1,'repair_completed_by':None,'repair_evidence_ref':None}
    obj.update(changes)
    return Obj(**obj)

def test_preventive_requires_due_date():
    with pytest.raises(HTTPException):start_work_order(asset(),'Preventive')
    start_work_order(asset(),'Preventive',date(2027,1,2))

def test_breakdown_blocked_if_asset_already_held():
    with pytest.raises(HTTPException):start_work_order(asset(operating_condition='UnderRepair'),'Breakdown')

def test_quantity_pool_requires_individual_identification():
    with pytest.raises(HTTPException):start_work_order(asset(tracking_mode='QuantityManaged'),'Breakdown')

def test_transition_must_be_ordered():
    with pytest.raises(HTTPException):advance_work_order(order(),'Released',9,'release-proof')
    assert advance_work_order(order(),'InRepair',9,'repair-proof')=='InRepair'

def test_independent_release_reviewer():
    w=order(status='RepairComplete',repair_completed_by=2,repair_evidence_ref='fixed-proof')
    for reviewer in (1,2):
        with pytest.raises(HTTPException) as error:advance_work_order(w,'Released',reviewer,'verify-proof')
        assert error.value.status_code==403
    assert advance_work_order(w,'Released',3,'verify-proof')=='Released'

def test_no_missing_repair_evidence():
    with pytest.raises(HTTPException):advance_work_order(order(status='RepairComplete'),'Released',4,'proof')

def test_unreleased_order_prohibits_start():
    assert not may_start_equipment(asset(),[order(status='RepairComplete')])
    assert not may_start_equipment(asset(operating_condition='Restricted'),[])
    assert may_start_equipment(asset(),[order(status='Released')])
