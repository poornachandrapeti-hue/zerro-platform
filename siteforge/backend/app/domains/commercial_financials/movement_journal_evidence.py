"""Fail-closed verification contract for external Finance-owned journal evidence.

Does not query a ledger, create journal records, or certify a movement on its own.
The source must be an authenticated Finance adapter returning authoritative postings.
"""
from decimal import Decimal, InvalidOperation


def _money(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('Invalid movement or journal amount') from None
    if not amount.is_finite() or amount <= 0:
        raise ValueError('Movement or journal amount must be positive and finite')
    return amount


def validate_journal_evidence(*, organization_id, project_id, movement_id,
                              currency, movement_amount, entries, finance_source_verified=False):
    """Validate evidence supplied by Finance; do not attest its origin.

    Each entry is a *complete* posting document with a unique posting id,
    balanced debit/credit totals, posted state and precise movement reference.
    Multiple documents for the same movement are rejected pending explicit
    adjustment/reversal handling by the Finance domain.
    """
    problems = []
    if not finance_source_verified:
        problems.append('FINANCE_SOURCE_NOT_AUTHENTICATED')
    if not isinstance(organization_id, int) or organization_id <= 0 or not isinstance(project_id, int) or project_id <= 0:
        problems.append('INVALID_ORGANIZATION_OR_PROJECT')
    if not isinstance(movement_id, int) or movement_id <= 0:
        problems.append('INVALID_MOVEMENT_ID')
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha() or not currency.isupper():
        problems.append('INVALID_CURRENCY')
    try:
        target_amount = _money(movement_amount)
    except ValueError:
        target_amount = None
        problems.append('INVALID_MOVEMENT_AMOUNT')
    if not isinstance(entries, list) or len(entries) != 1:
        problems.append('EXPECTED_ONE_AUTHORITATIVE_POSTING')
    else:
        e = entries[0]
        if not isinstance(e, dict):
            problems.append('INVALID_POSTING_EVIDENCE')
        else:
            if not e.get('posting_id') or not isinstance(e.get('posting_id'), str):
                problems.append('MISSING_POSTING_ID')
            if e.get('status') != 'POSTED':
                problems.append('JOURNAL_NOT_POSTED')
            if e.get('organization_id') != organization_id or e.get('project_id') != project_id:
                problems.append('JOURNAL_SCOPE_MISMATCH')
            if e.get('stock_movement_id') != movement_id:
                problems.append('JOURNAL_MOVEMENT_MISMATCH')
            if e.get('currency') != currency:
                problems.append('JOURNAL_CURRENCY_MISMATCH')
            if not e.get('posted_at') or not e.get('posted_by'):
                problems.append('MISSING_POSTING_AUDIT')
            try:
                debit, credit = _money(e.get('total_debit')), _money(e.get('total_credit'))
                if debit != credit:
                    problems.append('UNBALANCED_JOURNAL')
                if target_amount is not None and debit != target_amount:
                    problems.append('JOURNAL_AMOUNT_MISMATCH')
            except ValueError:
                problems.append('INVALID_JOURNAL_AMOUNT')
    return {
        'status': 'EVIDENCE_CONSISTENT_NOT_CERTIFIED' if not problems else 'BLOCKED',
        'issues': problems,
        'finance_source_authenticated': bool(finance_source_verified),
        'journal_posting_verified': False,
        'warning': 'Evidence consistency alone does not establish a Finance-ledger posting; authoritative read-back and independent reconciliation are required.',
    }
