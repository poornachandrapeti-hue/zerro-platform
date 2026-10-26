"""Phase 13 forecast preview; explicit planner assumptions, no changes to approved baseline.

Current CPM is computed for remaining work only; complete predecessor relationships
are fulfilled at the reporting data date (not evidence of actual completion dates).
"""
from datetime import date
from .scheduling_engine import calculate, ScheduleError


def preview(activities, dependencies, calendars, data_date: date, updates):
    by_id = {a['id']: a for a in activities}
    if len(by_id) != len(activities):
        raise ScheduleError('Duplicate activity identifier')
    unknown = set(updates) - set(by_id)
    if unknown:
        raise ScheduleError('Unknown activity in forecast update')
    complete, remaining, missing = set(), [], []
    for a in activities:
        status = updates.get(a['id'])
        if status is None:
            missing.append(a['code'])
            continue
        if status['completed']:
            complete.add(a['id'])
        else:
            duration = status['remaining_hours']
            if a['activity_type'] == 'Task' and (duration is None or duration <= 0):
                raise ScheduleError(f"Positive remaining hours required for {a['code']}")
            if a['activity_type'] == 'Milestone' and duration not in (None, 0):
                raise ScheduleError(f"Milestone remaining hours must be zero: {a['code']}")
            remaining.append({**a, 'duration_hours': 0 if a['activity_type'] == 'Milestone' else duration})
    if missing:
        raise ScheduleError('Forecast inputs missing for: ' + ', '.join(missing[:20]))
    remaining_ids = {a['id'] for a in remaining}
    links = []
    for d in dependencies:
        if d['predecessor_id'] not in by_id or d['successor_id'] not in by_id:
            raise ScheduleError('Dependency references missing activity')
        if d['successor_id'] in complete and d['predecessor_id'] in remaining_ids:
            raise ScheduleError('Completed activity has an unfinished predecessor: evidence requires review')
        if d['predecessor_id'] in remaining_ids and d['successor_id'] in remaining_ids:
            links.append(d)
    result = calculate(remaining, links, calendars, data_date)
    result.update({
        'data_date': data_date.isoformat(),
        'basis': 'UNAPPROVED_FORECAST_PREVIEW_V1',
        'completed_activity_ids': sorted(complete),
        'remaining_activity_count': len(remaining),
        'approved_baseline_unchanged': True,
        'source_actuals_verified': False,
        'assumptions': [
            'Remaining hours and completion indicators are planner-supplied inputs, not verified actuals.',
            'Completed predecessors are assumed satisfied at the data date; no actual completion date is inferred.',
            'Criticality is calculated for the unfinished network; omitted completion evidence may affect results.',
            'Resource leveling, imposed date constraints and out-of-sequence progress are not modeled.',
        ],
    })
    return result
