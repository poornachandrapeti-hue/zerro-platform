from decimal import Decimal
from pydantic import ValidationError
from app.domains.commercial_financials.router import PaymentApprovalLimitIn
from app.domains.commercial_financials.models import FinanceAuthorityAudit, FinancePaymentDecisionAudit
from app.domains.commercial_financials.router import router

def test_authority_change_requires_reason():
    try:
        PaymentApprovalLimitIn(user_id=10,currency='INR',payment_type='supplier',maximum_amount=Decimal('100'))
        assert False, 'Missing audit reason must fail validation'
    except ValidationError:
        pass

def test_authority_change_accepts_reason():
    x=PaymentApprovalLimitIn(user_id=10,currency='INR',payment_type='supplier',maximum_amount=Decimal('100'),reason='Quarterly authority review')
    assert x.reason=='Quarterly authority review'

def test_audit_models_use_distinct_append_only_tables():
    assert FinanceAuthorityAudit.__tablename__=='finance_authority_audit'
    assert FinancePaymentDecisionAudit.__tablename__=='finance_payment_decision_audit'
    assert 'previous_amount' in FinanceAuthorityAudit.__table__.columns
    assert 'authority_mode' in FinancePaymentDecisionAudit.__table__.columns

def test_read_only_approval_audit_endpoint():
    paths=[(route.path,route.methods) for route in router.routes]
    assert any(path.endswith('/approval-audit') and methods=={'GET'} for path,methods in paths)
