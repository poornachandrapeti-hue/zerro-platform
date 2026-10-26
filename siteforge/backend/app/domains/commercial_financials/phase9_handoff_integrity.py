"""Validate Finance-owned approved handoff payload integrity before GL read-back.

Pure validation, no writes and no certification. The digest and key follow
build_approved_handoff in movement_journal_proposals.py.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json


def validate_approved_handoff(handoff: dict) -> list[str]:
    if not isinstance(handoff, dict) or handoff.get('posting_status') != 'NOT_POSTED':
        return ['invalid_handoff']
    payload = handoff.get('journal_proposal')
    if not isinstance(payload, dict):
        return ['invalid_handoff']
    errors = []
    scope = ('organization_id', 'project_id', 'proposal_id',
             'proposal_revision', 'source_movement_line_id')
    if any(type(payload.get(k)) is not int or payload[k] <= 0 for k in scope):
        errors.append('invalid_proposal_identity')
    else:
        expected = 'finance-proposal:' + ':'.join(str(payload[k]) for k in scope[:4])
        if handoff.get('idempotency_key') != expected:
            errors.append('invalid_idempotency_key')
    if payload.get('schema_version') != 1:
        errors.append('invalid_schema_version')
    if not isinstance(payload.get('currency'), str) or len(payload['currency']) != 3 or not payload['currency'].isupper() or not payload['currency'].isalpha():
        errors.append('invalid_currency')
    lines = payload.get('lines')
    if not isinstance(lines, list) or not 2 <= len(lines) <= 100:
        errors.append('invalid_journal_lines')
    else:
        debit = Decimal(0); credit = Decimal(0)
        for line in lines:
            if not isinstance(line, dict) or type(line.get('cost_code_id')) is not int or line['cost_code_id'] <= 0:
                errors.append('invalid_journal_lines'); break
            try:
                dr = Decimal(line['debit']) if type(line.get('debit')) is str else None
                cr = Decimal(line['credit']) if type(line.get('credit')) is str else None
                if (dr is None or cr is None or not dr.is_finite() or not cr.is_finite()
                        or dr < 0 or cr < 0 or (dr > 0) == (cr > 0)
                        or dr.as_tuple().exponent != -2 or cr.as_tuple().exponent != -2):
                    raise ValueError()
                debit += dr; credit += cr
            except (InvalidOperation, ValueError, TypeError, KeyError):
                errors.append('invalid_journal_lines'); break
        try:
            total = Decimal(payload['balanced_total']) if type(payload.get('balanced_total')) is str else None
            if total is None or not total.is_finite() or total <= 0 or debit != credit or debit != total or total.as_tuple().exponent != -2:
                errors.append('invalid_journal_totals')
        except (InvalidOperation, ValueError, TypeError):
            errors.append('invalid_journal_totals')
    try:
        canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
        actual_digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        if handoff.get('payload_sha256') != actual_digest:
            errors.append('invalid_payload_digest')
    except (TypeError, ValueError, UnicodeError):
        errors.append('invalid_payload_digest')
    return sorted(set(errors))
