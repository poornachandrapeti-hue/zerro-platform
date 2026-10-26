"""Deterministic, side-effect-free draft CPM calculations in local project calendar time.
Dates are naive local schedule datetimes; calendar timezone is preserved as metadata.
Calendars support overnight shifts and holidays. Lag is NONNEGATIVE working hours.
"""
from datetime import datetime, date, time, timedelta
from collections import defaultdict

class ScheduleError(ValueError): pass

def _clock(value):
    h,m=map(int,value.split(':')); return time(h,m)

def windows(cal, start_day):
    """Shift anchored to a working day; end may fall on following calendar day."""
    if start_day.weekday() not in cal['working_days'] or start_day.isoformat() in {str(x) for x in cal.get('holidays', [])}:
        return None
    start=datetime.combine(start_day,_clock(cal['shift_start']))
    end=datetime.combine(start_day,_clock(cal['shift_end']))
    if end <= start: end+=timedelta(days=1)
    return start,end

def next_work(dt,cal):
    for i in range(3700):
        day=dt.date()+timedelta(days=i-1 if i==0 else i-1)
        if i==0 and day<dt.date()-timedelta(days=1): continue
        w=windows(cal,day)
        if w and dt < w[1]: return max(dt,w[0])
    raise ScheduleError('No available working time within calendar search horizon')

def prev_work(dt,cal):
    for i in range(3700):
        day=dt.date()-timedelta(days=i)
        w=windows(cal,day)
        if w and dt>w[0]: return min(dt,w[1])
    raise ScheduleError('No available working time within calendar search horizon')

def add_work(start,hours,cal):
    if hours<0: raise ScheduleError('Negative duration/lag is unsupported')
    t=next_work(start,cal)
    if hours==0:return t
    remaining=hours*60
    for _ in range(4000):
        # previous day's overnight shift may contain this timestamp
        w=windows(cal,t.date()-timedelta(days=1))
        if not (w and w[0]<=t<w[1]):w=windows(cal,t.date())
        if not (w and w[0]<=t<w[1]):
            t=next_work(t+timedelta(minutes=1),cal);continue
        minutes=(w[1]-t).total_seconds()/60
        if remaining<=minutes:return t+timedelta(minutes=remaining)
        remaining-=minutes;t=next_work(w[1],cal)
    raise ScheduleError('Duration exceeds calendar calculation horizon')

def sub_work(end,hours,cal):
    if hours<0: raise ScheduleError('Negative duration/lag is unsupported')
    t=prev_work(end,cal)
    if hours==0:return t
    remaining=hours*60
    for _ in range(4000):
        w=windows(cal,t.date()-timedelta(days=1))
        if not (w and w[0]<t<=w[1]):w=windows(cal,t.date())
        if not (w and w[0]<t<=w[1]):
            t=prev_work(t-timedelta(minutes=1),cal);continue
        minutes=(t-w[0]).total_seconds()/60
        if remaining<=minutes:return t-timedelta(minutes=remaining)
        remaining-=minutes;t=prev_work(w[0],cal)
    raise ScheduleError('Duration exceeds calendar calculation horizon')

def work_hours(start,end,cal):
    if end<=start:return 0.0
    total=0.0;day=start.date()-timedelta(days=1)
    while day<=end.date():
        w=windows(cal,day)
        if w: total+=max(0,(min(end,w[1])-max(start,w[0])).total_seconds()/3600)
        day+=timedelta(days=1)
    return round(total,3)

def calculate(activities,dependencies,calendars,data_date):
    """activities: id, code, duration_hours, activity_type, calendar_id; deps: predecessor_id, successor_id, relation, lag_hours."""
    nodes={a['id']:a for a in activities}
    if not nodes:return {'activities':[],'warnings':[],'project_finish':None}
    for a in activities:
        if a['calendar_id'] not in calendars:raise ScheduleError(f"Missing calendar for {a['code']}")
        if a['activity_type'] not in ('Task','Milestone'):raise ScheduleError(f"Unsupported activity type {a['code']}")
        if a['activity_type']=='Task' and (a['duration_hours'] is None or a['duration_hours']<=0):raise ScheduleError(f"Missing duration for {a['code']}")
    incoming=defaultdict(list);outgoing=defaultdict(list);indegree={key:0 for key in nodes}
    for d in dependencies:
        p,s=d['predecessor_id'],d['successor_id']
        if p not in nodes or s not in nodes or p==s:raise ScheduleError('Invalid or self dependency')
        if d['relation'] not in ('FS','SS','FF','SF') or d['lag_hours']<0:raise ScheduleError('Invalid relationship or negative lag')
        incoming[s].append(d);outgoing[p].append(d);indegree[s]+=1
    available=sorted((x for x in nodes if indegree[x]==0),key=lambda x:nodes[x]['code']);order=[]
    while available:
        n=available.pop(0);order.append(n)
        for d in outgoing[n]:
            m=d['successor_id'];indegree[m]-=1
            if indegree[m]==0:available.append(m);available.sort(key=lambda x:nodes[x]['code'])
    if len(order)!=len(nodes):raise ScheduleError('Circular dependency detected')
    anchor=datetime.combine(data_date,time.min)
    early={}
    for n in order:
        a=nodes[n];cal=calendars[a['calendar_id']];duration=0 if a['activity_type']=='Milestone' else a['duration_hours']
        start=next_work(anchor,cal)
        for d in incoming[n]:
            pred=early[d['predecessor_id']];relation=d['relation'];lag=d['lag_hours']
            basis=pred['finish'] if relation[0]=='F' else pred['start']
            constraint=add_work(basis,lag,cal)
            if relation[1]=='F':constraint=sub_work(constraint,duration,cal)
            start=max(start,constraint)
        start=next_work(start,cal);finish=add_work(start,duration,cal)
        early[n]={'start':start,'finish':finish}
    project_end=max(x['finish'] for x in early.values());latest={}
    for n in reversed(order):
        a=nodes[n];cal=calendars[a['calendar_id']];duration=0 if a['activity_type']=='Milestone' else a['duration_hours']
        end=project_end
        for d in outgoing[n]:
            successor=latest[d['successor_id']];relation=d['relation'];succcal=calendars[nodes[d['successor_id']]['calendar_id']]
            constraint=successor['start'] if relation[1]=='S' else successor['finish']
            # Lag is in successor working time and must be undone there.
            constraint=sub_work(constraint,d['lag_hours'],succcal)
            if relation[0]=='S':constraint=add_work(constraint,duration,cal)
            end=min(end,constraint)
        last_start=sub_work(end,duration,cal)
        latest[n]={'start':last_start,'finish':add_work(last_start,duration,cal)}
    results=[]
    for n in order:
        a=nodes[n];cal=calendars[a['calendar_id']]
        slack=max(0,work_hours(early[n]['start'],latest[n]['start'],cal))
        results.append({'id':n,'code':a['code'],'name':a['name'],'activity_type':a['activity_type'],
                        'start':early[n]['start'].isoformat(timespec='minutes'),'finish':early[n]['finish'].isoformat(timespec='minutes'),
                        'late_start':latest[n]['start'].isoformat(timespec='minutes'),'late_finish':latest[n]['finish'].isoformat(timespec='minutes'),
                        'total_float_hours':slack,'critical':slack<0.001,'duration_hours':a['duration_hours'] or 0,'calendar_id':a['calendar_id']})
    return {'activities':results,'warnings':[], 'project_finish':project_end.isoformat(timespec='minutes'),'calculation_basis':'DRAFT_CPM_WORKING_HOURS_V1'}
