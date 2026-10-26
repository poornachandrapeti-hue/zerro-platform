from datetime import date, timedelta
from app.domains.planning_reporting.productivity_history import summarize_daily_lines


def test_approved_only_rework_excluded_and_reversal():
    today=date(2026,10,18)
    rows=[(today-timedelta(days=3),10,False,False,'MT',True),
          (today-timedelta(days=2),5,False,False,'MT',True),
          (today-timedelta(days=2),2,True,False,'MT',True),
          (today-timedelta(days=1),100,False,False,'MT',False),
          (today,99,False,True,'MT',True)]
    result=summarize_daily_lines(rows,'MT',today,28)
    assert result['status']=='observed'
    assert result['net_verified_quantity']==13
    assert result['observed_days']==2
    assert result['sample_coverage']=='limited_sample'


def test_unit_mismatch_is_unavailable():
    assert summarize_daily_lines([(date(2026,10,18),1,False,False,'kg',True)],'MT',date(2026,10,18))['status']=='unavailable'


def test_no_approved_data_is_insufficient():
    assert summarize_daily_lines([(date(2026,10,18),2,False,False,'MT',False)],'MT',date(2026,10,18))['status']=='insufficient_data'


def test_broader_coverage_not_probability():
    end=date(2026,10,18)
    rows=[(end-timedelta(days=i*3),5,False,False,'MT',True) for i in range(6)]
    result=summarize_daily_lines(rows,'MT',end)
    assert result['sample_coverage']=='broader_sample'
    assert result['net_verified_quantity']==30
