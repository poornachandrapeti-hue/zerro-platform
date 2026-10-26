"""Read-only, source-referenced Contracts intelligence. No Finance/Planning inferred totals."""
from collections import Counter
from datetime import datetime, timezone, timedelta
from decimal import Decimal

EFFECTIVE = {'Executed','Active','Completed','Closed'}
FINAL_OBLIGATIONS = {'Accepted','Waived','Cancelled'}
FINAL_CLAIMS = {'Rejected','Withdrawn'}

def build_intelligence(project_id, contracts, amendments, obligations, claims, securities, deliveries, *, as_of=None):
    now = as_of or datetime.now(timezone.utc)
    ids = {c.id for c in contracts}
    lifecycle = Counter(c.lifecycle for c in contracts)
    base, delta, proposed, agreed_pending, claim_exposure = {}, {}, {}, {}, {}
    def add(bucket, currency, amount):
        if currency and amount is not None:
            bucket[currency] = bucket.get(currency, Decimal('0')) + Decimal(str(amount))
    for c in contracts:
        if c.lifecycle in EFFECTIVE:
            add(base,c.currency,c.original_value)
    amendment_ids = set()
    for a in amendments:
        if a.contract_id not in ids: continue
        amendment_ids.add(a.id)
        if a.status == 'Executed' and a.effective_version_id is not None:
            add(delta,a.currency,a.delta_value)
        elif a.status in {'Approved','Agreed','Awaiting Signature'}:
            add(agreed_pending,a.currency,a.delta_value)
    for cl in claims:
        if cl.contract_id in ids and cl.status not in FINAL_CLAIMS:
            add(claim_exposure,cl.currency,cl.requested_amount)
    effective = dict(base)
    for currency, amount in delta.items(): effective[currency] = effective.get(currency,Decimal('0')) + amount
    overdue = upcoming = unresolved = 0
    for o in obligations:
        if o.contract_id not in ids or o.status in FINAL_OBLIGATIONS:continue
        if o.due_at is None:unresolved += 1
        elif o.due_at < now:overdue += 1
        elif o.due_at <= now + timedelta(days=14):upcoming += 1
    expiring = expired = 0
    for s in securities:
        if s.contract_id not in ids or s.status == 'Released':continue
        if s.expires_at < now:expired += 1
        elif s.expires_at <= now + timedelta(days=30):expiring += 1
    delivery_counts = Counter(d.status for d in deliveries if d.amendment_id in amendment_ids)
    money=lambda d:{k:str(v) for k,v in sorted(d.items())}
    return {'schema_version':'contracts_intelligence_v1','source':'ZerroBuild Contracts',
        'project_id':project_id,'as_of':now.isoformat(),'read_only':True,
        'contracts_count':len(contracts),'contracts_by_status':dict(lifecycle),
        'original_value_by_currency':money(base),'effective_value_by_currency':money(effective),
        'agreed_pending_effectiveness_by_currency':money(agreed_pending),
        'open_claims_requested_by_currency':money(claim_exposure),
        'overdue_obligations':overdue,'upcoming_obligations_14d':upcoming,
        'obligations_missing_due_date':unresolved,'securities_expiring_30d':expiring,
        'securities_expired':expired,'delivery_status_counts':dict(delivery_counts),
        'financials_certified_billing':{'status':'Unavailable','value':None},
        'planning_baseline_status':{'status':'Unavailable','value':None},
        'source_integrity':{'status':'partial','reconciled':False,'reason':'Financials/Planning and partner data not source-reconciled'},
        'complete':False}
