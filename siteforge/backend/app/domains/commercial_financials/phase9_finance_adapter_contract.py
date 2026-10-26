"""Finance-owned GL adapter boundary for Phase 9.

This module does not implement GL writes, authorize a ledger, or certify postings.
It prepares an immutable, scoped request after independently verifying Finance
posting eligibility. The live Finance-owned posting implementation is required.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, Any

from .phase9_gl_posting_gate import assess_posting_intent
from .gl_readback_contract import inspect_finance_ledger_readback


class FinancePostingAdapter(Protocol):
    """To be implemented and security-reviewed in the authoritative Finance service.

    Both methods must enforce organization/project scope and use a durable unique
    idempotency key inside one authoritative posting transaction. Implementations
    must not trust data supplied by browser clients.
    """
    def submit_approved_journal(self, *, organization_id: int, project_id: int,
                                idempotency_key: str, payload_sha256: str,
                                journal_proposal: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def fetch_by_idempotency_key(self, *, organization_id: int, project_id: int,
                                 idempotency_key: str) -> list[Mapping[str, Any]]: ...


def prepare_finance_submission(handoff: dict, *, actor_id: int | None,
                               source_evidence: Mapping | None) -> dict:
    """Prepare a Finance handoff; no database/network side effects."""
    eligibility = assess_posting_intent(handoff, actor_id=actor_id,
                                        source_evidence=source_evidence)
    if not eligibility['eligible_for_finance_adapter']:
        return {**eligibility, 'submission_prepared': False}
    proposal = handoff['journal_proposal']
    return {**eligibility, 'submission_prepared': True,
            'organization_id': proposal['organization_id'],
            'project_id': proposal['project_id'],
            'journal_proposal': proposal,
            'posting_status': 'NOT_POSTED'}


def inspect_after_external_submission(handoff: dict, *, adapter: FinancePostingAdapter | None) -> dict:
    """Independently read back a Finance posting; cannot certify trust by itself.

    Does not initiate posting, to avoid accidentally re-posting journal lines.
    Ledger authority, authenticated transport, and durable idempotency have to be
    supplied and reviewed separately.
    """
    result = inspect_finance_ledger_readback(handoff, adapter=adapter)
    return {**result, 'gl_posted': False, 'journal_posting_verified': False,
            'finance_adapter_certification_pending': True}
