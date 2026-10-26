from app.domains.progress_monitoring.alert_rules import evaluate_progress_alerts

def test_variance_severity():
    data={'visibility':'project','exceptions':[],'data_date':'2026-10-19',
          'stages':{'construction':{'percent':42}},
          'planned':[{'period_end':'2026-10-18','planned_percent':55}]}
    assert evaluate_progress_alerts(data,5,10)[0]['severity']=='critical'
    assert evaluate_progress_alerts(data,15,20)==[]

def test_scoped_view_does_not_emit_project_variance():
    data={'visibility':'scoped','exceptions':[],'data_date':'2026-10-19',
          'stages':{'construction':{'percent':20}},
          'planned':[{'period_end':'2026-10-18','planned_percent':90}]}
    assert evaluate_progress_alerts(data)==[]

def test_quality_warnings_never_leak_unlisted_source():
    data={'visibility':'scoped','exceptions':['Missing visible scope']}
    assert evaluate_progress_alerts(data)[0]['type']=='source_quality'
