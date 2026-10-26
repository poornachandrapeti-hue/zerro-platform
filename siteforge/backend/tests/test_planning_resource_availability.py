from datetime import date
from types import SimpleNamespace
from app.domains.planning_reporting.resource_availability import capacity_evidence,mobilization_summary

DAY=date(2026,10,18)
def test_capacity_remains_unverified_even_with_reference():
    d=SimpleNamespace(id=1,activity_id=4,resource_type='Workforce',resource_name='Welders',period_start=date(2026,10,1),period_end=date(2026,10,31),confirmed_capacity=10,capacity_source='planning-ref',demand_quantity=12,demand_unit='headcount')
    r=capacity_evidence([d],as_of=DAY)[0]
    assert r['planning_capacity_value']==10
    assert r['capacity_evidence_status']=='planner-referenced-unverified'
    assert not r['available_for_automatic_scheduling']
def test_missing_capacity_stays_missing():
    d=SimpleNamespace(id=1,activity_id=4,resource_type='Equipment',resource_name='Crane',period_start=DAY,period_end=DAY,confirmed_capacity=None,capacity_source='',demand_quantity=1,demand_unit='units')
    assert capacity_evidence([d],as_of=DAY)[0]['capacity_evidence_status']=='missing'
def test_mobilization_does_not_count_proposed_or_duplicate():
    def dep(person,status='Mobilized'):
        return SimpleNamespace(personnel_id=person,status=status,company_id=8,discipline_id=2,actual_start=date(2026,10,1),actual_end=None)
    r=mobilization_summary([dep(1),dep(1),dep(2),dep(3,'Proposed')],as_of=DAY)
    assert r[0]['mobilized_personnel_count']==2
    assert r[0]['capacity_status']=='indicative-mobilization-only'
