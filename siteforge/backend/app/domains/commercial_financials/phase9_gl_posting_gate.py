"""Fail-closed Phase 9 Finance posting intent gate (no GL writes).

An approved proposal is NOT sufficient evidence of valued stock or a posted
journal. The Finance-owned posting adapter is intentionally not implemented.
This pure gate prepares a bounded, verifiable intent for a future integration.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from .phase9_handoff_integrity import validate_approved_handoff


def assess_posting_intent(handoff: dict, *, actor_id: int | None = None,
                          source_evidence: Mapping | None = None) -> dict:
    """Check immutable Finance handoff and independent valued-source evidence.

    `source_evidence` must be generated server-side by an authorized Finance
    valuation service, never from a client request. Returns eligibility only,
    never an authorization to write to a ledger.
    """
    blocked = {'eligible_for_finance_adapter': False,
               'gl_posted': False, 'journal_posting_verified': False,
               'movement_valuation_certified': False}
    errors = validate_approved_handoff(handoff)
    if errors:
        return {**blocked, 'reasons': errors}
    proposal = handoff['journal_proposal']
    if type(actor_id) is not int or actor_id <= 0:
        errors.append('finance_actor_required')
    if actor_id == proposal.get('finance_approved_by'):
        errors.append('independent_posting_actor_required')
    approved_at = proposal.get('finance_approved_at')
    try:
        if not isinstance(approved_at, str):
            raise ValueError()
        timestamp = datetime.fromisoformat(approved_at.replace('Z', '+00:00'))
        if timestamp.tzinfo is None or timestamp > datetime.now(timezone.utc):
            raise ValueError()
    except (ValueError, TypeError):
        errors.append('valid_finance_approval_timestamp_required')
    if not isinstance(source_evidence, Mapping):
        errors.append('authoritative_valued_source_required')
    else:
        for key in ('organization_id', 'project_id', 'source_movement_line_id', 'currency'):
            if source_evidence.get(key) != proposal.get(key):
                errors.append('valued_source_scope_mismatch')
                break
        if source_evidence.get('status') != 'FINANCE_VERIFIED':
            errors.append('source_valuation_not_finance_verified')
        if source_evidence.get('costing_policy_approved') is not True:
            errors.append('approved_costing_policy_required')
        if source_evidence.get('source_movement_posted') is not True:
            errors.append('posted_stock_movement_required')
        try:
            amount = source_evidence.get('movement_cost')
            value = Decimal(amount) if type(amount) is str else None
            total = Decimal(proposal['balanced_total'])
            if (value is None or not value.is_finite() or value <= 0 or
                    value.as_tuple().exponent != -2 or value != total):
                errors.append('source_cost_total_mismatch')
        except (InvalidOperation, TypeError, ValueError):
            errors.append('source_cost_total_mismatch')
    if errors:
        return {**blocked, 'reasons': sorted(set(errors))}
    return {**blocked, 'eligible_for_finance_adapter': True,
            'reasons': [], 'idempotency_key': handoff['idempotency_key'],
            'payload_sha256': handoff['payload_sha256'],
            'next_step': 'FINANCE_OWNED_ADAPTER_REQUIRED'}
