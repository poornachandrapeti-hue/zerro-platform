from dataclasses import replace
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from app.domains.commercial_financials.movement_cost_gate import VerifiedReceiptLayer, preview_issue_from_verified_layers

T = datetime(2026, 1, 10, tzinfo=timezone.utc)

def layer(i=1, **changes):
    base = VerifiedReceiptLayer(i, 1, 2, 3, 'KG', 'INR', Decimal('10'), Decimal('50'),
        T, T + timedelta(days=1), f'FIN-{i}', 'VERIFIED')
    return replace(base, **changes)

def run(layers=None, **changes):
    args = dict(organization_id=1, project_id=2, material_id=3, unit='KG', currency='INR',
        method='FIFO', issue_quantity='5', issue_at=T+timedelta(days=3), layers=[layer()] if layers is None else layers)
    args.update(changes)
    return preview_issue_from_verified_layers(**args)

def test_valid_preview_stays_unposted():
    out=run()
    assert out['unposted_amount']=='250.00'
    assert out['journal_posting_verified'] is False
    assert out['remaining_stock_verified'] is False

@pytest.mark.parametrize('changes', [
    {'organization_id':2}, {'project_id':5}, {'material_id':9},
    {'unit':'TON'}, {'currency':'USD'}, {'finance_status':'PENDING'},
    {'finance_evidence_id':''}, {'available_quantity':Decimal('NaN')},
    {'verified_unit_cost':Decimal('-1')},
    {'receipt_posted_at':T+timedelta(days=4)},
    {'finance_verified_at':T+timedelta(days=5)},
    {'finance_verified_at':T-timedelta(days=1)},
])
def test_reject_invalid_evidence(changes):
    with pytest.raises(ValueError):run(layers=[layer(**changes)])

def test_reject_duplicate_receipt():
    with pytest.raises(ValueError):run(layers=[layer(),layer()])

def test_reject_duplicate_finance_evidence():
    with pytest.raises(ValueError):run(layers=[layer(),layer(2,finance_evidence_id='FIN-1')])

def test_reject_fifo_unsorted():
    with pytest.raises(ValueError):run(layers=[layer(2, receipt_posted_at=T+timedelta(hours=1)), layer(1)])

def test_reject_excess_issue():
    with pytest.raises(ValueError):run(issue_quantity='11')
