from decimal import Decimal
from types import SimpleNamespace
from app.domains.stores_inventory.allocation_lifecycle import summarize


def row(id, quantity, remaining, status='Active'):
    return SimpleNamespace(id=id, quantity=Decimal(quantity), remaining_quantity=Decimal(remaining), status=status)


def test_no_allocations():
    r = summarize('100', [], {})
    assert r['unallocated_quantity'] == '100'


def test_partial_issue_and_partial_release_do_not_count_as_progress():
    r = summarize('100', [row(1, '60', '25')], {1: Decimal('15')})
    assert r['active_reserved_quantity'] == '25'
    assert r['consumed_by_issue'] == '20'
    assert r['released_quantity'] == '15'
    assert r['unallocated_quantity'] == '55'


def test_fully_released_can_be_reallocated():
    r = summarize('30', [row(1, '30', '0', 'Released')], {1: Decimal('30')})
    assert r['unallocated_quantity'] == '30'


def test_overcommit_flagged_not_hidden():
    r = summarize('10', [row(1, '11', '11')], {})
    assert r['overcommitted'] is True


def test_inconsistent_lifecycle_rejected():
    try:
        summarize('10', [row(1, '10', '8')], {1: Decimal('4')})
    except ValueError:
        pass
    else:
        assert False, 'must reject inconsistent history'
