from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from app.domains.planning_reporting.resource_coverage import coverage

START=datetime(2026,10,20,8,tzinfo=timezone.utc)
END=START+timedelta(hours=8)

def booking(kind,status,start=START,end=END,aid=7):
    return SimpleNamespace(activity_id=aid,resource_type=kind,status=status,starts_at=start,ends_at=end)

def test_full_equipment_booking():
    r=coverage(7,START,END,[booking('Equipment','EquipmentConfirmed')])
    assert r['equipment']['covers_entire_window'] is True
    assert r['workforce']['status']=='UNMAPPED'

def test_planning_review_not_confirmation():
    r=coverage(7,START,END,[booking('Workforce','Reviewed')])
    assert r['workforce']['status']=='NO_CONFIRMED_COVERAGE'

def test_partial_booking():
    r=coverage(7,START,END,[booking('Equipment','EquipmentConfirmed',START,START+timedelta(hours=4))])
    assert r['equipment']['status']=='PARTIAL_CONFIRMED_COVERAGE'

def test_adjacent_confirmed_windows_cover():
    mid=START+timedelta(hours=4)
    r=coverage(7,START,END,[booking('Workforce','HRConfirmed',START,mid),booking('Workforce','HRConfirmed',mid,END)])
    assert r['workforce']['covers_entire_window'] and r['workforce']['capacity_confirmed'] is False

def test_other_activity_does_not_count():
    r=coverage(7,START,END,[booking('Equipment','EquipmentConfirmed',aid=9)])
    assert r['equipment']['status']=='UNMAPPED'
