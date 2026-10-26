from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.domains.commercial_financials.router import validate_ra_balance_posting, remaining_balance, calculate_bill_payable


def test_advance_recovery_within_available_balance():
    validate_ra_balance_posting(Decimal('100'),Decimal('30'),Decimal('100'))


def test_advance_recovery_over_balance_is_rejected():
    with pytest.raises(HTTPException) as exc:
        validate_ra_balance_posting(Decimal('100.01'),Decimal('30'),Decimal('100'))
    assert exc.value.status_code==409


def test_negative_ledger_values_rejected():
    with pytest.raises(HTTPException):
        validate_ra_balance_posting(Decimal('-1'),Decimal('0'),Decimal('100'))


def test_retention_is_withheld_but_does_not_reduce_gross_cost():
    gross=Decimal('1000.00')
    assert calculate_bill_payable(gross,Decimal('50'),Decimal('100'),Decimal('0'))==Decimal('850.00')
    entries=[SimpleNamespace(movement='Increase',amount=Decimal('300')),
             SimpleNamespace(movement='Decrease',amount=Decimal('100'))]
    assert remaining_balance(entries)==Decimal('200')


def test_duplicate_balance_recovery_does_not_erase_history():
    entries=[SimpleNamespace(movement='Increase',amount=Decimal('100')),
             SimpleNamespace(movement='Decrease',amount=Decimal('100'))]
    assert remaining_balance(entries)==0
    with pytest.raises(HTTPException):
        validate_ra_balance_posting(Decimal('1'),Decimal('0'),remaining_balance(entries))
