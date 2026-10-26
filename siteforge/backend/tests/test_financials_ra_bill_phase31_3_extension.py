from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.domains.commercial_financials.router import calculate_bill_payable, next_bill_status, BillDeductions

def test_deductions_are_not_cost_additions():
    assert calculate_bill_payable(Decimal('225000'),Decimal('11250'),Decimal('1000'),Decimal('0'))==Decimal('212750.00')

def test_over_deduction_rejected():
    with pytest.raises(HTTPException) as err:calculate_bill_payable(Decimal('100'),Decimal('90'),Decimal('20'),Decimal('0'))
    assert err.value.status_code==422

def test_negative_amount_rejected():
    with pytest.raises(Exception):BillDeductions(retention_amount='-1',reason='Invalid amount')

def test_review_sequence():
    state='Draft'
    for action in ('submit','technical-approve','commercial-approve','post'):
        state=next_bill_status(state,action)
    assert state=='Posted'

def test_cannot_skip_approval():
    with pytest.raises(HTTPException):next_bill_status('Draft','post')

def test_post_is_not_payment():
    assert next_bill_status('Pending Approval','post')=='Posted'
