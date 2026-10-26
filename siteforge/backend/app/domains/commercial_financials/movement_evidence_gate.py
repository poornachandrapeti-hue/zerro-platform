"""Fail-closed accounting readiness diagnostics for the read-only Stores movement API.

This never authorizes stock valuation, accounting entries or billing.
"""


def classify_movement_cost_readiness(*, reconciliation, policy, lot_coverage):
    blockers = []
    if reconciliation.get('status') != 'INDICATIVE_ONLY':
        blockers.append('RECEIPT_COST_EVIDENCE_INCOMPLETE')
    if policy.get('status') != 'POLICY_APPROVED_EVIDENCE_ONLY':
        blockers.append('APPROVED_COSTING_POLICY_UNAVAILABLE')
    if not isinstance(lot_coverage, dict):
        blockers.append('HISTORICAL_LOT_INTAKE_UNVERIFIED')
    elif lot_coverage.get('status') != 'INTAKE_CEILING_CHECK_ONLY':
        # Never treat an unknown response shape as verified intake coverage.
        blockers.append('HISTORICAL_LOT_INTAKE_UNVERIFIED')
    blockers.extend(['FULL_CHRONOLOGICAL_STOCK_AVAILABILITY_UNVERIFIED',
                     'FINANCE_MOVEMENT_VALUATION_UNPOSTED',
                     'ACCOUNTING_JOURNAL_NOT_VERIFIED'])
    return {'status': 'BLOCKED_PENDING_AUTHORITATIVE_VALUATION',
            'blockers': blockers,
            'financial_value_authorized': False,
            'journal_posting_verified': False,
            'read_only': True}
