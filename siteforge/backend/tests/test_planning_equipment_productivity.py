from datetime import date
from app.domains.planning_reporting.equipment_productivity import calculate_equipment_productivity

END=date(2026,10,18)
def row(i=1,q=10,h=2,approved=True,rework=False,reversal=False,unit='MT',day=END):
    return (i,day,q,unit,approved,rework,reversal,h)

def test_observed_rate_and_no_double_count():
    x=calculate_equipment_productivity([row(),row(2,20,4)],'MT',END)
    assert x['status']=='observed' and x['net_eligible_quantity']==30
    assert x['allocated_equipment_hours']==6 and x['quantity_per_equipment_hour']==5

def test_missing_hours_blocks_rate():
    assert calculate_equipment_productivity([row(h=None)],'MT',END)['status']=='insufficient_data'

def test_unapproved_and_rework_excluded():
    x=calculate_equipment_productivity([row(),row(2,100,1,False),row(3,100,1,True,True)],'MT',END)
    assert x['net_eligible_quantity']==10

def test_unit_mismatch_refused():
    assert calculate_equipment_productivity([row(unit='m3')],'MT',END)['status']=='unavailable'

def test_duplicate_line_refused():
    assert calculate_equipment_productivity([row(),row()],'MT',END)['status']=='unavailable'

def test_no_positive_equipment_hours_refused():
    assert calculate_equipment_productivity([row(h=0)],'MT',END)['status']=='insufficient_data'

def test_empty_observations():
    assert calculate_equipment_productivity([],'MT',END)['status']=='insufficient_data'
