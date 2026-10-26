from datetime import datetime,timezone,timedelta
from decimal import Decimal
from types import SimpleNamespace as Obj
import pytest
from fastapi import HTTPException
from app.domains.planning_reporting.equipment_usage_rules import validate_usage

base=datetime(2026,10,26,tzinfo=timezone.utc)
allocation=Obj(status='EquipmentConfirmed',starts_at=base,ends_at=base+timedelta(hours=12))
def body(**overrides):
    vals=dict(starts_at=base,ends_at=base+timedelta(hours=8),operating_hours=Decimal('5'),
      idle_hours=Decimal('2'),breakdown_hours=Decimal('1'),maintenance_hours=Decimal('0'),
      meter_start=Decimal('100'),meter_end=Decimal('105'),fuel_liters=Decimal('30'),anomaly_note=None)
    vals.update(overrides)
    return Obj(**vals)
def blocked(b,code=409,existing=(),alloc=allocation):
    with pytest.raises(HTTPException) as err:validate_usage(b,alloc,existing)
    assert err.value.status_code==code

def test_valid_evidence():assert validate_usage(body(),allocation,[])
def test_hours_cannot_exceed_window():blocked(body(operating_hours=Decimal('7')))
def test_negative_hours():blocked(body(idle_hours=Decimal('-1')),422)
def test_unconfirmed_allocation():blocked(body(),alloc=Obj(status='Proposed',starts_at=base,ends_at=base+timedelta(hours=12)))
def test_allocation_bounds():blocked(body(ends_at=base+timedelta(hours=13)))
def test_meter_reverse():blocked(body(meter_end=Decimal('99')))
def test_meter_more_than_worked():blocked(body(meter_end=Decimal('110')))
def test_meter_pair():blocked(body(meter_end=None),422)
def test_overlap():blocked(body(),existing=[Obj(starts_at=base+timedelta(hours=6),ends_at=base+timedelta(hours=9),meter_start=None,meter_end=None)])
def test_adjacent_allowed():
    r=Obj(starts_at=base+timedelta(hours=8),ends_at=base+timedelta(hours=9),meter_start=None,meter_end=None)
    assert validate_usage(body(),allocation,[r])
def test_fuel_without_running_hours_explanation():blocked(body(operating_hours=0,breakdown_hours=6,idle_hours=2,fuel_liters=10))
def test_explained_fuel_anomaly():assert validate_usage(body(operating_hours=0,breakdown_hours=6,idle_hours=2,fuel_liters=10,anomaly_note='Fuel supplied while equipment idle',meter_start=None,meter_end=None),allocation,[])
def test_historical_meter_rollback():
    past=Obj(starts_at=base-timedelta(hours=4),ends_at=base,meter_start=Decimal('100'),meter_end=Decimal('106'))
    blocked(body(),existing=[past])
def test_naive_interval():blocked(body(starts_at=base.replace(tzinfo=None)),422)
