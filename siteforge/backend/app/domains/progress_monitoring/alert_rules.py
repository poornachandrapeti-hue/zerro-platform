"""Pure rule evaluation so thresholds and conditions can be unit-tested."""
import hashlib

def fingerprint(kind, detail):
    return hashlib.sha256((kind + ':' + detail).encode()).hexdigest()[:40]

def evaluate_progress_alerts(data, warning_pp=5, critical_pp=10):
    output=[]
    for message in data.get('exceptions', []):
        message=str(message)
        output.append({'fingerprint':fingerprint('source_quality',message),'type':'source_quality',
                       'severity':'warning','message':message})
    if data.get('visibility')!='project':
        return output
    current=((data.get('stages') or {}).get('construction') or {}).get('percent')
    cutoff=data.get('data_date')
    targets=[p for p in data.get('planned',[]) if cutoff and p.get('period_end') and p['period_end']<=cutoff]
    if current is None or not targets:
        return output
    target=targets[-1]
    if target.get('planned_percent') is None:
        return output
    gap=round(float(target['planned_percent'])-float(current),2)
    if gap>float(warning_pp):
        severity='critical' if gap>float(critical_pp) else 'warning'
        output.append({'fingerprint':fingerprint('progress_variance',str(target['period_end'])),
            'type':'progress_variance','severity':severity,
            'message':f'Verified construction progress is {gap:.2f} percentage points behind the last approved target.',
            'target_date':target['period_end'],'variance_pp':-gap})
    return output
