"""Validate externally supplied general-ledger receipts against approved handoff.

This is a pure verifier. It does not query a GL, submit transactions, or certify that
its input was obtained from an authoritative ledger. That requires authenticated
read-back from a Finance-owned posting service.
"""
from decimal import Decimal, InvalidOperation

REQUIRED = ('idempotency_key','payload_sha256','organization_id','project_id',
            'proposal_id','proposal_revision','source_movement_line_id','currency')


def verify_gl_receipt(handoff: dict, receipt: dict) -> dict:
    reasons = []
    if not isinstance(handoff, dict) or not isinstance(receipt, dict):
        return {'matches_handoff': False, 'journal_posting_verified': False,
                'reasons': ['invalid_evidence_format']}
    payload = handoff.get('journal_proposal')
    if not isinstance(payload, dict) or handoff.get('posting_status') != 'NOT_POSTED':
        reasons.append('invalid_handoff')
        payload = {}
    for name in REQUIRED:
        expected = handoff.get(name) if name in ('idempotency_key','payload_sha256') else payload.get(name)
        if expected is None or receipt.get(name) is None or receipt.get(name) != expected:
            reasons.append('mismatched_' + name)
    if receipt.get('status') != 'POSTED' or not receipt.get('posted_at') or not receipt.get('posted_by'):
        reasons.append('posting_audit_missing')
    if not receipt.get('external_journal_id'):
        reasons.append('journal_id_missing')
    try:
        debit = Decimal(str(receipt.get('total_debit')))
        credit = Decimal(str(receipt.get('total_credit')))
        expected_total = Decimal(str(payload.get('balanced_total')))
        if (not debit.is_finite() or not credit.is_finite() or debit <= 0 or
                debit != credit or debit != expected_total):
            reasons.append('journal_totals_mismatch')
    except (InvalidOperation, TypeError, ValueError):
        reasons.append('journal_totals_invalid')
    return {'matches_handoff': not reasons, 'journal_posting_verified': False,
            'authoritative_ledger_readback_required': True,
            'reasons': sorted(set(reasons))}
