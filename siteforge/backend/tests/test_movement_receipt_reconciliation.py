import pytest
from app.domains.commercial_financials.movement_receipt_reconciliation import reconcile_issue_receipt_evidence


def sample():
    return dict(organization_id=1, project_id=2,
        issues=[dict(id=10, organization_id=1, project_id=2, material_id=3, unit='KG', quantity='5')],
        lots=[dict(id=20, organization_id=1, project_id=2, material_id=3, unit='KG', goods_receipt_line_id=30)],
        allocations=[dict(stock_posting_line_id=10, receipt_lot_id=20, quantity='5', organization_id=1, project_id=2)],
        receipt_previews=[dict(receipt_line_id=30, status='COMPLETE_UNPOSTED_PREVIEW', unit_cost_preview='2.5', currency='INR')])


def test_indicative_only():
    result = reconcile_issue_receipt_evidence(**sample())[0]
    assert result['indicative_cost_preview'] == '12.5'
    assert result['movement_valuation_verified'] is False
    assert result['status'] == 'INDICATIVE_ONLY'


def test_partial_is_incomplete():
    data = sample(); data['allocations'][0]['quantity'] = '3'
    assert reconcile_issue_receipt_evidence(**data)[0]['indicative_cost_preview'] is None

@pytest.mark.parametrize('change', [
    lambda d: d['allocations'][0].update(quantity='6'),
    lambda d: d['allocations'][0].update(quantity='NaN'),
    lambda d: d['allocations'][0].update(receipt_lot_id=999),
    lambda d: d['lots'][0].update(material_id=100),
    lambda d: d['allocations'][0].update(project_id=9),
    lambda d: d['receipt_previews'].append(d['receipt_previews'][0].copy()),
])
def test_bad_evidence(change):
    data = sample(); change(data)
    with pytest.raises(ValueError): reconcile_issue_receipt_evidence(**data)


def test_incomplete_receipt_preview():
    data = sample(); data['receipt_previews'][0]['status'] = 'INCOMPLETE_INVOICE_ALLOCATION'
    assert reconcile_issue_receipt_evidence(**data)[0]['status'] == 'INCOMPLETE_EVIDENCE'
