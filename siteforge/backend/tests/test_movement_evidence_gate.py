from app.domains.commercial_financials.movement_evidence_gate import classify_movement_cost_readiness


def test_missing_evidence_fail_closed():
    r = classify_movement_cost_readiness(reconciliation={'status': 'INCOMPLETE_EVIDENCE'}, policy={}, lot_coverage=None)
    assert 'RECEIPT_COST_EVIDENCE_INCOMPLETE' in r['blockers']
    assert 'APPROVED_COSTING_POLICY_UNAVAILABLE' in r['blockers']
    assert not r['financial_value_authorized']


def test_indicative_receipt_and_approved_policy_still_not_posted():
    r = classify_movement_cost_readiness(reconciliation={'status': 'INDICATIVE_ONLY'}, policy={'status': 'POLICY_APPROVED_EVIDENCE_ONLY'}, lot_coverage={'status': 'INTAKE_CEILING_CHECK_ONLY'})
    assert 'FINANCE_MOVEMENT_VALUATION_UNPOSTED' in r['blockers']
    assert 'ACCOUNTING_JOURNAL_NOT_VERIFIED' in r['blockers']
    assert not r['journal_posting_verified']


def test_unknown_coverage_never_pretends_to_pass():
    r = classify_movement_cost_readiness(reconciliation={'status': 'INDICATIVE_ONLY'}, policy={'status':'POLICY_APPROVED_EVIDENCE_ONLY'},lot_coverage={'foo': 'bar'})
    assert 'HISTORICAL_LOT_INTAKE_UNVERIFIED' in r['blockers']
