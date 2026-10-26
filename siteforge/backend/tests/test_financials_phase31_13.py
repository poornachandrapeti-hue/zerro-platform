from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.domains.commercial_financials.procurement_integration import validate_line_entitlement


def po_line(id=1, quantity='10', unit_price='20'):
    return SimpleNamespace(id=id,quantity=Decimal(quantity),unit_price=Decimal(unit_price))


def invoice_line(id=1, quantity='5', rate='20'):
    return SimpleNamespace(purchase_order_line_id=id,quantity=Decimal(quantity),billed_unit_price=Decimal(rate))


def test_matched_line_and_partial_receipt():
    assert validate_line_entitlement({1:po_line()},[invoice_line()],{1:Decimal('8')},{1:Decimal('2')})==1


@pytest.mark.parametrize('lines,received,posted', [
    ([invoice_line(quantity='7')],{1:Decimal('6')},{1:Decimal('0')}),
    ([invoice_line(quantity='9')],{1:Decimal('10')},{1:Decimal('2')}),
    ([invoice_line(id=99)],{1:Decimal('10')},{1:Decimal('0')}),
    ([invoice_line(rate='21')],{1:Decimal('10')},{1:Decimal('0')}),
    ([invoice_line(quantity='0')],{1:Decimal('10')},{1:Decimal('0')}),
    ([],{1:Decimal('10')},{1:Decimal('0')}),
])
def test_mismatches_block_finance_post(lines,received,posted):
    with pytest.raises(HTTPException) as exc:
        validate_line_entitlement({1:po_line()},lines,received,posted)
    assert exc.value.status_code == 409


def test_repeated_invoice_lines_aggregate_before_match():
    with pytest.raises(HTTPException):
        validate_line_entitlement({1:po_line()},[invoice_line(quantity='5'),invoice_line(quantity='5')],{1:Decimal('9')},{1:Decimal('0')})
