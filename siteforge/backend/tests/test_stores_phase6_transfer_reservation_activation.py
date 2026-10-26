from decimal import Decimal
from fastapi import HTTPException
import pytest
from app.domains.stores_inventory.transfer_reservation_activation import activation_limits, _activation_gate


def test_activation_boundaries():
    assert activation_limits(lot_quantity='10', requested='4', other_held='6', warehouse_available='9', approved_remaining='5') == Decimal('4')

@pytest.mark.parametrize('values', [
    ('10','5','6','20','20'), ('10','5','0','3','20'),
    ('10','5','0','20','4'), ('NaN','1','0','5','5'),
    ('10','-1','0','10','10'), ('10','1','-2','10','10'),
])
def test_activation_fail_closed(values):
    with pytest.raises(HTTPException):
        activation_limits(lot_quantity=values[0], requested=values[1], other_held=values[2], warehouse_available=values[3], approved_remaining=values[4])


def test_activation_default_off(monkeypatch):
    monkeypatch.delenv('STORES_TRANSFER_RESERVATION_ACTIVATION_ENABLED', raising=False)
    monkeypatch.delenv('STORES_LOT_WRITER_CUTOVER', raising=False)
    with pytest.raises(HTTPException) as err:
        _activation_gate()
    assert err.value.status_code == 503
