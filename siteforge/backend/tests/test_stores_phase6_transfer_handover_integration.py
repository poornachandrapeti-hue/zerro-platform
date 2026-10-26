from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.material_handovers import resolve_handover_source


def allocation(quantity):
    return SimpleNamespace(quantity=Decimal(str(quantity)))


def test_grn_handover_keeps_original_provenance():
    kind, item = resolve_handover_source([allocation('3.000')], [], Decimal('3'))
    assert kind == 'GRN' and item.quantity == Decimal('3')


def test_transfer_handover_uses_transfer_provenance():
    kind, item = resolve_handover_source([], [allocation(4)], Decimal('4'))
    assert kind == 'Transfer' and item.quantity == Decimal('4')


@pytest.mark.parametrize('grn,transfer,qty', [([], [], 1), ([allocation(2)], [allocation(2)], 2), ([allocation(1)], [], 2), ([], [allocation(2)], 1)])
def test_missing_ambiguous_or_partial_provenance_is_rejected(grn, transfer, qty):
    with pytest.raises(HTTPException) as error:
        resolve_handover_source(grn, transfer, qty)
    assert error.value.status_code == 409
