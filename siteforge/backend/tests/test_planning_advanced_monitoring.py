from app.domains.planning_reporting.advanced_monitoring import summarize

def test_criticality_and_milestone_late():
    base=[{'code':'A','name':'Civil','critical':True},{'code':'M','name':'Milestone','critical':False}]
    forecast=[{'code':'A','critical':False,'finish':'2026-10-30'},{'code':'M','critical':True,'finish':'2026-11-15'}]
    milestone=[{'activity_code':'M','activity_name':'Handover','baseline_finish':'2026-11-10','variance_status':'actual_not_available'}]
    r=summarize(base,forecast,milestone,'2026-10-18')
    assert len(r['criticality_changes'])==2
    assert r['milestone_risks'][0]['difference_calendar_days']==5
    assert r['milestone_risks'][0]['risk_status']=='forecast_later_than_baseline'

def test_missing_forecast_not_zero_or_estimated():
    r=summarize([{'code':'M','critical':True}],[],[{'activity_code':'M','baseline_finish':'2026-10-01','completion_status':'incomplete'}],'2026-10-18')
    assert r['unmatched_baseline_activity_count']==1
    assert r['milestone_risks'][0]['forecast_finish'] is None
    assert r['milestone_risks'][0]['risk_status']=='past_baseline_at_forecast_data_date'

def test_approved_actual_excluded_from_risks():
    r=summarize([],[],[{'activity_code':'M','actual_finish':'2026-10-01'}])
    assert not r['milestone_risks']

def test_duplicate_codes_not_compared():
    r=summarize([{'code':'A','critical':True},{'code':'A','critical':False}], [{'code':'A','critical':True}],[])
    assert r['criticality_changes']==[]
    assert r['duplicate_activity_codes']==['A']
