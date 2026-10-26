"""Read-only ceiling check: accepted stock cannot exceed its posted GRN line.

This is an integrity gate, not a stock availability or Finance valuation proof.
"""
from decimal import Decimal, InvalidOperation


def _positive(value, label):
    if isinstance(value, bool):
        raise ValueError(f'{label} must be positive and finite')
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f'{label} must be positive and finite') from None
    if not number.is_finite() or number <= 0:
        raise ValueError(f'{label} must be positive and finite')
    return number


def verify_receipt_acceptance_ceiling(*, receipt_line_id, received_quantity, accepted_lines):
    if type(receipt_line_id) is not int or receipt_line_id <= 0:
        raise ValueError('Invalid receipt line identifier')
    received = _positive(received_quantity, 'Received quantity')
    if not accepted_lines:
        raise ValueError('No posted acceptance lines for receipt')
    seen = set()
    accepted = Decimal('0')
    for line in accepted_lines:
        line_id = line.get('id')
        if type(line_id) is not int or line_id <= 0 or line_id in seen:
            raise ValueError('Duplicate or invalid acceptance line identifier')
        seen.add(line_id)
        if line.get('goods_receipt_line_id') != receipt_line_id:
            raise ValueError('Acceptance references unrelated receipt')
        accepted += _positive(line.get('quantity'), 'Acceptance quantity')
        if accepted > received:
            raise ValueError('Accepted quantity exceeds posted GRN line')
    return {'status': 'ACCEPTANCE_WITHIN_GRN_QUANTITY', 'receipt_line_id': receipt_line_id,
            'received_quantity': str(received), 'accepted_quantity': str(accepted),
            'remaining_unaccepted_quantity': str(received - accepted),
            'inventory_balance_verified': False, 'movement_valuation_verified': False}
