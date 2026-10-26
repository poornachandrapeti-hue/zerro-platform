"""Conservative coverage of planned activity windows by confirmed resource bookings.

Not resource leveling, workforce headcount validation, or permission to execute work.
"""
from datetime import datetime

CONFIRMED = {'Equipment': 'EquipmentConfirmed', 'Workforce': 'HRConfirmed'}


def coverage(activity_id, starts_at, ends_at, allocations):
    if starts_at.tzinfo is None or ends_at.tzinfo is None or starts_at >= ends_at:
        raise ValueError('Valid timezone-aware activity window required')
    result = {}
    for resource_type, confirmed_status in CONFIRMED.items():
        related = [a for a in allocations if a.activity_id == activity_id and a.resource_type == resource_type]
        confirmed = [a for a in related if a.status == confirmed_status and a.starts_at < ends_at and a.ends_at > starts_at]
        # Union overlapping confirmed intervals; allow consecutive bookings for one resource type.
        intervals = sorted((max(starts_at, a.starts_at), min(ends_at, a.ends_at)) for a in confirmed)
        cursor = starts_at
        for begin, end in intervals:
            if begin > cursor:
                break
            if end > cursor:
                cursor = end
            if cursor >= ends_at:
                break
        if not related:
            status = 'UNMAPPED'
        elif cursor >= ends_at:
            status = 'BOOKING_WINDOW_COVERED'
        elif intervals:
            status = 'PARTIAL_CONFIRMED_COVERAGE'
        else:
            status = 'NO_CONFIRMED_COVERAGE'
        result[resource_type.lower()] = {
            'status': status,
            'confirmed_booking_count': len(confirmed),
            'covers_entire_window': cursor >= ends_at,
            'confirmed_until': cursor.isoformat() if confirmed else None,
            'capacity_confirmed': False if resource_type == 'Workforce' else None,
        }
    return result
