"""Read-only Finance policy eligibility for indicative Stores movement provenance.

Approval of a costing policy is not authorization to value a movement or post journals.
"""

VALID_METHODS = frozenset({'FIFO', 'WEIGHTED_AVERAGE'})


def classify_policy_evidence(policies, receipt_currency):
    """Select the most recent revision; never fall back past an unapproved revision."""
    ordered = sorted(policies, key=lambda p: p.revision, reverse=True)
    if not ordered:
        return {'status': 'NO_APPROVED_POLICY', 'policy_id': None,
                'method': None, 'costing_policy_applied': False}
    latest = ordered[0]
    if latest.status != 'Approved' or latest.approved_by is None or latest.approved_at is None:
        status = 'LATEST_POLICY_NOT_APPROVED'
    elif latest.costing_method not in VALID_METHODS:
        status = 'UNSUPPORTED_COSTING_METHOD'
    elif not receipt_currency:
        status = 'RECEIPT_CURRENCY_UNVERIFIED'
    elif latest.currency != receipt_currency:
        status = 'CURRENCY_MISMATCH'
    else:
        status = 'POLICY_APPROVED_EVIDENCE_ONLY'
    return {'status': status, 'policy_id': latest.id,
            'revision': latest.revision, 'method': latest.costing_method,
            'currency': latest.currency, 'costing_policy_applied': False,
            'movement_valuation_verified': False, 'journal_posting_verified': False}
