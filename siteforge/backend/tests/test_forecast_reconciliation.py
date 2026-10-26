from datetime import date
from app.domains.planning_reporting.forecast_reconciliation import reconcile, finish_variance

def test_conflicting_completion_states():
    inputs=[{'activity_id':1,'completed':True},{'activity_id':2,'completed':False}]
    records=[{'activity_id':1,'activity_code':'A','link_status':'linked','measurement':{'verified_percent':65}},
             {'activity_id':2,'activity_code':'B','link_status':'linked','measurement':{'verified_percent':100}}]
    r=reconcile(inputs,records)
    assert r['counts']['planner_complete_but_source_incomplete']==1
    assert r['counts']['source_complete_but_planner_unfinished']==1
    assert r['as_of_forecast_data_date'] is False

def test_missing_measurements_are_not_zero():
    r=reconcile([{'activity_id':6,'completed':False}],[])
    assert r['activities'][0]['verified_percent_current'] is None
    assert r['counts']['unavailable']==1

def test_calendar_day_variance():
    assert finish_variance('2026-12-24','2026-12-15')['variance_days']==9
    assert finish_variance(None,'2026-12-15')['variance_days'] is None
