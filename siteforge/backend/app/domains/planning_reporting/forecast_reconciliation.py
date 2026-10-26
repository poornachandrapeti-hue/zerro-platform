"""Read-only current-source reconciliation of planner forecast assumptions.

A point-in-time CURRENT measurement cannot validate historical data-date actuals.
No historical reconstruction or automatic forecast approval is performed.
"""
from datetime import date


def reconcile(saved_inputs, progress_rows):
    source_by_id = {r['activity_id']: r for r in progress_rows}
    seen = set()
    details = []
    for item in saved_inputs:
        aid = item['activity_id']
        if aid in seen:
            raise ValueError('Duplicate saved forecast activity identifier')
        seen.add(aid)
        source = source_by_id.get(aid)
        state = source.get('link_status') if source else 'activity_missing'
        verified = (source.get('measurement') or {}).get('verified_percent') if source else None
        planner_complete = bool(item.get('completed'))
        if state != 'linked' or verified is None:
            match = 'unavailable'
        elif planner_complete and float(verified) < 100:
            match = 'planner_complete_but_source_incomplete'
        elif not planner_complete and float(verified) >= 100:
            match = 'source_complete_but_planner_unfinished'
        else:
            match = 'consistent_current_status'
        details.append({'activity_id':aid, 'activity_code':source.get('activity_code') if source else None,
                        'source_status':state,'verified_percent_current':verified,
                        'planner_completed_at_forecast':planner_complete,'comparison':match})
    count = {key:sum(d['comparison']==key for d in details) for key in (
        'consistent_current_status','planner_complete_but_source_incomplete',
        'source_complete_but_planner_unfinished','unavailable')}
    return {'activities':details,'counts':count,
            'as_of_forecast_data_date':False,
            'basis':'CURRENT verified Construction totals vs SAVED historical planner inputs; not a historical as-of comparison'}


def finish_variance(forecast_finish, baseline_finish):
    if not forecast_finish or not baseline_finish:
        return {'variance_days':None,'status':'missing_date'}
    try:
        f=date.fromisoformat(str(forecast_finish)[:10]); b=date.fromisoformat(str(baseline_finish)[:10])
    except (TypeError,ValueError):
        return {'variance_days':None,'status':'invalid_date'}
    return {'variance_days':(f-b).days,'status':'calendar_day_comparison_not_contractual_delay'}
