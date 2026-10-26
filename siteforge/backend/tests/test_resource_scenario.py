import importlib.util
from pathlib import Path

location=Path(__file__).resolve().parents[1]/'app/domains/planning_reporting/resource_scenario.py'
spec=importlib.util.spec_from_file_location('resource_scenario',location)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

SOURCE={'link_status':'linked','measurement':{'unit':'MT','scope_quantity':100,'verified_quantity':60}}

def test_dual_constraint_labor_limits():
    r=m.resource_scenario(SOURCE,unit='MT',labor_rate=.1,workers=5,labor_hours_per_worker_day=8,
        equipment_rate=2,equipment_count=1,equipment_hours_per_unit_day=8)
    assert r['status']=='scenario' and r['estimated_working_days']==10
    assert r['limiting_resource']=='labor'

def test_equipment_limits():
    r=m.resource_scenario(SOURCE,unit='MT',labor_rate=1,workers=5,labor_hours_per_worker_day=8,
        equipment_rate=.5,equipment_count=1,equipment_hours_per_unit_day=8)
    assert r['limiting_resource']=='equipment' and r['estimated_working_days']==10

def test_requires_complete_constraints():
    assert m.resource_scenario(SOURCE,unit='MT',labor_rate=1)['status']=='unavailable'

def test_wrong_unit_denied():
    assert m.resource_scenario(SOURCE,unit='m3',labor_rate=1,workers=1,labor_hours_per_worker_day=8)['status']=='unavailable'

def test_missing_quantity_denied():
    s={'link_status':'linked','measurement':{'unit':'MT','scope_quantity':100}}
    assert m.resource_scenario(s,unit='MT',labor_rate=1,workers=1,labor_hours_per_worker_day=8)['status']=='unavailable'

def test_zero_remaining():
    s={'link_status':'linked','measurement':{'unit':'MT','scope_quantity':100,'verified_quantity':100}}
    assert m.resource_scenario(s,unit='MT',equipment_rate=2,equipment_count=1,equipment_hours_per_unit_day=8)['estimated_working_days']==0

def test_no_constraints_denied():
    assert m.resource_scenario(SOURCE,unit='MT')['status']=='unavailable'
