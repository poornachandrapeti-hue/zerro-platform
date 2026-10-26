from datetime import date,timedelta
from types import SimpleNamespace as N
import pytest
from fastapi import HTTPException
from app.domains.planning_reporting.equipment_custody_rules import available_quantity,validate_issue,validate_return

def asset(**kw):
    args=dict(id=7,status='Active',operating_condition='Serviceable',demobilized_on=None,
        inspection_review_status='Verified',inspection_valid_through=date.today()+timedelta(days=15),tracking_mode='Individual')
    args.update(kw);return N(**args)

def err(f,*args):
    with pytest.raises(HTTPException) as info:f(*args)
    assert info.value.status_code==409

def test_individual_confirmed_allocation():
    validate_issue(asset(),1,N(status='EquipmentConfirmed',resource_ref='equipment:7',resource_type='Equipment'))
    err(validate_issue,asset(),1,None)
    err(validate_issue,asset(),2,N(status='EquipmentConfirmed',resource_ref='equipment:7',resource_type='Equipment'))
    err(validate_issue,asset(),1,N(status='Proposed',resource_ref='equipment:7',resource_type='Equipment'))
    err(validate_issue,asset(),1,N(status='EquipmentConfirmed',resource_ref='equipment:8',resource_type='Equipment'))

def test_condition_and_inspection_holds():
    for variant in [dict(operating_condition='Restricted'),dict(operating_condition='UnderRepair'),
                    dict(inspection_review_status='Pending'),dict(inspection_valid_through=date.today()-timedelta(days=1)),
                    dict(status='Inactive'),dict(demobilized_on=date.today())]:
        err(validate_issue,asset(**variant),1,N(status='EquipmentConfirmed',resource_ref='equipment:7',resource_type='Equipment'))

def test_pool_issue_and_running_quantity():
    validate_issue(asset(tracking_mode='QuantityManaged'),3,None)
    events=[N(action='Issue',quantity=3),N(action='Return',quantity=1)]
    assert available_quantity(5,events)==3
    err(available_quantity,1,events+[N(action='Return',quantity=3)])

def test_return_parent_and_quantity():
    issue=N(id=13,action='Issue',asset_id=7,project_id=2,quantity=5)
    history=[N(action='Return',parent_issue_id=13,quantity=2)]
    assert validate_return(issue,history,3,7,2)==0
    err(validate_return,issue,history,4,7,2)
    err(validate_return,issue,history,1,7,3)
    err(validate_return,issue,history,1,8,2)
