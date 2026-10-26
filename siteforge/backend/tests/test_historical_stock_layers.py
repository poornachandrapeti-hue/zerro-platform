import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.domains.commercial_financials.historical_stock_layers import reconstruct_receipt_layers

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
def ev(i, kind, q, rid=10, **extra):
    return dict(id=i, kind=kind, quantity=q, receipt_line_id=rid, material_id=3, unit='KG',
                warehouse_id=4, organization_id=1, project_id=2,
                occurred_at=BASE + timedelta(seconds=i), **extra)
def calc(events):
    return reconstruct_receipt_layers(organization_id=1, project_id=2, events=events)

def test_issue_and_return():
    result = calc([ev(1,'RECEIPT','100'),ev(2,'ISSUE','40'),ev(3,'RETURN','10',source_issue_event_id=2)])
    assert result['receipt_layers'][0]['remaining_quantity'] == '70'
    assert result['finance_valuation_verified'] is False

def test_unsorted_input():
    assert calc([ev(2,'ISSUE',10), ev(1,'RECEIPT',100)])['receipt_layers'][0]['remaining_quantity'] == '90'

@pytest.mark.parametrize('events', [
    [ev(1,'RECEIPT',10),ev(2,'ISSUE',11)],
    [ev(1,'RECEIPT',10),ev(1,'RECEIPT',10)],
    [ev(1,'RECEIPT',10),ev(2,'ISSUE',2),ev(3,'RETURN',3,source_issue_event_id=2)],
    [ev(1,'RECEIPT',10),ev(2,'RETURN',1,source_issue_event_id=99)],
    [ev(1,'RECEIPT',10),ev(2,'ISSUE',2),ev(3,'RETURN',1,rid=11,source_issue_event_id=2)],
    [ev(2,'ISSUE',1)],
    [ev(1,'RECEIPT',10),ev(2,'RECEIPT',20)],
    [ev(1,'RECEIPT',10),dict(ev(2,'ISSUE',1), project_id=3)],
    [ev(1,'RECEIPT',10),dict(ev(2,'ISSUE',1), material_id=12)],
    [ev(1,'RECEIPT',10),dict(ev(2,'ISSUE',1), quantity='NaN')],
])
def test_reject_invalid(events):
    with pytest.raises(ValueError): calc(events)

def test_timestamp_ties_rejected():
    a, b = ev(1,'RECEIPT',10), ev(2,'ISSUE',1)
    b['occurred_at'] = a['occurred_at']
    with pytest.raises(ValueError, match='ordering'): calc([a,b])
