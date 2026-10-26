from types import SimpleNamespace
from app.domains.commercial_financials.movement_policy_evidence import classify_policy_evidence


def policy(**updates):
    values = dict(id=1, revision=1, status='Approved', approved_by=2,
                  approved_at='2026-01-01', costing_method='FIFO', currency='INR')
    values.update(updates)
    return SimpleNamespace(**values)


def test_no_policy():
    assert classify_policy_evidence([], 'INR')['status'] == 'NO_APPROVED_POLICY'


def test_approved_fifo_is_evidence_only():
    r = classify_policy_evidence([policy()], 'INR')
    assert r['status'] == 'POLICY_APPROVED_EVIDENCE_ONLY'
    assert not r['costing_policy_applied']
    assert not r['movement_valuation_verified']


def test_weighted_average():
    assert classify_policy_evidence([policy(costing_method='WEIGHTED_AVERAGE')], 'INR')['status'] == 'POLICY_APPROVED_EVIDENCE_ONLY'


def test_no_fallback_to_old_approved_policy():
    r = classify_policy_evidence([policy(), policy(id=2,revision=2,status='Draft',approved_by=None,approved_at=None)], 'INR')
    assert r['status'] == 'LATEST_POLICY_NOT_APPROVED'
    assert r['policy_id'] == 2


def test_mismatched_currency():
    assert classify_policy_evidence([policy()], 'USD')['status'] == 'CURRENCY_MISMATCH'


def test_missing_receipt_currency():
    assert classify_policy_evidence([policy()], None)['status'] == 'RECEIPT_CURRENCY_UNVERIFIED'


def test_unsupported_method():
    assert classify_policy_evidence([policy(costing_method='LIFO')], 'INR')['status'] == 'UNSUPPORTED_COSTING_METHOD'


def test_missing_independent_approval_evidence():
    assert classify_policy_evidence([policy(approved_by=None)], 'INR')['status'] == 'LATEST_POLICY_NOT_APPROVED'
