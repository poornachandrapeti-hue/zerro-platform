"""Boundary validation for Finance-owned journal proposal amounts."""
from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.domains.commercial_financials.movement_journal_proposals import validate_lines, JournalLine

def lines(a, b):
    return [SimpleNamespace(debit=Decimal(a), credit=Decimal('0')), SimpleNamespace(debit=Decimal('0'), credit=Decimal(b))]

def test_valid_cent_precision():
    assert validate_lines(lines('123.45','123.45')) == '123.45'

@pytest.mark.parametrize('amount', ['NaN','Infinity','-Infinity','1.001','-1','1000000000000000000'])
def test_bad_amounts_fail_closed(amount):
    with pytest.raises(HTTPException) as ex:
        validate_lines(lines(amount,amount))
    assert ex.value.status_code == 422

def test_zero_and_unbalanced_rejected():
    for a,b in [('0','0'),('10','9')]:
        with pytest.raises(HTTPException): validate_lines(lines(a,b))

def test_stored_json_is_revalidated():
    with pytest.raises(HTTPException): validate_lines([SimpleNamespace(debit=Decimal('NaN'),credit=Decimal('0'))]*2)

def test_too_many_lines_rejected():
    with pytest.raises(HTTPException): validate_lines(lines('1','1')*51)
