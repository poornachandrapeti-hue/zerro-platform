from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from app.domains.planning_reporting.resource_capacity import equipment_demand_evidence

START=datetime(2026,10,20,8,tzinfo=timezone.utc)
END=START+timedelta(hours=8)
def allocation(ref, a=START, b=END, status='EquipmentConfirmed'):
    return SimpleNamespace(activity_id=7,resource_type='Equipment',status=status,resource_ref=ref,starts_at=a,ends_at=b)
def demand(qty,unit='units'):
    return SimpleNamespace(id=1,activity_id=7,resource_type='Equipment',resource_name='Cranes',demand_quantity=qty,demand_unit=unit)

def test_distinct_assets_cover():
    r=equipment_demand_evidence(7,START,END,[allocation('A'),allocation('B')],[demand(2)])
    assert r['equipment_demands'][0]['status']=='BOOKING_COUNT_MEETS_DEMAND'
    assert r['equipment_demands'][0]['distinct_fully_booked_assets']==2

def test_duplicate_asset_not_double_counted():
    r=equipment_demand_evidence(7,START,END,[allocation('A'),allocation('A')],[demand(2)])
    assert r['equipment_demands'][0]['booking_gap']==1

def test_partial_asset_not_counted():
    r=equipment_demand_evidence(7,START,END,[allocation('A',b=START+timedelta(hours=4))],[demand(1)])
    assert r['equipment_demands'][0]['status']=='NO_FULL_WINDOW_BOOKINGS'

def test_consecutive_bookings_same_asset_cover():
    mid=START+timedelta(hours=4)
    r=equipment_demand_evidence(7,START,END,[allocation('A',b=mid),allocation('A',a=mid)],[demand(1)])
    assert r['equipment_demands'][0]['booking_gap']==0

def test_incomparable_demand_is_not_satisfied():
    r=equipment_demand_evidence(7,START,END,[allocation('A')],[demand(8,'equipment-hours')])
    assert r['equipment_demands'][0]['status']=='INCOMPARABLE_UNIT'
    assert r['equipment_demands'][0]['booking_gap'] is None

def test_unconfirmed_not_counted():
    r=equipment_demand_evidence(7,START,END,[allocation('A',status='Reviewed')],[demand(1)])
    assert r['equipment_demands'][0]['booking_gap']==1

def test_timezone_required():
    with pytest.raises(ValueError): equipment_demand_evidence(7,START.replace(tzinfo=None),END,[],[])
