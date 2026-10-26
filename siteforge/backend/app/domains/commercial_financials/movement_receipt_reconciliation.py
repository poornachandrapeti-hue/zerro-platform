"""Read-only reconciliation of posted issue-lot provenance to receipt-cost previews.

Never produces an authoritative valuation or a journal. Caller must load stock
posting lines and lot allocations from the same authorized project snapshot.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation


def positive(value, name):
    try:
        number = Decimal(str(value))
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise ValueError(f'Invalid {name}') from exc
    if not number.is_finite() or number <= 0:
        raise ValueError(f'Invalid {name}')
    return number


def reconcile_issue_receipt_evidence(*, organization_id, project_id, issues, allocations, lots, receipt_previews):
    """Issues: id, organization_id, project_id, material_id, unit, quantity.
    Allocations: stock_posting_line_id, receipt_lot_id, quantity, organization_id, project_id.
    Lots: id, goods_receipt_line_id, material_id, unit, organization_id, project_id.
    Receipt previews: receipt_line_id, status, unit_cost_preview, currency.
    All amounts are indicative; preview evidence is not Finance verified valuation.
    """
    for key, value in [('organization_id', organization_id), ('project_id', project_id)]:
        if type(value) is not int or value <= 0:
            raise ValueError(f'Invalid {key}')
    indexed_issues = {}
    indexed_lots = {}
    indexed_receipts = {}
    for entry, dest, id_key, kind in [(issues, indexed_issues, 'id', 'issue'), (lots, indexed_lots, 'id', 'lot'), (receipt_previews, indexed_receipts, 'receipt_line_id', 'receipt')]:
        for obj in entry:
            identifier = obj[id_key]
            if type(identifier) is not int or identifier <= 0 or identifier in dest:
                raise ValueError(f'Duplicate or invalid {kind} identifier')
            dest[identifier] = obj
    for item in [*issues, *lots, *allocations]:
        if (item['organization_id'], item['project_id']) != (organization_id, project_id):
            raise ValueError('Cross-organization or cross-project evidence')
    grouped = defaultdict(list)
    seen = set()
    for allocation in allocations:
        line_id, lot_id = allocation['stock_posting_line_id'], allocation['receipt_lot_id']
        if line_id not in indexed_issues or lot_id not in indexed_lots:
            raise ValueError('Orphan issue-to-lot allocation')
        if (line_id, lot_id) in seen:
            raise ValueError('Duplicate issue-to-lot allocation')
        seen.add((line_id, lot_id))
        issue, lot = indexed_issues[line_id], indexed_lots[lot_id]
        if (issue['material_id'], issue['unit']) != (lot['material_id'], lot['unit']):
            raise ValueError('Issue and receipt-lot material mismatch')
        grouped[line_id].append((lot, positive(allocation['quantity'], 'allocated quantity')))
    results = []
    for line_id, issue in indexed_issues.items():
        quantity = positive(issue['quantity'], 'issue quantity')
        linked = grouped[line_id]
        allocated = sum((q for _, q in linked), Decimal(0))
        if allocated > quantity:
            raise ValueError('Allocation exceeds posted issue quantity')
        missing = allocated != quantity
        currencies = set()
        indicative = Decimal(0)
        receipt_ids = []
        for lot, qty in linked:
            rid = lot['goods_receipt_line_id']
            receipt_ids.append(rid)
            cost = indexed_receipts.get(rid)
            if not cost or cost['status'] != 'COMPLETE_UNPOSTED_PREVIEW' or cost.get('unit_cost_preview') is None:
                missing = True
                continue
            curr = cost['currency']
            if not isinstance(curr, str) or len(curr) != 3 or not curr.isupper() or not curr.isalpha():
                raise ValueError('Invalid receipt currency')
            currencies.add(curr)
            indicative += qty * positive(cost['unit_cost_preview'], 'receipt unit cost preview')
        if len(currencies) > 1:
            raise ValueError('Mixed receipt currencies for issue')
        results.append({
            'stock_posting_line_id': line_id, 'issue_quantity': str(quantity),
            'allocated_quantity': str(allocated), 'receipt_line_ids': sorted(set(receipt_ids)),
            'status': 'INCOMPLETE_EVIDENCE' if missing else 'INDICATIVE_ONLY',
            'indicative_cost_preview': None if missing else str(indicative),
            'currency': next(iter(currencies)) if not missing and currencies else None,
            'movement_valuation_verified': False, 'journal_posting_verified': False,
            'warning': 'No authoritative receipt-layer remaining balances, costing chronology, or journal verification.'
        })
    return results
