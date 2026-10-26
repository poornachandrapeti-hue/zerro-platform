from decimal import Decimal
import pytest
from app.domains.commercial_financials.inventory_valuation_engine import CostLayer
from app.domains.commercial_financials.phase9_valuation_rollforward import preview_issue_rollforward


def layers():
    return [CostLayer(11, Decimal('10'), Decimal('50'), 'INR'),
            CostLayer(12, Decimal('20'), Decimal('80'), 'INR')]


def preview(method, issues, receipt_layers=None):
    return preview_issue_rollforward(method=method, currency='INR',
                                     layers=layers() if receipt_layers is None else receipt_layers,
                                     issues=issues)


def test_fifo_sequential_issues_never_double_count_first_layer():
    result = preview('FIFO', [{'issue_id': 1, 'quantity': '8'}, {'issue_id': 2, 'quantity': '7'}])
    assert [r['unposted_amount'] for r in result['issues']] == ['400.00', '500.00']
    assert result['issues'][1]['fifo_allocations'] == [
        {'receipt_line_id': 11, 'quantity': '2'},
        {'receipt_line_id': 12, 'quantity': '5'}]
    assert result['remaining_pool_quantity'] == '15'
    assert result['total_unposted_amount'] == '900.00'
    assert result['journal_posting_verified'] is False


def test_weighted_average_maintains_opening_rate_in_no_receipts_window():
    result = preview('WEIGHTED_AVERAGE', [{'issue_id': 1, 'quantity': '8'},
                                           {'issue_id': 2, 'quantity': '7'}])
    assert [r['unposted_amount'] for r in result['issues']] == ['560.00', '490.00']
    assert result['total_unposted_amount'] == '1050.00'
    assert result['remaining_pool_quantity'] == '15'
    assert all(not r['fifo_allocations'] for r in result['issues'])


def test_partial_fractional_fifo_no_premature_rounding():
    rows = [CostLayer(1, Decimal('0.3'), Decimal('1.005'), 'INR')]
    result = preview('FIFO', [{'issue_id': 1, 'quantity': '0.1'},
                              {'issue_id': 2, 'quantity': '0.2'}], rows)
    assert [r['unposted_amount'] for r in result['issues']] == ['0.10', '0.20']
    assert result['remaining_pool_quantity'] == '0.0'


@pytest.mark.parametrize('method,issues,receipt_layers', [
    ('FIFO', [{'issue_id': 1, 'quantity': '31'}], None),
    ('WEIGHTED_AVERAGE', [{'issue_id': 1, 'quantity': '10'}, {'issue_id': 2, 'quantity': '21'}], None),
    ('FIFO', [{'issue_id': 1, 'quantity': '1'}, {'issue_id': 1, 'quantity': '1'}], None),
    ('FIFO', [{'issue_id': True, 'quantity': '1'}], None),
    ('FIFO', [{'issue_id': 1, 'quantity': 'NaN'}], None),
    ('FIFO', [{'issue_id': 1, 'quantity': '0'}], None),
    ('FIFO', [], None),
    ('LIFO', [{'issue_id': 1, 'quantity': '1'}], None),
    ('FIFO', [{'issue_id': 1, 'quantity': '1'}], [CostLayer(1, Decimal('2'), Decimal('3'), 'USD')]),
])
def test_fail_closed(method, issues, receipt_layers):
    with pytest.raises(ValueError):
        preview(method, issues, receipt_layers)
