"""Phase 31.17: pure receivable-aging and dated cash-inflow projections.

No accounting recognition or payment is performed by these functions.
"""
from datetime import datetime, timezone
from decimal import Decimal


def receivables_aging_and_cash_forecast(claims, collected_by_claim, as_of):
    """Return (aging per currency, in-app alerts, due-date inflows, missing-date count).

    Only caller-validated, certified claims should be supplied. Undated receivables
    are explicitly reported as unaged rather than silently counted as 'not_due'.
    """
    if as_of.tzinfo is None:
        as_of=as_of.replace(tzinfo=timezone.utc)
    bins={}
    alerts=[]
    incoming={}
    missing=0
    for claim in claims:
        outstanding=max(Decimal('0'),Decimal(claim.certified_value)-Decimal(collected_by_claim.get(claim.id,0)))
        if not outstanding:
            continue
        currency=claim.currency
        buckets=bins.setdefault(currency,{k:Decimal('0') for k in ('not_due','1_30','31_60','61_90','over_90','undated')})
        if claim.due_date is None:
            buckets['undated']+=outstanding
            missing+=1
            continue
        due=claim.due_date.date()
        days=(as_of.date()-due).days
        bucket='not_due' if days<=0 else ('1_30' if days<=30 else '31_60' if days<=60 else '61_90' if days<=90 else 'over_90')
        buckets[bucket]+=outstanding
        key=due.isoformat()
        c=incoming.setdefault(currency,{})
        c[key]=c.get(key,Decimal('0'))+outstanding
        if days>0:
            alerts.append({'kind':'overdue_receivable','claim_id':claim.id,'number':claim.number,'currency':currency,'amount':str(outstanding),'days_overdue':days})
    return ({cc:{key:str(value) for key,value in vals.items()} for cc,vals in bins.items()},alerts,incoming,missing)
