"""Non-persistent resource throughput scenarios; not a resource-levelled CPM forecast."""
from decimal import Decimal, InvalidOperation


def _num(value):
    if value is None:
        return None
    try:
        out = Decimal(str(value))
        if not out.is_finite() or out <= 0:
            raise ValueError('Resource inputs must be finite positive numbers')
        return out
    except (InvalidOperation, TypeError) as exc:
        raise ValueError('Invalid resource input') from exc


def resource_scenario(source, *, unit, labor_rate=None, workers=None,
                      labor_hours_per_worker_day=None, equipment_rate=None,
                      equipment_count=None, equipment_hours_per_unit_day=None):
    if source.get('link_status') != 'linked':
        return {'status': 'unavailable', 'reason': 'No uniquely linked Construction source'}
    m = source.get('measurement') or {}
    if not unit or m.get('unit') != unit:
        return {'status': 'unavailable', 'reason': 'Quantity unit must match the verified Construction source'}
    try:
        scope = Decimal(str(m['scope_quantity']))
        verified = Decimal(str(m['verified_quantity']))
    except (KeyError, TypeError, InvalidOperation):
        return {'status': 'unavailable', 'reason': 'Missing verified scope or quantity'}
    if not all(v.is_finite() for v in (scope, verified)) or scope <= 0 or verified < 0 or verified > scope:
        return {'status': 'unavailable', 'reason': 'Invalid scope or verified quantity'}
    labor_fields = (labor_rate, workers, labor_hours_per_worker_day)
    equipment_fields = (equipment_rate, equipment_count, equipment_hours_per_unit_day)
    if any(v is not None for v in labor_fields) and not all(v is not None for v in labor_fields):
        return {'status': 'unavailable', 'reason': 'Complete labor rate, crew size, and daily productive hours required'}
    if any(v is not None for v in equipment_fields) and not all(v is not None for v in equipment_fields):
        return {'status': 'unavailable', 'reason': 'Complete equipment rate, unit count, and daily operating hours required'}
    if all(v is None for v in labor_fields + equipment_fields):
        return {'status': 'unavailable', 'reason': 'At least one complete resource constraint required'}
    try:
        labor_capacity = _num(labor_rate) * _num(workers) * _num(labor_hours_per_worker_day) if labor_rate is not None else None
        equipment_capacity = _num(equipment_rate) * _num(equipment_count) * _num(equipment_hours_per_unit_day) if equipment_rate is not None else None
    except ValueError as exc:
        return {'status': 'unavailable', 'reason': str(exc)}
    remaining = scope - verified
    capacity = min(c for c in (labor_capacity, equipment_capacity) if c is not None)
    days = remaining / capacity
    bottleneck = ('labor' if labor_capacity is not None and labor_capacity == capacity else 'equipment')
    return {'status': 'scenario', 'unit': unit, 'remaining_quantity': float(remaining),
            'labor_capacity_per_day': float(labor_capacity) if labor_capacity is not None else None,
            'equipment_capacity_per_day': float(equipment_capacity) if equipment_capacity is not None else None,
            'limiting_resource': bottleneck, 'estimated_working_days': round(float(days), 2),
            'resource_constraints_included': [x for x, c in [('labor', labor_capacity), ('equipment', equipment_capacity)] if c is not None],
            'confirmed_future_availability': False, 'schedule_finish_calculated': False,
            'basis': 'Current verified outstanding quantity and planner-supplied productivity and resource allocations; does not account for calendar, downtime, dependencies or confirmed availability'}
