from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.domains.commercial_financials.router import SupplierPaymentRequestIn, PaymentRecordIn, payment_remaining

def test_supplier_request_requires_valid_amount_and_evidence():
    with pytest.raises(ValidationError): SupplierPaymentRequestIn(number='PAY-1',invoice_posting_id=1,amount=0,evidence_reference='supplier-doc')
    with pytest.raises(ValidationError): SupplierPaymentRequestIn(number='PAY-1',invoice_posting_id=1,amount=100,evidence_reference='bad')

def test_supplier_request_needs_posted_invoice_reference():
    request=SupplierPaymentRequestIn(number='PAY-1',invoice_posting_id=13,amount=Decimal('100.00'),evidence_reference='supplier-document')
    assert request.invoice_posting_id==13

def test_partial_payment_ceiling():
    assert payment_remaining(Decimal('500.00'),Decimal('200.00'))==Decimal('300.00')
    with pytest.raises(ValueError): payment_remaining(Decimal('100.00'),Decimal('101.00'))
