"""E6 equipment runtime evidence validation; no progress/financial posting."""
from datetime import timezone
from decimal import Decimal, InvalidOperation
from fastapi import HTTPException

D = Decimal

def amount(value, label):
    try: x = D(str(value))
    except (InvalidOperation, ValueError, TypeError): raise HTTPException(422, f"Invalid {label}")
    if not x.is_finite() or x < 0 or x.as_tuple().exponent < -3:
        raise HTTPException(422, f"{label} must be finite, nonnegative and at most 3 decimal places")
    return x

def validate_usage(body, allocation, existing):
    if not body.starts_at.tzinfo or not body.ends_at.tzinfo:
        raise HTTPException(422,'Timezone-aware usage interval required')
    start=body.starts_at.astimezone(timezone.utc)
    end=body.ends_at.astimezone(timezone.utc)
    if start >= end:raise HTTPException(422,'Usage start must precede end')
    if allocation.status!='EquipmentConfirmed':
        raise HTTPException(409,'Confirmed Planning equipment allocation required')
    if not allocation.starts_at.tzinfo or not allocation.ends_at.tzinfo:
        raise HTTPException(409,'Planning allocation has no timezone')
    if start < allocation.starts_at.astimezone(timezone.utc) or end > allocation.ends_at.astimezone(timezone.utc):
        raise HTTPException(409,'Usage must fit confirmed allocation window')
    window = D(str((end-start).total_seconds())) / D('3600')
    values=[amount(getattr(body,k),k) for k in ('operating_hours','idle_hours','breakdown_hours','maintenance_hours')]
    if sum(values) > window + D('0.001'):
        raise HTTPException(409,'Combined usage hours exceed reporting window')
    if (body.meter_start is None) != (body.meter_end is None):
        raise HTTPException(422,'Meter start and end required together')
    if body.meter_start is not None:
        a,b=amount(body.meter_start,'meter_start'),amount(body.meter_end,'meter_end')
        if b < a:raise HTTPException(409,'Meter cannot decrease')
        if b-a > values[0] + D('0.001'):
            raise HTTPException(409,'Meter increase exceeds operating hours')
    fuel=amount(body.fuel_liters,'fuel_liters') if body.fuel_liters is not None else D('0')
    if fuel > 0 and values[0] == 0 and not body.anomaly_note:
        raise HTTPException(409,'Fuel without running hours requires anomaly explanation')
    for record in existing:
        old_start,old_end=record.starts_at.astimezone(timezone.utc),record.ends_at.astimezone(timezone.utc)
        if start < old_end and old_start < end:
            raise HTTPException(409,'Equipment usage overlaps existing record')
        if body.meter_start is not None and record.meter_end is not None and old_end <= start:
            if D(str(body.meter_start)) < D(str(record.meter_end)):
                raise HTTPException(409,'Meter reading below historical closing meter')
        if body.meter_end is not None and record.meter_start is not None and end <= old_start:
            if D(str(body.meter_end)) > D(str(record.meter_start)):
                raise HTTPException(409,'Meter reading exceeds future opening meter')
    return True
