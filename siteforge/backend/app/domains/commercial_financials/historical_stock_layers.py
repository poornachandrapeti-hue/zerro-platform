"""Read-only historical receipt layer quantity reconstruction.

This is an evidence check, not an inventory ledger, costing authority, or GL journal.
Input events must be a complete, canonical snapshot of posted movement data.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from datetime import datetime


def _qty(value):
    try:
        result = Decimal(str(value))
    except (ValueError, TypeError, InvalidOperation):
        raise ValueError('Quantity must be finite and positive') from None
    if not result.is_finite() or result <= 0:
        raise ValueError('Quantity must be finite and positive')
    return result


def reconstruct_receipt_layers(*, organization_id: int, project_id: int, events: list[dict]):
    """Reconstruct outstanding quantities using explicit receipt-line references.

    Events require id, organization_id, project_id, receipt_line_id, material_id,
    unit, warehouse_id, occurred_at (timezone-aware datetime), kind
    (RECEIPT, ISSUE, RETURN), and quantity. Events are sorted by occurred_at/id;
    events sharing a timestamp are rejected to avoid hidden posting-order guesses.
    Returns must reference the original ISSUE event by source_issue_event_id.
    Returns restore quantity to the SAME receipt layer as their referenced issue.
    Cross-layer and over-return entries fail closed.
    """
    if type(organization_id) is not int or organization_id <= 0 or type(project_id) is not int or project_id <= 0:
        raise ValueError('Invalid organization or project')
    seen_ids = set()
    seen_times = set()
    normalized = []
    for e in events:
        if e.get('organization_id') != organization_id or e.get('project_id') != project_id:
            raise ValueError('Out-of-scope movement')
        event_id = e.get('id')
        if type(event_id) is not int or event_id <= 0 or event_id in seen_ids:
            raise ValueError('Duplicate or invalid movement ID')
        seen_ids.add(event_id)
        ts = e.get('occurred_at')
        if not isinstance(ts, datetime) or ts.tzinfo is None or ts.utcoffset() is None:
            raise ValueError('Timezone-aware posting timestamp required')
        if ts in seen_times:
            raise ValueError('Ambiguous movement ordering at same timestamp')
        seen_times.add(ts)
        if e.get('kind') not in ('RECEIPT', 'ISSUE', 'RETURN'):
            raise ValueError('Unsupported movement kind')
        for field in ('receipt_line_id', 'material_id', 'warehouse_id'):
            if type(e.get(field)) is not int or e[field] <= 0:
                raise ValueError(f'Invalid {field}')
        if not isinstance(e.get('unit'), str) or not e['unit'].strip():
            raise ValueError('Invalid unit')
        normalized.append((ts, event_id, e, _qty(e.get('quantity'))))
    normalized.sort(key=lambda x: (x[0], x[1]))
    balances = defaultdict(lambda: Decimal(0))
    layer_identity = {}
    issues = {}
    returned_by_issue = defaultdict(lambda: Decimal(0))
    for _, eid, e, quantity in normalized:
        rid = e['receipt_line_id']
        key = (e['material_id'], e['unit'], e['warehouse_id'])
        if rid in layer_identity and layer_identity[rid] != key:
            raise ValueError('Receipt layer identity mismatch')
        if e['kind'] == 'RECEIPT':
            if rid in layer_identity:
                raise ValueError('Duplicate receipt-layer opening')
            layer_identity[rid] = key
            balances[rid] = quantity
        else:
            if rid not in layer_identity:
                raise ValueError('Movement references unopened receipt layer')
            if layer_identity[rid] != key:
                raise ValueError('Movement material/unit/warehouse mismatch')
            if e['kind'] == 'ISSUE':
                if quantity > balances[rid]:
                    raise ValueError('Historical issue exceeds available layer quantity')
                balances[rid] -= quantity
                issues[eid] = (rid, quantity)
            else:
                original_id = e.get('source_issue_event_id')
                if type(original_id) is not int or original_id not in issues:
                    raise ValueError('Return must refer to earlier issue')
                original_rid, original_qty = issues[original_id]
                if rid != original_rid:
                    raise ValueError('Return receipt layer differs from original issue')
                if returned_by_issue[original_id] + quantity > original_qty:
                    raise ValueError('Return exceeds original issue')
                returned_by_issue[original_id] += quantity
                balances[rid] += quantity
    return {
        'status': 'HISTORICAL_QUANTITY_EVIDENCE_ONLY',
        'organization_id': organization_id,
        'project_id': project_id,
        'event_count': len(normalized),
        'receipt_layers': [{'receipt_line_id': rid, 'material_id': layer_identity[rid][0],
                            'unit': layer_identity[rid][1], 'warehouse_id': layer_identity[rid][2],
                            'remaining_quantity': str(balances[rid])} for rid in sorted(layer_identity)],
        'finance_valuation_verified': False,
        'journal_posting_verified': False,
        'warning': 'Requires a complete DB snapshot and verification against the canonical stock ledger; no monetary valuation or postings performed.'
    }
