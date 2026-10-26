"""Read-only receipt-lot creation ceiling backed by posted acceptance quantities.

The check does not assert free stock, cost basis or certified valuation.
"""
from decimal import Decimal, InvalidOperation


def positive(value, name):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a positive finite quantity')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f'{name} must be a positive finite quantity') from None
    if not result.is_finite() or result <= 0:
        raise ValueError(f'{name} must be a positive finite quantity')
    return result


def verify_lot_acceptance_coverage(*, receipt_line_id, lots, accepted_quantity):
    if type(receipt_line_id) is not int or receipt_line_id <= 0:
        raise ValueError('Invalid receipt line ID')
    accepted = positive(accepted_quantity, 'Accepted quantity')
    if not lots:
        raise ValueError('No receipt lots linked to posted acceptance')
    total = Decimal('0')
    seen = set()
    for lot in lots:
        identifier = lot.get('id')
        if type(identifier) is not int or identifier <= 0 or identifier in seen:
            raise ValueError('Invalid or repeated receipt lot ID')
        seen.add(identifier)
        if lot.get('goods_receipt_line_id') != receipt_line_id:
            raise ValueError('Receipt lot points to another GRN line')
        total += positive(lot.get('quantity'), 'Receipt lot quantity')
        if total > accepted:
            raise ValueError('Receipt lot intake exceeds posted accepted quantity')
    return {'status': 'LOT_INTAKE_WITHIN_ACCEPTANCE',
            'receipt_line_id': receipt_line_id, 'accepted_quantity': str(accepted),
            'lot_intake_quantity': str(total), 'unassigned_accepted_quantity': str(accepted - total),
            'free_stock_verified': False, 'movement_valuation_verified': False}
