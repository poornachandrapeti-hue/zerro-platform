from datetime import date
import pytest
from app.domains.planning_reporting.forecast_engine import preview
from app.domains.planning_reporting.scheduling_engine import ScheduleError

CAL={1:{'working_days':[0,1,2,3,4],'shift_start':'08:00','shift_end':'16:00','holidays':[]}}
ACT=[{'id':1,'code':'A','name':'A','activity_type':'Task','duration_hours':24,'calendar_id':1},
     {'id':2,'code':'B','name':'B','activity_type':'Task','duration_hours':16,'calendar_id':1}]
DEP=[{'predecessor_id':1,'successor_id':2,'relation':'FS','lag_hours':0}]

def test_forecast_remaining_work_chain():
    result=preview(ACT,DEP,CAL,date(2026,10,19),{1:{'completed':False,'remaining_hours':8},2:{'completed':False,'remaining_hours':16}})
    assert result['project_finish'].startswith('2026-10-21')
    assert result['approved_baseline_unchanged']
    assert result['basis']=='UNAPPROVED_FORECAST_PREVIEW_V1'

def test_completed_predecessor_removed_from_remaining_network():
    result=preview(ACT,DEP,CAL,date(2026,10,19),{1:{'completed':True,'remaining_hours':0},2:{'completed':False,'remaining_hours':8}})
    assert result['remaining_activity_count']==1
    assert result['completed_activity_ids']==[1]

def test_missing_inputs_fail_closed():
    with pytest.raises(ScheduleError,match='missing'):
        preview(ACT,DEP,CAL,date(2026,10,19),{1:{'completed':True,'remaining_hours':0}})

def test_unfinished_predecessor_of_completed_activity_rejected():
    with pytest.raises(ScheduleError,match='unfinished predecessor'):
        preview(ACT,DEP,CAL,date(2026,10,19),{1:{'completed':False,'remaining_hours':8},2:{'completed':True,'remaining_hours':0}})

def test_invalid_remaining_duration_rejected():
    with pytest.raises(ScheduleError,match='Positive remaining'):
        preview(ACT,DEP,CAL,date(2026,10,19),{1:{'completed':False,'remaining_hours':0},2:{'completed':False,'remaining_hours':8}})
