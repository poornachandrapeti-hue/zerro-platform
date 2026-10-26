"""Source-level return posting quantity/balance invariants; not live PG tests."""
from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.material_returns import _return_balance_after_posting


def test_valid_balanced_return():
    assert _return_balance_after_posting('500', '200', '50') == Decimal('550')


@pytest.mark.parametrize('on_hand,reserved,qty', [
    ('500','501','50'), ('-1','0','50'), ('500','-1','50'),
    ('500','0','0'), ('500','0','-1'), ('NaN','0','50'),
    ('500','Infinity','50'), ('500','0','NaN'),
    ('Infinity','0','50'),
])
def test_rejects_corrupt_balance_or_return(on_hand, reserved, qty):
    with pytest.raises(HTTPException) as err:
        _return_balance_after_posting(on_hand, reserved, qty)
    assert err.value.status_code == 409
