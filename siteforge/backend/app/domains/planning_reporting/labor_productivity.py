"""Retrospective Construction line-level quantity/productive-labor-hour analysis.

Hours are booked to Construction progress lines; HR attendance is never presumed
allocated to an activity. No historical approval-as-of claims are made.
"""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal, InvalidOperation


def calculate_labor_productivity(rows, unit, end_date, window_days=28):
    """Rows: (line_id, work_date, quantity, unit, approved_now, rework,
    reversal, productive_minutes, idle_minutes). One row per line/person, or
    one line with null minutes if it has no labor entry.
    """
    begin=end_date-timedelta(days=window_days-1)
    by_line={}
    for line_id,day,quantity,line_unit,approved,rework,reversal,productive,idle in rows:
        if not approved or rework or reversal or day is None or not (begin<=day<=end_date):
            continue
        if line_unit != unit:
            return {'status':'unavailable','reason':'Progress line unit differs from activity quantity unit'}
        try:
            q=Decimal(str(quantity))
        except (InvalidOperation, TypeError, ValueError):
            return {'status':'unavailable','reason':'Invalid recorded quantity'}
        if not q.is_finite() or q<=0:
            return {'status':'unavailable','reason':'Nonpositive or invalid eligible progress quantity'}
        rec=by_line.setdefault(line_id,{'date':day,'quantity':q,'productive':0,'idle':0,'has_labor':False,'person_rows':0})
        if rec['date']!=day or rec['quantity']!=q:
            return {'status':'unavailable','reason':'Inconsistent progress line records'}
        if productive is not None or idle is not None:
            p=int(productive or 0); i=int(idle or 0)
            if p<0 or i<0:
                return {'status':'unavailable','reason':'Negative labor minutes'}
            rec['productive']+=p;rec['idle']+=i;rec['has_labor']=True;rec['person_rows']+=1
    if not by_line:
        return {'status':'insufficient_data','reason':'No eligible approved, non-rework, positive quantity lines'}
    if any(not line['has_labor'] or line['productive']<=0 for line in by_line.values()):
        return {'status':'insufficient_data','reason':'Some eligible quantity lines have no positive activity-booked productive labor minutes','quantity_line_count':len(by_line)}
    qty=sum((x['quantity'] for x in by_line.values()),Decimal(0))
    minutes=sum(x['productive'] for x in by_line.values())
    idle=sum(x['idle'] for x in by_line.values())
    hours=Decimal(minutes)/Decimal(60)
    days=len(set(x['date'] for x in by_line.values()))
    return {'status':'observed','unit':unit,'window_start':begin.isoformat(),'window_end':end_date.isoformat(),
        'quantity_line_count':len(by_line),'observed_days':days,
        'net_eligible_quantity':float(qty),'productive_labor_hours':float(hours),
        'idle_labor_hours':round(idle/60,3),'quantity_per_productive_labor_hour':float((qty/hours).quantize(Decimal('0.0001'))),
        'labor_hours_per_unit':float((hours/qty).quantize(Decimal('0.0001'))),
        'coverage':'broader_sample' if len(by_line)>=8 and days>=5 else 'limited_sample',
        'basis':'Retrospective approved-now Construction quantities linked to per-person progress-line productive minutes. Excludes rework, reversals, and unapproved records; not approval-as-of history, elapsed scheduling hours, or a forecast confidence probability.',
        'automatically_updates_forecast':False}
