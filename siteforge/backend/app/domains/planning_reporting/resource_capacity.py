"""Evidence-only comparison of confirmed individual equipment reservations to unit demand.

This does not perform resource leveling or certify equipment operation/worker capacity.
"""
from collections import defaultdict

EQUIPMENT_UNITS = {'unit', 'units', 'equipment units', 'machines', 'assets'}


def _covers(start, end, reservations):
    intervals = sorted((max(start, r.starts_at), min(end, r.ends_at))
                       for r in reservations if r.starts_at < end and r.ends_at > start)
    cursor = start
    for left, right in intervals:
        if left > cursor:
            return False
        cursor = max(cursor, right)
        if cursor >= end:
            return True
    return cursor >= end


def _asset_id(reference):
    """Accept only stable register references, not free-text asset names."""
    if not isinstance(reference, str) or not reference.startswith('equipment:'):
        return None
    value = reference.split(':', 1)[1]
    return int(value) if value.isdigit() and int(value) > 0 else None


def _normalize_type(value):
    return ' '.join(str(value or '').casefold().split())


def equipment_demand_evidence(activity_id, start, end, allocations, demands, assets=None):
    """Distinct confirmed assets count once each only if covering the entire window.

    Demand units must be literal asset counts, not hours or staffing. A covered booking
    is not a regulatory inspection, utilization, or operating authorization check.
    """
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise ValueError('Valid timezone-aware forecast interval required')
    groups = defaultdict(list)
    for a in allocations:
        if (a.activity_id == activity_id and a.resource_type == 'Equipment'
                and a.status == 'EquipmentConfirmed' and a.resource_ref):
            groups[a.resource_ref].append(a)
    refs = sorted(ref for ref, rows in groups.items() if _covers(start, end, rows))
    # When a register is supplied, never treat generic equipment counts as
    # satisfying an equipment-specific demand. Each registered asset is counted
    # at most once per demand, and type/certification are checked independently.
    asset_by_id = {a.id: a for a in (assets or [])}
    type_matched = {}
    if assets is not None:
        for ref in refs:
            asset = asset_by_id.get(_asset_id(ref))
            if asset is None or getattr(asset, 'status', None) != 'Active':
                continue
            if getattr(asset, 'inspection_review_status', None) != 'Verified':
                continue
            valid_through = getattr(asset, 'inspection_valid_through', None)
            if valid_through is None or valid_through < end.date():
                continue
            key = _normalize_type(getattr(asset, 'equipment_type', ''))
            if key:
                type_matched.setdefault(key, set()).add(asset.id)
    results = []
    for d in demands:
        if d.activity_id != activity_id or d.resource_type != 'Equipment':
            continue
        unit = (d.demand_unit or '').strip().lower()
        required_type = _normalize_type(d.resource_name)
        eligible_refs = (len(type_matched.get(required_type, set())) if assets is not None else len(refs))
        if unit not in EQUIPMENT_UNITS:
            status = 'INCOMPARABLE_UNIT'
            gap = None
        elif d.demand_quantity <= 0:
            status = 'INVALID_DEMAND'
            gap = None
        elif assets is not None and not required_type:
            status = 'EQUIPMENT_TYPE_REQUIRED'
            gap = None
        elif assets is not None and eligible_refs == 0:
            status = 'NO_TYPE_MATCHED_CONFIRMED_ASSETS'
            gap = d.demand_quantity
        elif not refs:
            status = 'NO_FULL_WINDOW_BOOKINGS'
            gap = d.demand_quantity
        else:
            gap = max(0, d.demand_quantity - eligible_refs)
            status = 'BOOKING_COUNT_MEETS_DEMAND' if gap == 0 else 'BOOKING_COUNT_SHORTFALL'
        results.append({'demand_id': d.id, 'resource_name': d.resource_name,
                        'demand_quantity': d.demand_quantity, 'demand_unit': d.demand_unit,
                        'distinct_fully_booked_assets': len(refs), 'type_matched_eligible_assets': eligible_refs, 'required_equipment_type': d.resource_name, 'booking_gap': gap,
                        'status': status, 'capacity_verified': False})
    return {'activity_id': activity_id, 'fully_booked_asset_refs': refs,
            'equipment_demands': results, 'workforce_headcount_verified': False,
            'resource_leveled_schedule': False}
