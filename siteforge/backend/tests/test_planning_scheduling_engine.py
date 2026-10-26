from datetime import date, datetime
import pytest
from app.domains.planning_reporting.scheduling_engine import calculate, ScheduleError, add_work

CAL={1:{'working_days':[0,1,2,3,4],'shift_start':'08:00','shift_end':'16:00','holidays':[]}}
def act(i,hours=8,kind='Task'):
    return dict(id=i,code=f'T-{i}',name=f'Task {i}',calendar_id=1,activity_type=kind,duration_hours=hours)
def dep(p,s,r='FS',lag=0):return dict(predecessor_id=p,successor_id=s,relation=r,lag_hours=lag)

def test_fs_chain_skips_weekend():
    r=calculate([act(1),act(2)],[dep(1,2)],CAL,date(2026,10,23))
    a=r['activities'];assert a[0]['start']=='2026-10-23T08:00'
    assert a[1]['start']=='2026-10-26T08:00' and all(x['critical'] for x in a)

def test_relationships_and_lag():
    for relationship in ('FS','SS','FF','SF'):
        r=calculate([act(1,16),act(2,8)],[dep(1,2,relationship,2)],CAL,date(2026,10,19))
        x,y=r['activities']
        assert x['start']<=y['finish']
        assert r['project_finish']

def test_cycle_and_negative_lag_blocked():
    with pytest.raises(ScheduleError,match='Circular'):
        calculate([act(1),act(2)],[dep(1,2),dep(2,1)],CAL,date(2026,10,19))
    with pytest.raises(ScheduleError,match='negative'):
        calculate([act(1),act(2)],[dep(1,2,lag=-1)],CAL,date(2026,10,19))

def test_holiday_skipped():
    cal={1:{**CAL[1],'holidays':['2026-10-20']}}
    r=calculate([act(1,16)],[],cal,date(2026,10,19))
    assert r['activities'][0]['finish']=='2026-10-21T16:00'

def test_overnight_shift():
    cal={'working_days':[0,1,2,3,4],'shift_start':'20:00','shift_end':'04:00','holidays':[]}
    assert add_work(datetime(2026,10,19,20),8,cal)==datetime(2026,10,20,4)
