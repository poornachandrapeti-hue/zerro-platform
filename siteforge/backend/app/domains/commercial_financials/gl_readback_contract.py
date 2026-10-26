"""Fail-closed Finance GL read-back adapter contract.

No GL backend is installed here. A future Finance-owned adapter must perform an
independent authenticated ledger query; caller-supplied receipts are not trusted.
This module never marks a journal posted or financially certified by itself.
"""
from __future__ import annotations

from typing import Protocol, Mapping, Any
from .gl_receipt_verification import verify_gl_receipt
from .phase9_handoff_integrity import validate_approved_handoff


class FinanceLedgerReadback(Protocol):
    """Adapter implemented by the authoritative Finance service only.

    fetch_by_idempotency_key must authenticate to Finance, scope organization
    and project in its query, and return *all* matching ledger postings.
    """
    def fetch_by_idempotency_key(self, *, organization_id: int, project_id: int,
                                 idempotency_key: str) -> list[Mapping[str, Any]]: ...


def inspect_finance_ledger_readback(handoff: dict, adapter: FinanceLedgerReadback | None = None) -> dict:
    """Compare a handoff against an independent ledger read-back; no writes.

    `matches_handoff` establishes consistency, not GL posting certification.
    An unconfigured adapter must not fall back to client-supplied receipt data.
    """
    blocked = {'matches_handoff': False, 'journal_posting_verified': False,
               'movement_valuation_certified': False,
               'authoritative_ledger_readback_required': True}
    if not isinstance(handoff, dict) or handoff.get('posting_status') != 'NOT_POSTED':
        return {**blocked, 'reasons': ['invalid_handoff']}
    payload = handoff.get('journal_proposal')
    if not isinstance(payload, dict) or not isinstance(handoff.get('idempotency_key'), str) or not handoff['idempotency_key']:
        return {**blocked, 'reasons': ['invalid_handoff']}
    try:
        org = payload['organization_id']; project = payload['project_id']
        if type(org) is not int or type(project) is not int or org <= 0 or project <= 0:
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        return {**blocked, 'reasons': ['invalid_scope']}
    integrity_errors = validate_approved_handoff(handoff)
    if integrity_errors:
        return {**blocked, 'reasons': integrity_errors}
    if adapter is None:
        return {**blocked, 'reasons': ['finance_ledger_adapter_not_configured']}
    try:
        receipts = adapter.fetch_by_idempotency_key(
            organization_id=org, project_id=project,
            idempotency_key=handoff['idempotency_key'])
    except Exception:
        # No remote exception bodies or credentials may leak to callers.
        return {**blocked, 'reasons': ['finance_ledger_readback_failed']}
    if not isinstance(receipts, list):
        return {**blocked, 'reasons': ['invalid_finance_readback_response']}
    if len(receipts) == 0:
        return {**blocked, 'reasons': ['finance_journal_not_found']}
    if len(receipts) != 1:
        return {**blocked, 'reasons': ['ambiguous_finance_ledger_postings']}
    receipt = receipts[0]
    if not isinstance(receipt, Mapping):
        return {**blocked, 'reasons': ['invalid_finance_readback_response']}
    result = verify_gl_receipt(handoff, dict(receipt))
    # Even a matching independently fetched record cannot certify the ledger
    # unless the provider implementation and trust boundary are reviewed.
    return {**blocked, 'matches_handoff': result['matches_handoff'],
            'reasons': result['reasons'], 'readback_source': 'finance_adapter',
            'ledger_reference': receipt.get('external_journal_id') if result['matches_handoff'] else None}
