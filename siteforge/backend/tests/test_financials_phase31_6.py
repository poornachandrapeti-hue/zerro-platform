from decimal import Decimal
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.domains.commercial_financials.router import payment_remaining, PaymentRequestIn, PaymentRecordIn

def test_available_payable_respects_existing_allocations():
    assert payment_remaining(Decimal('1000'),Decimal('250'),Decimal('400'))==Decimal('350')
    with pytest.raises(ValueError):payment_remaining(Decimal('100'),Decimal('90'),Decimal('20'))

def test_request_needs_positive_amount_and_evidence():
    with pytest.raises(ValidationError):PaymentRequestIn(number='REQ',bill_id=1,amount='0',evidence_reference='evidence-ref')
    with pytest.raises(ValidationError):PaymentRequestIn(number='REQ',bill_id=1,amount='1.00',evidence_reference='short')

def test_payment_evidence_required_and_reference_unique_contract():
    with pytest.raises(ValidationError):PaymentRecordIn(amount='0.00',paid_at='2026-10-20T13:00:00Z',transaction_reference='BANK-1',evidence_reference='document-ref')
    with pytest.raises(ValidationError):PaymentRecordIn(amount='1.00',paid_at='2026-10-20T13:00:00Z',transaction_reference='x',evidence_reference='document-ref')
