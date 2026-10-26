from app.domains.progress_monitoring.stage_scheme import validate_weights, calculate_overall

def test_approved_complete_epc():
    weights={'engineering':2000,'procurement':3000,'construction':5000}
    stage={k:{'percent':p,'status':'approved_earned_progress'} for k,p in [('engineering',50),('procurement',80),('construction',20)]}
    assert calculate_overall(weights,stage,scheme_approved=True,full_scope=True,baseline_matches=True)['percent']==44.0
def test_no_ready_proxy():
    w={'engineering':2000,'procurement':3000,'construction':5000}
    rows={k:{'percent':90,'status':'readiness_only'} for k in w}
    assert calculate_overall(w,rows,scheme_approved=True,full_scope=True,baseline_matches=True)['percent'] is None
def test_scoped_or_unapproved():
    w={'engineering':2000,'procurement':3000,'construction':5000}
    rows={k:{'percent':50,'status':'approved_earned_progress'} for k in w}
    assert calculate_overall(w,rows,scheme_approved=True,full_scope=False,baseline_matches=True)['percent'] is None
    assert calculate_overall(w,rows,scheme_approved=False,full_scope=True,baseline_matches=True)['percent'] is None
def test_invalid_weights():
    assert validate_weights({'engineering':5000,'procurement':2000,'construction':2000})
    assert validate_weights({'engineering':5000,'procurement':3000,'construction':2000,'quality':0})
    assert validate_weights({'construction':10000})
