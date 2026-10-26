"""Focused regression checks for Phase 31.4 contracts and receivables."""
from decimal import Decimal
from unittest.mock import MagicMock
from app.domains.commercial_financials.models import FinanceClientClaim, FinanceClientClaimLine, FinanceClientCollection
from app.domains.commercial_financials.router import client_receivables_data

def test_claim_source_line_unique():
    assert any(set(c.columns.keys()) == {'measurement_id'} for c in FinanceClientClaimLine.__table__.constraints if hasattr(c,'columns'))

def test_unique_collection_reference_per_project():
    assert any(set(c.columns.keys()) == {'project_id','transaction_reference'} for c in FinanceClientCollection.__table__.constraints if hasattr(c,'columns'))

def test_receivables_exclude_uncertified_and_separate_cash_from_revenue():
    claim=MagicMock();claim.id=1;claim.currency='INR';claim.status='Certified';claim.certified_value=Decimal('250.00')
    draft=MagicMock();draft.id=2;draft.currency='INR';draft.status='Submitted';draft.certified_value=Decimal('0.00')
    receipt=MagicMock();receipt.amount=Decimal('100.00')
    db=MagicMock();db.query.return_value.filter_by.side_effect=[MagicMock(all=lambda:[claim,draft]),MagicMock(all=lambda:[receipt])]
    results=client_receivables_data(db,99)['by_currency']['INR']
    assert results=={'client_certified_value':'250.00','collections':'100.00','receivables_outstanding':'150.00'}

def test_claim_has_separate_certification_fields():
    assert {'amount','certified_value','status','certified_by','certified_at'}.issubset(FinanceClientClaim.__table__.columns.keys())
