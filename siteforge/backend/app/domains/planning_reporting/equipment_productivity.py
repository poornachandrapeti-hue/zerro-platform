"""Read-only observed quantity per activity-booked equipment-hour.

One equipment-hour value is attached to a Construction progress line; quantity
must be counted once, irrespective of workers attached to that line.
"""
from datetime import timedelta
from decimal import Decimal, InvalidOperation


def calculate_equipment_productivity(rows, unit, end_date, window_days=28):
    """Rows: (line_id, report_date, quantity, unit, approved_now, rework,
    reversal, equipment_hours). Retrospective observations, not approval-as-of.
    """
    begin = end_date - timedelta(days=window_days - 1)
    by_line = {}
    for line_id, day, quantity, line_unit, approved, rework, reversal, equipment_hours in rows:
        if not approved or rework or reversal or day is None or not begin <= day <= end_date:
            continue
        if line_unit != unit:
            return {'status': 'unavailable', 'reason': 'Quantity unit differs from the linked activity unit'}
        try:
            q = Decimal(str(quantity))
        except (InvalidOperation, ValueError, TypeError):
            return {'status': 'unavailable', 'reason': 'Invalid recorded quantity'}
        if not q.is_finite() or q <= 0:
            return {'status': 'unavailable', 'reason': 'Nonpositive or invalid eligible quantity'}
        if line_id in by_line:
            return {'status': 'unavailable', 'reason': 'Duplicate progress-line records in equipment observation'}
        if equipment_hours is None:
            return {'status': 'insufficient_data', 'reason': 'Eligible progress line has no allocated equipment hours'}
        try:
            hours = Decimal(str(equipment_hours))
        except (InvalidOperation, ValueError, TypeError):
            return {'status': 'unavailable', 'reason': 'Invalid recorded equipment hours'}
        if not hours.is_finite() or hours <= 0:
            return {'status': 'insufficient_data', 'reason': 'Positive activity-booked equipment hours required'}
        by_line[line_id] = (day, q, hours)
    if not by_line:
        return {'status': 'insufficient_data', 'reason': 'No eligible approved, non-rework progress lines'}
    quantity = sum((r[1] for r in by_line.values()), Decimal(0))
    hours = sum((r[2] for r in by_line.values()), Decimal(0))
    days = len({r[0] for r in by_line.values()})
    return {
        'status': 'observed', 'unit': unit,
        'window_start': begin.isoformat(), 'window_end': end_date.isoformat(),
        'quantity_line_count': len(by_line), 'observed_days': days,
        'net_eligible_quantity': float(quantity), 'allocated_equipment_hours': float(hours),
        'quantity_per_equipment_hour': float((quantity / hours).quantize(Decimal('0.0001'))),
        'equipment_hours_per_unit': float((hours / quantity).quantize(Decimal('0.0001'))),
        'coverage': 'broader_sample' if len(by_line) >= 8 and days >= 5 else 'limited_sample',
        'basis': 'Retrospective, currently approved Construction progress-line equipment-hours. '
                 'No equipment identity, class, utilization or concurrent resource availability is verified. '
                 'Not approval-as-of history, calendar duration, or forecast confidence probability.',
        'automatically_updates_forecast': False,
    }
