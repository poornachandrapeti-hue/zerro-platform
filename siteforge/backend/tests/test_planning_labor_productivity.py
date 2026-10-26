from datetime import date
from app.domains.planning_reporting.labor_productivity import calculate_labor_productivity

DAY=date(2026,10,17)
def line(i=1,qty=10,mins=120,approved=True,rework=False,reversal=False,unit='MT'):
    return (i,DAY,qty,unit,approved,rework,reversal,mins,0)

def test_labor_rate_and_no_duplicate_quantities():
    records=[line(mins=120),(1,DAY,10,'MT',True,False,False,60,30)]
    r=calculate_labor_productivity(records,'MT',DAY)
    assert r['status']=='observed' and r['net_eligible_quantity']==10
    assert r['productive_labor_hours']==3

def test_missing_labor_does_not_claim_rate():
    r=calculate_labor_productivity([line(),line(i=2,mins=None)],'MT',DAY)
    assert r['status']=='insufficient_data'

def test_excludes_rework_and_unapproved():
    r=calculate_labor_productivity([line(),line(i=2,rework=True),line(i=3,approved=False)],'MT',DAY)
    assert r['net_eligible_quantity']==10

def test_wrong_unit_rejected():
    assert calculate_labor_productivity([line(unit='m3')],'MT',DAY)['status']=='unavailable'

def test_empty():
    assert calculate_labor_productivity([],'MT',DAY)['status']=='insufficient_data'
