from decimal import Decimal
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.domains.commercial_financials.router import PaymentApprovalLimitIn, enforce_payment_authority
from app.domains.commercial_financials.models import FinancePaymentApprovalLimit, FinanceApprovalPolicy

class FakeQuery:
    def __init__(self,items):self.items=items
    def filter_by(self,**kwargs):self.items=[x for x in self.items if all(getattr(x,k)==v for k,v in kwargs.items())];return self
    def one_or_none(self):return self.items[0] if self.items else None
    def all(self):return self.items
class FakeDb:
    def __init__(self,items):self.items=items
    def query(self,model):
        assert model in (FinancePaymentApprovalLimit, FinanceApprovalPolicy)
        return FakeQuery(self.items[:] if model is FinancePaymentApprovalLimit else [])

def test_unconfigured_preserves_existing_approvals():
    assert enforce_payment_authority(FakeDb([]),1,2,'INR',Decimal('100'),'supplier')=='legacy_unconfigured'

def test_authority_scoped_to_user_currency_and_payment_type():
    policies=[FinancePaymentApprovalLimit(project_id=1,user_id=2,currency='INR',payment_type='supplier',maximum_amount=Decimal('500'),active=True)]
    db=FakeDb(policies)
    assert enforce_payment_authority(db,1,2,'INR',Decimal('500'),'supplier')=='configured'
    for user,currency,amount in [(3,'INR',Decimal('10')),(2,'USD',Decimal('10')),(2,'INR',Decimal('501'))]:
        with pytest.raises(HTTPException) as e:enforce_payment_authority(db,1,user,currency,amount,'supplier')
        assert e.value.status_code==403
    assert enforce_payment_authority(db,1,3,'INR',Decimal('999'),'subcontract')=='legacy_unconfigured'

def test_inactive_authority_denied():
    policy=FinancePaymentApprovalLimit(project_id=1,user_id=2,currency='INR',payment_type='subcontract',maximum_amount=Decimal('1000'),active=False)
    with pytest.raises(HTTPException):enforce_payment_authority(FakeDb([policy]),1,2,'INR',Decimal('1'),'subcontract')

def test_policy_input_validation():
    with pytest.raises(ValidationError):PaymentApprovalLimitIn(user_id=2,currency='IN',payment_type='supplier',maximum_amount=100)
    with pytest.raises(ValidationError):PaymentApprovalLimitIn(user_id=2,currency='INR',payment_type='supplier',maximum_amount=-1)
