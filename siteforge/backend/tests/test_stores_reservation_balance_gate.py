"""Reservation gate: reject an inconsistent existing ledger before reserving."""
from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.atomic_lot_acceptance import _assert_acceptance_balance_invariants

def balance(on_hand, reserved):
    return SimpleNamespace(on_hand=Decimal(on_hand), reserved=Decimal(reserved))

@pytest.mark.parametrize("on_hand,reserved", [("-1", "0"), ("5", "-1"), ("3", "4"), ("NaN", "0"), ("5", "Infinity")])
def test_reservation_rejects_corrupt_aggregate_balance(on_hand, reserved):
    with pytest.raises(HTTPException) as err:
        _assert_acceptance_balance_invariants(balance(on_hand, reserved))
    assert err.value.status_code == 409

def test_consistent_balance_passes():
    _assert_acceptance_balance_invariants(balance("5", "2"))

def test_reservation_service_invokes_balance_check_before_coverage():
    import inspect
    from app.domains.stores_inventory.lot_reservations import reserve_lot
    source = inspect.getsource(reserve_lot)
    assert source.index("_assert_acceptance_balance_invariants(balance)") < source.index("_require_full_coverage(db")
