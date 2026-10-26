import pytest
from app.domains.commercial_financials.receipt_lot_coverage import audit_lot_issue_coverage


def lot(**updates):
    return dict(id=9, organization_id=1, project_id=2, quantity='10', **updates)


def alloc(**updates):
    return dict(stock_posting_line_id=51, receipt_lot_id=9, organization_id=1, project_id=2, quantity='4', **updates)


def run(lots=None, allocations=None):
    return audit_lot_issue_coverage(organization_id=1, project_id=2,
                                    lots=[lot()] if lots is None else lots,
                                    posted_allocations=[alloc()] if allocations is None else allocations)


def test_coverage_clearly_not_available_stock():
    result = run()
    assert result['lots'][0]['unallocated_intake_ceiling'] == '6'
    assert result['historical_stock_available_verified'] is False
    assert result['finance_valuation_verified'] is False


def test_multiple_issues_are_aggregated():
    entries = [alloc(), {**alloc(), 'stock_posting_line_id': 52, 'quantity': '6'}]
    assert run(allocations=entries)['lots'][0]['unallocated_intake_ceiling'] == '0'

@pytest.mark.parametrize('allocations', [
    [{**alloc(), 'quantity': '11'}],
    [alloc(), alloc()],
    [{**alloc(), 'organization_id': 99}],
    [{**alloc(), 'receipt_lot_id': 555}],
    [{**alloc(), 'quantity': 'NaN'}],
    [{**alloc(), 'quantity': '-1'}],
])
def test_bad_allocation_rejected(allocations):
    with pytest.raises(ValueError):
        run(allocations=allocations)


def test_empty_allocations():
    assert run(allocations=[])['lots'][0]['unallocated_intake_ceiling'] == '10'
