from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.domains.commercial_financials.router import _positive_money, remaining_balance, ExpenseIn, VariationIn, BalanceEntryIn

def test_money_validation():
    assert _positive_money(Decimal('10.20')) == Decimal('10.20')
    for amount in ('0','-0.01','NaN','1.123'):
        with pytest.raises(HTTPException): _positive_money(Decimal(amount))

def test_balances_account_for_recoveries():
    rows=[SimpleNamespace(amount=Decimal('250.00'),movement='Increase'),SimpleNamespace(amount=Decimal('100.00'),movement='Decrease')]
    assert remaining_balance(rows)==Decimal('150.00')
    with pytest.raises(ValueError):remaining_balance([SimpleNamespace(amount=Decimal('1.00'),movement='Decrease')])

def test_input_rejects_missing_financial_evidence():
    with pytest.raises(Exception):ExpenseIn(number='EX1',cost_code_id=1,source_reference='SRC',description='site expense',currency='INR',amount='10',evidence_reference='short')
    with pytest.raises(Exception):VariationIn(number='VO1',contract_id=1,description='new service',currency='INR',evidence_reference='short')
    with pytest.raises(Exception):BalanceEntryIn(contract_id=1,reference='REF',balance_type='Retention Held',movement='Increase',amount='50',evidence_reference='short')
