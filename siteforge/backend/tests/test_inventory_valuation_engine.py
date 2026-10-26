from decimal import Decimal
import pytest
from app.domains.commercial_financials.inventory_valuation_engine import CostLayer, calculate_issue_preview


def layers():
    return [CostLayer(1, Decimal('10'), Decimal('50'), 'INR'), CostLayer(2, Decimal('20'), Decimal('80'), 'INR')]


def test_fifo_partial():
    out = calculate_issue_preview('FIFO', '15', layers(), 'INR')
    assert out['unposted_amount'] == '900.00'
    assert out['fifo_allocations'] == [{'receipt_line_id': 1, 'quantity': '10'}, {'receipt_line_id': 2, 'quantity': '5'}]
    assert out['movement_valuation_verified'] is False


def test_weighted_average():
    out = calculate_issue_preview('WEIGHTED_AVERAGE', 15, layers(), 'INR')
    assert out['unposted_amount'] == '1050.00'
    assert out['fifo_allocations'] == []


@pytest.mark.parametrize('issue,layer_set,currency,method', [
    (31, layers(), 'INR', 'FIFO'), (0, layers(), 'INR', 'FIFO'),
    ('NaN', layers(), 'INR', 'FIFO'), ('Infinity', layers(), 'INR', 'FIFO'),
    (1, [], 'INR', 'FIFO'), (1, layers(), 'USD', 'FIFO'),
    (1, [CostLayer(1, Decimal('1'), Decimal('-2'), 'INR')], 'INR', 'FIFO'),
    (1, [CostLayer(1, Decimal('1'), Decimal('2'), 'INR'), CostLayer(1, Decimal('2'), Decimal('2'), 'INR')], 'INR', 'FIFO'),
    (1, layers(), 'INR', 'LIFO'),
])
def test_reject_bad_inputs(issue,layer_set,currency,method):
    with pytest.raises(ValueError):
        calculate_issue_preview(method, issue, layer_set, currency)
