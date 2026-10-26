from app.domains.stores_inventory.lot_movement_review import assess_lot

BASE = dict(received=10, accepted_posting=10, issued=3, returned=1,
            qa_accepted=10, qa_rejected=0, qa_quarantined=0, qa_pending=0,
            attribution_current=True, expired=False, unmapped_outbound=False)

def test_reconciled_diagnostic_never_authorizes_issue():
    result = assess_lot(**BASE)
    assert result['provenance_reconciled'] is True
    assert result['available_to_issue'] is None
    assert result['issue_authorized'] is False

def test_overissued_blocked():
    assert 'OUTBOUND_EXCEEDS_RECEIPT_PROVENANCE' in assess_lot(**(BASE | {'issued': 11}))['reconciliation_flags']

def test_qa_revocation_stale():
    assert 'QA_VERSION_STALE_OR_MISSING' in assess_lot(**(BASE | {'attribution_current': False}))['reconciliation_flags']

def test_returns_exceed_issues():
    assert 'RETURNS_EXCEED_ISSUES' in assess_lot(**(BASE | {'returned': 4}))['reconciliation_flags']

def test_expiry_restriction():
    assert 'LOT_EXPIRED' in assess_lot(**(BASE | {'expired': True}))['reconciliation_flags']

def test_missing_historical_allocations():
    assert 'LEGACY_OUTBOUND_NOT_FULLY_ATTRIBUTED' in assess_lot(**(BASE | {'unmapped_outbound': True}))['reconciliation_flags']
