"""Fail-closed chronology gate for receipt-backed issued stock.

Created timestamps provide a minimal historical ordering check, not financial
posting authority or proof of remaining layer availability.
"""
from datetime import datetime


def verify_receipt_acceptance_precedes_issue(issue_at, acceptance_events):
    if not isinstance(issue_at, datetime) or issue_at.tzinfo is None or issue_at.utcoffset() is None:
        raise ValueError('Posted issue timestamp must be timezone-aware')
    if not acceptance_events:
        raise ValueError('Missing posted receipt acceptance evidence')
    for receipt_line_id, accepted_at in acceptance_events:
        if type(receipt_line_id) is not int or receipt_line_id <= 0:
            raise ValueError('Invalid accepted receipt line identifier')
        if not isinstance(accepted_at, datetime) or accepted_at.tzinfo is None or accepted_at.utcoffset() is None:
            raise ValueError('Receipt acceptance timestamp must be timezone-aware')
        if accepted_at > issue_at:
            raise ValueError('Receipt stock acceptance occurred after material issue')
    return {'status': 'ACCEPTANCE_CHRONOLOGY_OK', 'historical_balance_verified': False,
            'movement_valuation_verified': False}
