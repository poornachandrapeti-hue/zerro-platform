"""Pure, read-only cost roll-forward for *verified* receipt layers and issue intents.

Not a physical allocation, perpetual ledger, Finance approval or GL posting. All
inputs must be scoped, chronologically verified and authorized by the caller.
Returns and landed-cost adjustments are deliberately excluded: they require
original-issue cost provenance and authoritative Finance adjustment evidence.
"""
from decimal import Decimal, ROUND_HALF_UP

from .inventory_valuation_engine import CostLayer, _positive, calculate_issue_preview


def preview_issue_rollforward(*, method: str, currency: str,
                              layers: list[CostLayer], issues: list[dict]) -> dict:
    """Calculate sequential issue previews without reusing the same opening balance.

    Each issue: {'issue_id': positive integer, 'quantity': positive decimal}.
    FIFO consumes the first available verified cost layer. Weighted-average uses
    a single opening weighted pool across these issues, with no intervening
    receipts, returns, transfers or adjustments. Amounts are rounded per issue
    using the existing preview engine; unrounded internal amounts are never
    assumed to be posted accounting amounts.
    """
    if not isinstance(issues, list) or not issues:
        raise ValueError('At least one ordered issue is required')
    # Reuse the existing validation of policy, currency and cost layers.
    if not layers:
        raise ValueError('Verified receipt valuation layers are required')
    minimum_quantity = min(_positive(layer.quantity, 'Layer quantity') for layer in layers)
    calculate_issue_preview(method, minimum_quantity, layers, currency)
    remaining = {layer.receipt_line_id: _positive(layer.quantity, 'Layer quantity') for layer in layers}
    pool_remaining = sum(remaining.values(), Decimal(0))
    seen = set()
    rows = []
    for issue in issues:
        if not isinstance(issue, dict):
            raise ValueError('Invalid issue intent')
        issue_id = issue.get('issue_id')
        if type(issue_id) is not int or issue_id <= 0 or issue_id in seen:
            raise ValueError('Issue IDs must be unique positive integers')
        seen.add(issue_id)
        qty = _positive(issue.get('quantity'), 'Issue quantity')
        active = [CostLayer(l.receipt_line_id, remaining[l.receipt_line_id], l.unit_cost, currency)
                  for l in layers if remaining[l.receipt_line_id] > 0] if method == 'FIFO' else layers
        if not active:
            raise ValueError('Insufficient valued receipt-layer quantity')
        if method == 'WEIGHTED_AVERAGE' and qty > pool_remaining:
            raise ValueError('Insufficient valued receipt-layer quantity')
        value = calculate_issue_preview(method, qty, active, currency) if method == 'FIFO' else calculate_issue_preview(method, qty, layers, currency)
        if method == 'FIFO':
            for allocation in value['fifo_allocations']:
                remaining[allocation['receipt_line_id']] -= Decimal(allocation['quantity'])
        pool_remaining -= qty
        rows.append({'issue_id': issue_id, 'issue_quantity': str(qty),
                     'unposted_amount': value['unposted_amount'],
                     'fifo_allocations': value['fifo_allocations']})
    return {'status': 'UNPOSTED_ROLLFORWARD_PREVIEW', 'method': method,
            'currency': currency, 'issues': rows,
            'total_unposted_amount': str(sum((Decimal(r['unposted_amount']) for r in rows), Decimal(0)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'remaining_pool_quantity': str(pool_remaining),
            'movement_valuation_verified': False, 'journal_posting_verified': False,
            'warning': 'Inputs and chronology are caller-supplied. No intermediate receipts, returns, transfers or adjustments; no posting or Finance authority is implied.'}
