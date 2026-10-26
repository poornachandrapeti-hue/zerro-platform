from datetime import date
import pytest
from pydantic import ValidationError
from app.domains.planning_reporting.workspace_router import CalendarInput, ActivityInput, ScheduleInput

def test_calendar_rejects_invalid_time_zone_and_days():
    with pytest.raises(ValidationError): CalendarInput(code='DAY',name='Day',timezone='Not/AZone')
    with pytest.raises(ValidationError): CalendarInput(code='DAY',name='Day',working_days=[0,0])
    with pytest.raises(ValidationError): CalendarInput(code='DAY',name='Day',shift_start='08:00',shift_end='08:00')

def test_activity_rejects_invalid_or_ambiguous_values():
    base=dict(code='A01',name='Pour foundations',wbs_id=1,calendar_id=1,company_id=1)
    with pytest.raises(ValidationError): ActivityInput(**base)
    with pytest.raises(ValidationError): ActivityInput(**base,duration_hours=8,source_type='construction')
    with pytest.raises(ValidationError): ActivityInput(**base,duration_hours=8,planned_start=date(2026,10,18),planned_finish=date(2026,10,17))

def test_schedule_type_validation():
    with pytest.raises(ValidationError): ScheduleInput(name='Base',kind='Fake',version='1',data_date=date.today(),calendar_id=1)
