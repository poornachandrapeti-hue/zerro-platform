"""Non-persistent estimates derived from CURRENT verified scope and explicit productivity.

This is not historical as-of evidence, and it never modifies approved forecasts.
"""
from decimal import Decimal, InvalidOperation, ROUND_CEILING


def estimate_remaining(source, rate, rate_unit):
    if not source or source.get('link_status') != 'linked':
        return {'status': 'unavailable', 'reason': 'No valid, uniquely linked execution source'}
    m = source.get('measurement') or {}
    unit = str(m.get('unit') or '').strip()
    if not unit or unit != str(rate_unit or '').strip():
        return {'status': 'unavailable', 'reason': 'Productivity rate unit must exactly match source quantity unit'}
    try:
        scope = Decimal(str(m['scope_quantity']))
        verified = Decimal(str(m['verified_quantity']))
        hourly_rate = Decimal(str(rate))
    except (KeyError, TypeError, InvalidOperation):
        return {'status': 'unavailable', 'reason': 'Valid scope and verified quantities are required'}
    if any(not v.is_finite() for v in (scope, verified, hourly_rate)) or scope <= 0 or verified < 0 or verified > scope:
        return {'status': 'unavailable', 'reason': 'Invalid scope or verified measurement'}
    if hourly_rate <= 0:
        return {'status': 'unavailable', 'reason': 'Productivity rate must be positive'}
    outstanding = scope - verified
    hours = outstanding / hourly_rate
    return {'status': 'recommendation', 'unit': unit, 'scope_quantity': float(scope),
            'verified_quantity_current': float(verified), 'remaining_quantity': float(outstanding),
            'productivity_units_per_hour': float(hourly_rate),
            'recommended_remaining_hours': float(hours.quantize(Decimal('0.01'))),
            'completed_from_current_measurement': outstanding == 0,
            'source_as_of_forecast_data_date': False,
            'basis': 'CURRENT verified Construction quantity / EXPLICIT planner productivity rate; review required'}
