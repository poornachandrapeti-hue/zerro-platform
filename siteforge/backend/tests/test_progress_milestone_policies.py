from types import SimpleNamespace
from app.domains.progress_monitoring.milestone_policy import validate_policy,approved_result
def test_weight_validation():
    assert not validate_policy('engineering',{'prepared':30,'released':70})
    assert validate_policy('engineering',{'prepared':30,'released':60})
    assert validate_policy('procurement',{'ordered':40,'received':60})
def test_approved_earned_requires_scope_baseline_and_policy():
    p=SimpleNamespace(stage='engineering',status='Approved',version=1,planning_publication_id=8)
    prev={'preview_percent':65,'errors':[]}
    assert approved_result(prev,p,True,8)['earned_percent']==65
    assert approved_result(prev,p,False,8)['earned_percent'] is None
    assert approved_result(prev,p,True,9)['earned_percent'] is None
    assert approved_result(prev,None,True,8)['earned_percent'] is None
def test_procurement_earning_requires_validated_acceptance():
    p=SimpleNamespace(stage='procurement',status='Approved',version=1,planning_publication_id=8)
    assert approved_result({'preview_percent':80,'errors':[]},p,True,8)['earned_percent']==80
    assert approved_result({'preview_percent':None,'errors':['Acceptance incomplete']},p,True,8)['earned_percent'] is None
