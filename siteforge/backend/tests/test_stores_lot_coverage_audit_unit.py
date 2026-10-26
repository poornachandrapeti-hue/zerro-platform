from app.domains.stores_inventory.lot_coverage_audit import coverage

def test_exact_allocation_remains_read_only():
    result = coverage('12.500', '12.500', 'Accept')
    assert result['fully_attributed'] and not result['issue_authorized']

def test_partial_is_flagged():
    result = coverage('10', '6', 'Issue')
    assert result['unattributed_quantity'] == '4'
    assert 'UNATTRIBUTED_QUANTITY' in result['flags']

def test_over_attribution_is_flagged():
    assert 'OVER_ATTRIBUTED_QUANTITY' in coverage('3', '5', 'Return')['flags']

def test_no_floating_point_rounding():
    assert coverage('0.300', '0.100', 'Accept')['unattributed_quantity'] == '0.200'

def test_invalid_negative():
    assert 'NEGATIVE_ATTRIBUTION' in coverage('2', '-1', 'Issue')['flags']
