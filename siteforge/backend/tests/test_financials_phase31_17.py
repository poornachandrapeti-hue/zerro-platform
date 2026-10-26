from datetime import datetime, timezone, timedelta
from decimal import Decimal
from types import SimpleNamespace
from app.domains.commercial_financials.financial_aging import receivables_aging_and_cash_forecast

def test_aging_and_forecast_distinct_currencies_and_partial_collections():
    now=datetime(2026,10,20,tzinfo=timezone.utc)
    claims=[SimpleNamespace(id=1,number='A',currency='INR',certified_value=Decimal('200'),due_date=now-timedelta(days=35)),
            SimpleNamespace(id=2,number='B',currency='USD',certified_value=Decimal('90'),due_date=now+timedelta(days=5))]
    buckets,alerts,inflows,missing=receivables_aging_and_cash_forecast(claims,{1:Decimal('50')},now)
    assert buckets['INR']['31_60']=='150'
    assert buckets['USD']['not_due']=='90'
    assert len(alerts)==1 and alerts[0]['claim_id']==1
    assert inflows['INR']['2026-09-15']==Decimal('150')
    assert missing==0

def test_undated_claim_is_not_fabricated_and_fully_collected_excluded():
    now=datetime(2026,10,20,tzinfo=timezone.utc)
    claims=[SimpleNamespace(id=1,number='A',currency='INR',certified_value=Decimal('100'),due_date=None),
            SimpleNamespace(id=2,number='B',currency='INR',certified_value=Decimal('80'),due_date=now-timedelta(days=95))]
    buckets,alerts,inflows,missing=receivables_aging_and_cash_forecast(claims,{2:Decimal('80')},now)
    assert buckets['INR']['undated']=='100' and buckets['INR']['over_90']=='0'
    assert not alerts and not inflows and missing==1
