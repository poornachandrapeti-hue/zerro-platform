from app.domains.planning_reporting.bulk_import_router import validate_dependencies, validate_calendars

def test_dependencies_valid_and_cycle_stage():
    errors,rows=validate_dependencies([(2,{'predecessor_code':'A','successor_code':'B','relation':'FS','lag_hours':0})],{'A':1,'B':2},set())
    assert not errors and rows[0]['predecessor_id']==1
    errors,_=validate_dependencies([(3,{'predecessor_code':'A','successor_code':'B','relation':'FS','lag_hours':-1})],{'A':1,'B':2},set())
    assert errors

def test_calendars_duplicate_and_invalid():
    row={'calendar_code':'NEW','calendar_name':'Site','timezone':'Asia/Kolkata','working_days':'0,1,2,3,4,5','shift_start':'08:00','shift_end':'17:00','holidays':''}
    errors,ready=validate_calendars([(2,row)],set())
    assert not errors and ready[0]['working_days']==[0,1,2,3,4,5]
    errors,_=validate_calendars([(2,row)],{'NEW'})
    assert errors
