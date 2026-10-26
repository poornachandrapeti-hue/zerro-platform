"""Pure service-level invariants; database service tests still required."""
from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.atomic_lot_issue import _assert_issue_balance_invariants


def balance(hand, reserved):
    return SimpleNamespace(on_hand=Decimal(hand), reserved=Decimal(reserved))


@pytest.mark.parametrize("hand,reserved", [("-1", "0"), ("1", "-1"), ("2", "3")])
def test_corrupt_aggregate_balance_is_rejected(hand, reserved):
    with pytest.raises(HTTPException) as err:
        _assert_issue_balance_invariants(balance(hand, reserved), Decimal("1"), True)
    assert err.value.status_code == 409


def test_reservation_issue_cannot_underflow_aggregate_reserved():
    with pytest.raises(HTTPException) as err:
        _assert_issue_balance_invariants(balance("10", "0.500"), Decimal("1"), True)
    assert err.value.status_code == 409


def test_reserved_issue_with_consistent_balance_is_allowed():
    _assert_issue_balance_invariants(balance("10", "3"), Decimal("2"), True)


def test_direct_issue_with_sufficient_physical_balance_is_allowed():
    _assert_issue_balance_invariants(balance("10", "0"), Decimal("2"), False)


def test_issue_above_physical_balance_is_rejected():
    with pytest.raises(HTTPException) as err:
        _assert_issue_balance_invariants(balance("2", "1"), Decimal("3"), True)
    assert err.value.status_code == 409
