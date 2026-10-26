"""Static policy surface checks; not a substitute for database integration tests."""
from decimal import Decimal
from fastapi import HTTPException
from app.domains.commercial_financials.inventory_costing_policy import PolicyInput, policy_out, METHODS

def test_methods_are_explicit():
    assert METHODS == {'FIFO','WEIGHTED_AVERAGE'}

def test_policy_currency_validated():
    try: PolicyInput(costing_method='FIFO',currency='INR1',effective_note='Test project policy')
    except Exception: pass
    else: assert False, 'Invalid ISO code accepted'

def test_policy_is_not_valuer_or_journal():
    class Row:
        id=1;project_id=3;revision=1;costing_method='FIFO';currency='INR'
        effective_note='Chosen by Finance';status='Approved';created_by=10
        submitted_by=10;approved_by=11;approved_at=None;decision_reason='Approved'
    data=policy_out(Row())
    assert data['movement_valuation_ready'] is False
    assert data['journal_posting_ready'] is False
