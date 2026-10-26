"""Pure Finance calculation kernel. Input layers must be independently verified.

This module NEVER reads invoices as receipt valuation, writes inventory, or posts GL.
Callers must establish authoritative costs, chronology, currency and approved policy.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


@dataclass(frozen=True)
class CostLayer:
    receipt_line_id: int
    quantity: Decimal
    unit_cost: Decimal
    currency: str


def _positive(value, label):
    try:
        v = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f'{label} must be a finite positive decimal') from None
    if not v.is_finite() or v <= 0:
        raise ValueError(f'{label} must be a finite positive decimal')
    return v


def calculate_issue_preview(method: str, issue_quantity, layers: list[CostLayer], currency: str):
    """Compute an *unposted* issue-cost preview using ordered verified layers.

    FIFO layers must be oldest-first; caller is responsible for that guarantee.
    WAC represents a weighted-average over the supplied eligible layers only.
    This is not a general moving-average ledger engine.
    """
    if method not in ('FIFO', 'WEIGHTED_AVERAGE'):
        raise ValueError('Unsupported costing policy')
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha() or currency != currency.upper():
        raise ValueError('Invalid policy currency')
    qty = _positive(issue_quantity, 'Issue quantity')
    if not layers:
        raise ValueError('Verified receipt valuation layers are required')
    seen = set()
    cleaned = []
    for layer in layers:
        if not isinstance(layer.receipt_line_id, int) or layer.receipt_line_id <= 0 or layer.receipt_line_id in seen:
            raise ValueError('Receipt line IDs must be unique positive integers')
        seen.add(layer.receipt_line_id)
        if layer.currency != currency:
            raise ValueError('Currency mismatch between policy and receipt layer')
        cleaned.append((layer.receipt_line_id, _positive(layer.quantity, 'Layer quantity'),
                        _positive(layer.unit_cost, 'Unit cost')))
    available = sum((q for _, q, _ in cleaned), Decimal(0))
    if qty > available:
        raise ValueError('Insufficient valued receipt-layer quantity')
    if method == 'FIFO':
        remaining = qty
        allocations = []
        amount = Decimal(0)
        for rid, quantity, rate in cleaned:
            consumed = min(remaining, quantity)
            if consumed:
                amount += consumed * rate
                allocations.append({'receipt_line_id': rid, 'quantity': str(consumed)})
                remaining -= consumed
            if remaining == 0:
                break
    else:
        amount = qty * (sum((q * rate for _, q, rate in cleaned), Decimal(0)) / available)
        allocations = []  # WAC issues do not imply specific FIFO layer consumption.
    return {
        'status': 'PREVIEW_ONLY_UNVERIFIED',
        'method': method,
        'currency': currency,
        'issue_quantity': str(qty),
        'unposted_amount': str(amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        'fifo_allocations': allocations,
        'movement_valuation_verified': False,
        'journal_posting_verified': False,
        'warning': 'Calculation only; receipt costs, chronology, reservations, policy authority and journal evidence must be independently verified.',
    }
