"""Read-only return cost reversals tied to the *original issue* cost evidence.

This is not an inventory posting, costing certification or GL journal. Caller must
independently establish the issue, return chronology, quantity and Finance source.
Never revalue a return at the latest receipt cost or current weighted-average.
"""
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

_CENT = Decimal('0.01')


def _quantity(value, label):
    if isinstance(value, bool) or isinstance(value, (dict, list)):
        raise ValueError(f'{label} must be a positive finite quantity')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f'{label} must be a positive finite quantity') from None
    if not result.is_finite() or result <= 0:
        raise ValueError(f'{label} must be a positive finite quantity')
    return result


def _amount(value):
    amount = _quantity(value, 'Original issue cost')
    if amount != amount.quantize(_CENT):
        raise ValueError('Original issue cost must be expressed in whole currency cents')
    return amount


def preview_issue_return_reversals(*, issue_id: int, issued_quantity, original_issue_amount,
                                   currency: str, returns: list[dict]) -> dict:
    """Preview cumulative return reversal amounts, never exceeding original issue cost.

    Input returns must be authoritative ordered events from the same original issue:
    [{'return_id': positive int, 'issue_id': issue_id, 'quantity': positive decimal}, ...].
    Intermediate amounts use cumulative rounding; the final full-quantity return
    reverses any remaining cents. No positive stock/ledger mutations occur here.
    """
    if type(issue_id) is not int or issue_id <= 0:
        raise ValueError('Original issue ID must be a positive integer')
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha() or not currency.isupper():
        raise ValueError('Invalid original issue currency')
    issued = _quantity(issued_quantity, 'Original issued quantity')
    total = _amount(original_issue_amount)
    if not isinstance(returns, list) or not returns:
        raise ValueError('Ordered return evidence is required')
    returned = Decimal(0)
    previously_reversed = Decimal(0)
    seen = set()
    rows = []
    for event in returns:
        if not isinstance(event, dict):
            raise ValueError('Invalid return evidence')
        rid = event.get('return_id')
        if type(rid) is not int or rid <= 0 or rid in seen:
            raise ValueError('Return IDs must be unique positive integers')
        seen.add(rid)
        if type(event.get('issue_id')) is not int or event['issue_id'] != issue_id:
            raise ValueError('Return original issue does not match')
        qty = _quantity(event.get('quantity'), 'Returned quantity')
        returned += qty
        if returned > issued:
            raise ValueError('Returns exceed original issued quantity')
        cumulative_cost = (total * returned / issued).quantize(_CENT, rounding=ROUND_HALF_UP)
        reversal = cumulative_cost - previously_reversed
        if reversal < 0:
            raise ValueError('Invalid return reversal chronology')
        rows.append({'return_id': rid, 'issue_id': issue_id, 'return_quantity': str(qty),
                     'unposted_reversal_amount': str(reversal)})
        previously_reversed = cumulative_cost
    return {'status': 'UNPOSTED_RETURN_REVERSAL_PREVIEW', 'issue_id': issue_id,
            'currency': currency, 'returns': rows,
            'total_unposted_reversal_amount': str(previously_reversed),
            'unreversed_issue_amount': str(total - previously_reversed),
            'remaining_issued_quantity': str(issued - returned),
            'movement_valuation_verified': False, 'journal_posting_verified': False,
            'warning': 'Caller-supplied original-issue evidence and return chronology have not been independently certified. No stock or GL posting occurs.'}
