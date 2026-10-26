"""Finance landed-cost allocation *preview*, with no database or ledger writes.

Inputs are asserted Finance-approved metadata supplied by a caller. This module
cannot establish that those assertions match authoritative Finance records.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from .inventory_valuation_engine import _positive


@dataclass(frozen=True)
class ReceiptCostBasis:
    receipt_line_id: int
    organization_id: int
    project_id: int
    material_id: int
    quantity: Decimal
    purchase_unit_cost: Decimal
    currency: str


@dataclass(frozen=True)
class ApprovedLandedCharge:
    charge_id: str
    organization_id: int
    project_id: int
    currency: str
    amount: Decimal
    status: str
    source_document: str
    approved_by: int
    approved_at: datetime
    category: str  # e.g. freight, insurance, handling


def preview_landed_cost_allocation(*, receipts: list[ReceiptCostBasis],
                                   charges: list[ApprovedLandedCharge],
                                   organization_id: int, project_id: int,
                                   currency: str, as_of: datetime) -> dict:
    """Allocate approved charges pro rata by base purchase cost, at cent precision.

    The caller must verify Finance documents, approval segregation and actual
    receipt availability against source databases before using any result.
    """
    if as_of.tzinfo is None:
        raise ValueError('Valuation timestamp must be timezone-aware')
    if not currency or len(currency) != 3 or not currency.isalpha() or currency.upper() != currency:
        raise ValueError('Invalid valuation currency')
    if not receipts:
        raise ValueError('At least one receipt line is required')
    if not charges:
        raise ValueError('Approved landed-charge evidence is required')
    bases = []
    seen_lines = set()
    for r in receipts:
        if r.receipt_line_id <= 0 or r.receipt_line_id in seen_lines:
            raise ValueError('Duplicate or invalid receipt line')
        seen_lines.add(r.receipt_line_id)
        if (r.organization_id, r.project_id, r.currency) != (organization_id, project_id, currency):
            raise ValueError('Receipt project, organization or currency mismatch')
        if r.material_id <= 0:
            raise ValueError('Invalid material reference')
        q = _positive(r.quantity, 'Receipt quantity')
        cost = _positive(r.purchase_unit_cost, 'Purchase unit cost')
        bases.append((r.receipt_line_id, q, q * cost))
    total_base = sum((b for _, _, b in bases), Decimal(0))
    total_charges = Decimal(0)
    seen_charges = set()
    for c in charges:
        if not c.charge_id.strip() or c.charge_id in seen_charges:
            raise ValueError('Duplicate or missing landed-charge reference')
        seen_charges.add(c.charge_id)
        if (c.organization_id, c.project_id, c.currency) != (organization_id, project_id, currency):
            raise ValueError('Landed charge scope or currency mismatch')
        if c.status != 'APPROVED' or c.approved_by <= 0 or not c.source_document.strip() or not c.category.strip():
            raise ValueError('Landed charge lacks approval or document evidence')
        if c.approved_at.tzinfo is None or c.approved_at > as_of:
            raise ValueError('Landed charge approval is invalid or future dated')
        amount = _positive(c.amount, 'Landed charge amount')
        if amount != amount.quantize(Decimal('.01')):
            raise ValueError('Landed charge must be denominated in currency cents')
        total_charges += amount
    # Largest-remainder allocation ensures total allocated cents = charge sum,
    # with deterministic ties by receipt line ID.
    cents = int(total_charges * 100)
    portions = []
    for line_id, qty, base in bases:
        exact = Decimal(cents) * base / total_base
        whole = int(exact.to_integral_value(rounding=ROUND_DOWN))
        portions.append((line_id, qty, base, whole, exact - whole))
    unassigned = cents - sum(x[3] for x in portions)
    winners = {x[0] for x in sorted(portions, key=lambda x: (-x[4], x[0]))[:unassigned]}
    rows = []
    for line_id, qty, base, whole, _ in sorted(portions, key=lambda x: x[0]):
        allocated = Decimal(whole + (1 if line_id in winners else 0)) / 100
        rows.append({'receipt_line_id': line_id, 'purchase_cost': str(base),
                     'allocated_landed_charge': str(allocated.quantize(Decimal('.01'))),
                     'preview_total_receipt_cost': str(base + allocated),
                     'preview_unit_cost': str((base + allocated) / qty)})
    return {'status': 'UNPOSTED_FINANCE_PREVIEW', 'currency': currency,
            'total_landed_charges': str(total_charges), 'receipt_lines': rows,
            'finance_source_verified': False, 'journal_posting_verified': False,
            'warning': 'Source approvals, cost documents, receipt eligibility and journals require authoritative database verification.'}
