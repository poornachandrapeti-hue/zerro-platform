"""Read-only reconciliation of Finance-approved landed-charge batch allocations.

The caller must obtain batches and allocations from the Finance-authoritative
read path and verify receipt lineage, approval separation and project scope.
This does not post stock or financial journals.
"""
from decimal import Decimal, InvalidOperation


def _money(value, label):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f'Invalid {label}') from exc
    if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal('0.01')):
        raise ValueError(f'Invalid {label}: finite non-negative cents required')
    return amount


def reconcile_landed_cost_batches(*, batches, allocations, receipt_line_ids, currency):
    """Fail closed if allocations don't conserve each approved batch's amount.

    batches: [{batch_id, amount, currency, independently_approved}]
    allocations: [{batch_id, receipt_line_id, amount, currency}]
    receipt_line_ids: IDs of already scoped and verified GRN lines.
    """
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha() or currency != currency.upper():
        raise ValueError('Invalid currency')
    if not batches:
        raise ValueError('No approved landed-cost batches')
    allowed = set()
    for item in receipt_line_ids:
        if type(item) is not int or item <= 0 or item in allowed:
            raise ValueError('Duplicate or invalid receipt line reference')
        allowed.add(item)
    if not allowed:
        raise ValueError('Receipt lineage required')
    amounts = {}
    for b in batches:
        bid = b['batch_id']
        if type(bid) is not int or bid <= 0 or bid in amounts:
            raise ValueError('Duplicate or invalid batch ID')
        if b.get('independently_approved') is not True or b.get('currency') != currency:
            raise ValueError('Landed batch approval or currency not verified')
        amounts[bid] = _money(b['amount'], 'approved batch amount')
        if amounts[bid] <= 0:
            raise ValueError('Approved batch amount must be positive')
    total_by_batch = {bid: Decimal('0.00') for bid in amounts}
    seen = set()
    result = []
    for a in allocations:
        bid, rid = a['batch_id'], a['receipt_line_id']
        if bid not in amounts or type(rid) is not int or rid not in allowed:
            raise ValueError('Orphan batch or receipt allocation')
        if (bid, rid) in seen:
            raise ValueError('Duplicate landed charge allocation')
        if a.get('currency') != currency:
            raise ValueError('Landed allocation currency mismatch')
        seen.add((bid, rid))
        value = _money(a['amount'], 'landed allocation amount')
        total_by_batch[bid] += value
        result.append({'batch_id': bid, 'receipt_line_id': rid,
                       'amount': str(value.quantize(Decimal('0.01'))), 'currency': currency})
    if any(total_by_batch[bid] != amounts[bid] for bid in amounts):
        raise ValueError('Landed batch amounts are not fully reconciled')
    return {'status': 'RECONCILED_UNPOSTED_PREVIEW', 'currency': currency,
            'allocations': sorted(result, key=lambda a: (a['receipt_line_id'], a['batch_id'])),
            'batch_count': len(amounts), 'allocated_total': str(sum(amounts.values(), Decimal('0.00'))),
            'finance_source_verified': False, 'movement_valuation_verified': False,
            'journal_posting_verified': False}
