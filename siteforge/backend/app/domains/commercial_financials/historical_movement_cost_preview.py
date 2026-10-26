"""Read-only as-of-issue cost preview from complete, independently verified evidence.

Does not establish database completeness, approval, actual costing authority or GL posting.
"""
from decimal import Decimal
from .historical_stock_layers import reconstruct_receipt_layers
from .inventory_valuation_engine import CostLayer, calculate_issue_preview


def preview_historical_issue(*, organization_id: int, project_id: int, events: list[dict],
                             issue_event_id: int, verified_unit_costs: dict[int, str],
                             method: str, currency: str) -> dict:
    """Require complete canonical ordered events through the selected issue.

    Rates are supplied only from independently authenticated Finance evidence by
    the caller. FIFO here is a *costing preview*, not a physical lot allocation.
    """
    if type(issue_event_id) is not int or issue_event_id <= 0:
        raise ValueError('Invalid issue event ID')
    matches = [e for e in events if e.get('id') == issue_event_id]
    if len(matches) != 1 or matches[0].get('kind') != 'ISSUE':
        raise ValueError('Selected event must be exactly one posted issue')
    target = matches[0]
    ts = target.get('occurred_at')
    if ts is None:
        raise ValueError('Issue timestamp required')
    # Reject incomplete/invalid future evidence as well, so a caller cannot
    # hide an out-of-scope event by putting it after the selected issue.
    reconstruct_receipt_layers(organization_id=organization_id, project_id=project_id, events=events)
    prefix = [e for e in events if e['occurred_at'] < ts]
    before = reconstruct_receipt_layers(organization_id=organization_id, project_id=project_id, events=prefix)
    eligible = [r for r in before['receipt_layers'] if r['material_id'] == target['material_id']
                and r['unit'] == target['unit'] and r['warehouse_id'] == target['warehouse_id']
                and Decimal(r['remaining_quantity']) > 0]
    if not eligible:
        raise ValueError('No historically available receipt layers')
    opened = {e['receipt_line_id']: e['occurred_at'] for e in prefix if e['kind'] == 'RECEIPT'}
    eligible.sort(key=lambda r: (opened[r['receipt_line_id']], r['receipt_line_id']))
    if not isinstance(verified_unit_costs, dict):
        raise ValueError('Verified receipt cost map required')
    required_ids = {r['receipt_line_id'] for r in eligible}
    if set(verified_unit_costs) != required_ids:
        raise ValueError('Exact verified unit cost coverage required for available layers')
    layers = [CostLayer(r['receipt_line_id'], Decimal(r['remaining_quantity']),
                        verified_unit_costs[r['receipt_line_id']], currency) for r in eligible]
    output = calculate_issue_preview(method, target['quantity'], layers, currency)
    # A warehouse issue has an explicit physical receipt lot, whereas an
    # accounting FIFO layer sequence can differ. Never silently present a
    # costing preview as if it matched the stock posting's physical lineage.
    physical_receipt_line_id = target['receipt_line_id']
    fifo_allocated_ids = [row['receipt_line_id'] for row in output['fifo_allocations']]
    output['physical_receipt_line_id'] = physical_receipt_line_id
    output['physical_lot_in_eligible_layers'] = physical_receipt_line_id in required_ids
    output['costing_vs_physical_lot'] = (
        'DIFFERENT_LAYER_BASIS' if method == 'FIFO' and fifo_allocated_ids != [physical_receipt_line_id]
        else 'SAME_LAYER_BASIS' if method == 'FIFO'
        else 'NOT_COMPARABLE_WEIGHTED_AVERAGE'
    )
    # Actual posted receipt ancestry and the approved valuation methodology
    # must both be verified before a posted Finance valuation is established.
    output.update({
        'issue_event_id': issue_event_id,
        'as_of': ts.isoformat(),
        'source_event_count': len(prefix) + 1,
        'layer_balance_basis': 'CANONICAL_EVENTS_SUPPLIED_BY_CALLER',
        'financial_authority_verified': False,
        'warning': 'Indicative as-of historical cost only: physical lot lineage may differ from accounting FIFO, and full ledger snapshot, Finance cost approvals and journal posting must be checked independently.',
    })
    return output
