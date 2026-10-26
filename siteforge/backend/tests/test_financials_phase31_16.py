from decimal import Decimal
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.domains.commercial_financials.models import FinanceApprovalPolicy, FinancePaymentApprovalLimit
from app.domains.commercial_financials.router import enforce_payment_authority, ApprovalPolicyIn

class Query:
    def __init__(self, rows): self.rows=list(rows)
    def filter_by(self,**kwargs): self.rows=[r for r in self.rows if all(getattr(r,k)==v for k,v in kwargs.items())];return self
    def all(self): return self.rows
    def one_or_none(self): return self.rows[0] if self.rows else None
class DB:
    def __init__(self, limits=(), policies=()): self.limits=limits;self.policies=policies
    def query(self,m): return Query(self.policies if m is FinanceApprovalPolicy else self.limits)

def test_strict_policy_rejects_missing_limits():
    db=DB(policies=[FinanceApprovalPolicy(project_id=3,payment_type='supplier',require_configured_authority=True)])
    with pytest.raises(HTTPException) as exc:enforce_payment_authority(db,3,5,'INR',Decimal('200'),'supplier')
    assert exc.value.status_code==403

def test_legacy_policy_remains_compatible():
    assert enforce_payment_authority(DB(),3,5,'INR',Decimal('200'),'supplier')=='legacy_unconfigured'

def test_strict_policy_accepts_limit_for_user_and_currency():
    db=DB(limits=[FinancePaymentApprovalLimit(project_id=3,user_id=5,payment_type='supplier',currency='INR',maximum_amount=Decimal('500'),active=True)],policies=[FinanceApprovalPolicy(project_id=3,payment_type='supplier',require_configured_authority=True)])
    assert enforce_payment_authority(db,3,5,'INR',Decimal('500'),'supplier')=='configured'
    with pytest.raises(HTTPException):enforce_payment_authority(db,3,5,'INR',Decimal('501'),'supplier')

def test_policy_rejects_invalid_aging():
    with pytest.raises(ValidationError): ApprovalPolicyIn(payment_type='supplier',require_configured_authority=True,overdue_after_hours=0,reason='valid reason')
