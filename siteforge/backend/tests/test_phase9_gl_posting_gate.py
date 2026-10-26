from copy import deepcopy

from app.domains.commercial_financials.phase9_gl_posting_gate import assess_posting_intent
from tests.test_phase9_handoff_integrity import handoff


def evidence(h):
    p = h['journal_proposal']
    return dict(organization_id=p['organization_id'], project_id=p['project_id'],
                source_movement_line_id=p['source_movement_line_id'], currency=p['currency'],
                status='FINANCE_VERIFIED', costing_policy_approved=True,
                source_movement_posted=True, movement_cost=p['balanced_total'])


def test_missing_evidence_fails_closed():
    result = assess_posting_intent(handoff(), actor_id=88)
    assert not result['eligible_for_finance_adapter']
    assert 'authoritative_valued_source_required' in result['reasons']


def test_good_evidence_only_prepares_intent():
    h = handoff()
    result = assess_posting_intent(h, actor_id=88, source_evidence=evidence(h))
    assert result['eligible_for_finance_adapter']
    assert not result['gl_posted'] and not result['journal_posting_verified']
    assert not result['movement_valuation_certified']
    assert result['idempotency_key'] == h['idempotency_key']


def test_finance_approver_cannot_be_posting_actor():
    h = handoff()
    result = assess_posting_intent(h, actor_id=h['journal_proposal']['finance_approved_by'], source_evidence=evidence(h))
    assert 'independent_posting_actor_required' in result['reasons']


def test_source_cost_must_match_exactly():
    h = handoff(); e = evidence(h); e['movement_cost'] = '124.99'
    assert 'source_cost_total_mismatch' in assess_posting_intent(h, actor_id=88, source_evidence=e)['reasons']


def test_unapproved_cost_policy_blocked():
    h = handoff(); e = evidence(h); e['costing_policy_approved'] = False
    assert 'approved_costing_policy_required' in assess_posting_intent(h, actor_id=88, source_evidence=e)['reasons']


def test_unposted_movement_blocked():
    h = handoff(); e = evidence(h); e['source_movement_posted'] = False
    assert 'posted_stock_movement_required' in assess_posting_intent(h, actor_id=88, source_evidence=e)['reasons']


def test_cross_project_evidence_blocked():
    h = handoff(); e = evidence(h); e['project_id'] += 1
    assert 'valued_source_scope_mismatch' in assess_posting_intent(h, actor_id=88, source_evidence=e)['reasons']


def test_tampered_payload_never_eligible():
    h = handoff(); e = evidence(h)
    h['journal_proposal']['description'] = 'tampered'
    assert not assess_posting_intent(h, actor_id=88, source_evidence=e)['eligible_for_finance_adapter']


def test_client_supplied_status_without_valid_evidence_fails():
    h = handoff(); e = evidence(h); e['status'] = 'POSTED'
    assert 'source_valuation_not_finance_verified' in assess_posting_intent(h, actor_id=88, source_evidence=e)['reasons']


def test_missing_actor_fails():
    h = handoff()
    assert 'finance_actor_required' in assess_posting_intent(h, source_evidence=evidence(h))['reasons']
