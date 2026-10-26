from dataclasses import replace
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from app.domains.commercial_financials.receipt_cost_evidence import ReceiptCostEvidence, eligible_receipt_layers, preview_from_approved_evidence

T = datetime(2026, 10, 1, tzinfo=timezone.utc)
def example(**kwargs):
    default = dict(receipt_line_id=1, project_id=3, organization_id=2, material_id=9,
                   unit='KG', quantity_available=Decimal('10'), landed_unit_cost=Decimal('50'),
                   currency='INR', source_document_id='FIN-LC-1', approved_by=42,
                   approved_at=T + timedelta(days=1), receipt_posted_at=T, status='APPROVED')
    default.update(kwargs)
    return ReceiptCostEvidence(**default)

def opts(items):
    return dict(evidence=items, project_id=3, organization_id=2, material_id=9,
                unit='KG', currency='INR', issue_at=T+timedelta(days=4))

def test_fifo_sorts_eligible_receipts_by_posting_time():
    later=example(receipt_line_id=2, quantity_available=Decimal('20'), landed_unit_cost=Decimal('80'),
                  receipt_posted_at=T+timedelta(days=1), approved_at=T+timedelta(days=2))
    x=preview_from_approved_evidence(method='FIFO', issue_quantity=15, **opts([later,example()]))
    assert x['unposted_amount']=='900.00'
    assert x['source_receipt_line_ids']==[1,2]
    assert x['journal_posting_verified'] is False

@pytest.mark.parametrize('change', [
    {'project_id':4}, {'organization_id':7}, {'material_id':8}, {'unit':'M'},
    {'currency':'USD'}, {'status':'DRAFT'}, {'approved_by':0},
    {'source_document_id':' '}, {'quantity_available':Decimal('NaN')},
    {'landed_unit_cost':Decimal('-1')}, {'approved_at':T-timedelta(days=1)},
    {'approved_at':T+timedelta(days=5)}, {'receipt_posted_at':T+timedelta(days=5)},
    {'approved_at':datetime(2026,10,2)},
])
def test_refuse_unverified_evidence(change):
    with pytest.raises(ValueError): eligible_receipt_layers(**opts([example(**change)]))

def test_duplicate_evidence_refused():
    with pytest.raises(ValueError): eligible_receipt_layers(**opts([example(),example()]))

def test_missing_evidence_refused():
    with pytest.raises(ValueError): eligible_receipt_layers(**opts([]))
