"""Read-only bounded audit of approved Finance journal handoffs.

Never posts or certifies accounting. A trusted Finance adapter is required for
ledger read-back; duplicate proposal keys or journal IDs fail closed.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from .gl_readback_contract import FinanceLedgerReadback, inspect_finance_ledger_readback

MAX_BATCH_SIZE = 100


def reconcile_handoff_batch(handoffs: Sequence[dict[str, Any]],
                            adapter: FinanceLedgerReadback | None = None) -> dict[str, Any]:
    """Return exception evidence, never GL certification or ledger mutations."""
    if not isinstance(handoffs, (list, tuple)) or not (1 <= len(handoffs) <= MAX_BATCH_SIZE):
        raise ValueError('handoff batch must contain between 1 and 100 records')
    keys = []
    for handoff in handoffs:
        if not isinstance(handoff, Mapping):
            raise ValueError('handoff records must be objects')
        payload = handoff.get('journal_proposal')
        key = handoff.get('idempotency_key')
        if not isinstance(payload, Mapping) or not isinstance(key, str) or not key:
            raise ValueError('handoff requires a proposal and idempotency key')
        keys.append((payload.get('organization_id'), payload.get('project_id'), key))
    duplicates = {key for key, count in Counter(keys).items() if count > 1}
    rows = []
    journal_ids = []
    for index, handoff in enumerate(handoffs):
        key = keys[index]
        if key in duplicates:
            result = {'matches_handoff': False, 'journal_posting_verified': False,
                      'movement_valuation_certified': False,
                      'reasons': ['duplicate_handoff_key']}
        else:
            result = inspect_finance_ledger_readback(dict(handoff), adapter)
        journal_id = result.get('ledger_reference')
        if journal_id:
            journal_ids.append(journal_id)
        rows.append({'index': index, 'idempotency_key': key[2], **result})
    duplicate_journals = {jid for jid, count in Counter(journal_ids).items() if count > 1}
    for row in rows:
        if row.get('ledger_reference') in duplicate_journals:
            row.update(matches_handoff=False, ledger_reference=None,
                       journal_posting_verified=False, movement_valuation_certified=False,
                       reasons=['duplicate_external_journal_reference'])
    matched = sum(bool(row.get('matches_handoff')) for row in rows)
    return {'total': len(rows), 'matched_readbacks': matched,
            'exceptions': len(rows) - matched, 'journal_posting_verified': False,
            'movement_valuation_certified': False, 'rows': rows}
