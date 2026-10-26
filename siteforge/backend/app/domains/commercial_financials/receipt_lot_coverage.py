"""Read-only coverage check for outward allocations vs recorded receipt-lot intake.

This is NOT historical remaining stock: returns, transfers, reservations and
physical stock corrections require canonical stock-ledger replay.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation


def _positive(value):
    try:
        amount = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        raise ValueError('Invalid quantity') from None
    if not amount.is_finite() or amount <= 0:
        raise ValueError('Quantity must be positive and finite')
    return amount


def audit_lot_issue_coverage(*, organization_id, project_id, lots, posted_allocations):
    if type(organization_id) is not int or organization_id < 1 or type(project_id) is not int or project_id < 1:
        raise ValueError('Invalid project scope')
    lot_index = {}
    for lot in lots:
        if (lot['organization_id'], lot['project_id']) != (organization_id, project_id):
            raise ValueError('Out-of-scope receipt lot')
        lot_id = lot['id']
        if type(lot_id) is not int or lot_id <= 0 or lot_id in lot_index:
            raise ValueError('Duplicate or invalid receipt lot')
        lot_index[lot_id] = _positive(lot['quantity'])
    used = defaultdict(lambda: Decimal(0))
    seen = set()
    for allocation in posted_allocations:
        if (allocation['organization_id'], allocation['project_id']) != (organization_id, project_id):
            raise ValueError('Out-of-scope allocation')
        lot_id, issue_id = allocation['receipt_lot_id'], allocation['stock_posting_line_id']
        if lot_id not in lot_index or type(issue_id) is not int or issue_id < 1:
            raise ValueError('Orphan or invalid posted allocation')
        if (issue_id, lot_id) in seen:
            raise ValueError('Duplicate posted issue-lot reference')
        seen.add((issue_id, lot_id))
        used[lot_id] += _positive(allocation['quantity'])
        if used[lot_id] > lot_index[lot_id]:
            raise ValueError('Posted allocations exceed lot intake quantity')
    return {
        'status': 'INTAKE_CEILING_CHECK_ONLY',
        'organization_id': organization_id, 'project_id': project_id,
        'lots': [{'receipt_lot_id': i, 'intake_quantity': str(lot_index[i]),
                  'posted_outbound_allocated': str(used[i]),
                  'unallocated_intake_ceiling': str(lot_index[i] - used[i])}
                 for i in sorted(lot_index)],
        'historical_stock_available_verified': False,
        'finance_valuation_verified': False,
        'journal_posting_verified': False,
        'warning': 'Intake ceiling only; NOT free stock or historical availability. Returns, transfers, reservations and other ledger movements not replayed.'
    }
