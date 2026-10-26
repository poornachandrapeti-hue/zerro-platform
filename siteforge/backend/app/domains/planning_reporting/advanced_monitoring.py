"""Read-only approved-baseline versus approved-planner-forecast monitoring.

This is a planning risk comparison, never a contractual delay determination.
"""
from datetime import date


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except (TypeError, ValueError):
        return None


def summarize(baseline_rows, forecast_rows, milestones, forecast_data_date=None):
    """Match rows by unique activity code; never infer unmatched activity status."""
    base={}
    fore={}
    duplicate=set()
    for item in baseline_rows or []:
        if not isinstance(item,dict): continue
        code=str(item.get('code') or item.get('activity_code') or '')
        if not code:continue
        if code in base:duplicate.add(code)
        base[code]=item
    for item in forecast_rows or []:
        if not isinstance(item,dict):continue
        code=str(item.get('code') or item.get('activity_code') or '')
        if not code:continue
        if code in fore:duplicate.add(code)
        fore[code]=item
    changed=[]
    for code, row in base.items():
        if code in duplicate or code not in fore:continue
        nxt=fore[code]
        if not isinstance(row.get('critical'),bool) or not isinstance(nxt.get('critical'),bool):continue
        if row['critical'] != nxt['critical']:
            changed.append({'activity_code':code[:80], 'activity_name':str(row.get('name') or '')[:240],
                'baseline_critical':row['critical'],'forecast_critical':nxt['critical'],
                'forecast_finish':nxt.get('finish'),
                'interpretation':'planner_forecast_criticality_change'})
    risks=[]
    cutoff=_day(forecast_data_date)
    for m in milestones or []:
        code=m.get('activity_code')
        if not code or code in duplicate:continue
        if m.get('actual_finish'):
            continue
        planned=_day(m.get('baseline_finish'))
        predicted=_day(fore.get(code,{}).get('finish'))
        status='forecast_unavailable'
        gap=None
        if planned and predicted:
            gap=(predicted-planned).days
            status='forecast_later_than_baseline' if gap>0 else 'forecast_not_later_than_baseline'
        elif m.get('completion_status')=='incomplete' and planned and cutoff and cutoff>planned:
            status='past_baseline_at_forecast_data_date'
        risks.append({'activity_code':str(code)[:80], 'activity_name':str(m.get('activity_name') or '')[:240],
            'baseline_finish':m.get('baseline_finish'),
            'forecast_finish':fore.get(code,{}).get('finish'), 'difference_calendar_days':gap,
            'risk_status':status, 'actual_evidence_status':m.get('variance_status')})
    return {'criticality_changes':changed[:500], 'milestone_risks':risks[:500],
            'unmatched_baseline_activity_count':len(set(base)-set(fore)),
            'duplicate_activity_codes':sorted(duplicate)[:20],
            'basis':'approved_baseline_vs_latest_approved_planner_forecast',
            'live_actuals_reconstructed':False,
            'resource_leveled':False,
            'note':'Comparisons use approved but planner-assumed forecast dates; no inference of contractual entitlement or verified completion.'}
