"""Acceptance-side fail-closed invariants in the actual Stores service."""
from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.atomic_lot_acceptance import _assert_acceptance_balance_invariants


def _balance(on_hand, reserved):
    return SimpleNamespace(on_hand=Decimal(on_hand), reserved=Decimal(reserved))


@pytest.mark.parametrize('on_hand,reserved', [('-1','0'), ('5','-1'), ('2','3'), ('NaN','0'), ('5','Infinity')])
def test_acceptance_rejects_corrupt_balance(on_hand, reserved):
    with pytest.raises(HTTPException) as exc:
        _assert_acceptance_balance_invariants(_balance(on_hand, reserved))
    assert exc.value.status_code == 409


def test_acceptance_allows_consistent_balance():
    _assert_acceptance_balance_invariants(_balance('10.000', '4.000'))


def test_acceptance_service_calls_invariant_before_posting():
    import inspect
    from app.domains.stores_inventory.atomic_lot_acceptance import accept_lot
    source = inspect.getsource(accept_lot)
    assert source.index('_assert_acceptance_balance_invariants(balance)') < source.index('stock._save(')
