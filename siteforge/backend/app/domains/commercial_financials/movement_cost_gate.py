"""Fail-closed Finance issue-cost preview gate; never a journal or stock posting.

Only pass records authenticated and independently fetched by Finance from authoritative
posting/costing sources. PO list prices and landed-cost previews are not eligible.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from .inventory_valuation_engine import CostLayer, calculate_issue_preview, _positive


@dataclass(frozen=True)
class VerifiedReceiptLayer:
    receipt_line_id: int
    organization_id: int
    project_id: int
    material_id: int
    unit: str
    currency: str
    available_quantity: Decimal
    verified_unit_cost: Decimal
    receipt_posted_at: datetime
    finance_verified_at: datetime
    finance_evidence_id: str
    finance_status: str


def preview_issue_from_verified_layers(*, organization_id: int, project_id: int,
        material_id: int, unit: str, currency: str, method: str,
        issue_quantity, issue_at: datetime, layers: list[VerifiedReceiptLayer]):
    """Preview only. Caller must load remaining quantities under an authoritative snapshot.

    Does not implement moving-average ledger chronology or certify accounting evidence.
    """
    if any(not isinstance(v, int) or v <= 0 for v in (organization_id, project_id, material_id)):
        raise ValueError('Valid organization/project/material identifiers required')
    if not unit or not unit.strip():
        raise ValueError('Material unit required')
    if issue_at.tzinfo is None:
        raise ValueError('Timezone-aware issue timestamp required')
    if not layers:
        raise ValueError('No verified receipt cost layers')
    seen_receipts = set()
    seen_evidence = set()
    cost_layers = []
    for layer in layers:
        if (layer.organization_id, layer.project_id, layer.material_id) != (organization_id, project_id, material_id):
            raise ValueError('Receipt layer outside current organization/project/material')
        if layer.unit != unit or layer.currency != currency:
            raise ValueError('Receipt layer unit/currency mismatch')
        if layer.finance_status != 'VERIFIED' or not layer.finance_evidence_id.strip():
            raise ValueError('Authoritative Finance receipt-cost verification required')
        if layer.receipt_line_id in seen_receipts or layer.finance_evidence_id in seen_evidence:
            raise ValueError('Duplicate receipt line or Finance evidence')
        seen_receipts.add(layer.receipt_line_id)
        seen_evidence.add(layer.finance_evidence_id)
        if (layer.receipt_posted_at.tzinfo is None or layer.finance_verified_at.tzinfo is None
                or layer.receipt_posted_at > issue_at or layer.finance_verified_at > issue_at
                or layer.finance_verified_at < layer.receipt_posted_at):
            raise ValueError('Invalid receipt and Finance verification chronology')
        cost_layers.append(CostLayer(layer.receipt_line_id,
            _positive(layer.available_quantity, 'Available quantity'),
            _positive(layer.verified_unit_cost, 'Verified unit cost'), currency))
    if method == 'FIFO' and [x.receipt_posted_at for x in layers] != sorted(x.receipt_posted_at for x in layers):
        raise ValueError('FIFO layers must be sorted by receipt posting timestamp')
    result = calculate_issue_preview(method, issue_quantity, cost_layers, currency)
    result['finance_evidence_ids'] = [x.finance_evidence_id for x in layers]
    result['remaining_stock_verified'] = False
    result['warning'] = ('Unposted calculation using caller-supplied Finance-verified cost evidence; '
        'remaining stock, historical movement chronology, costing policy and journals still require database verification.')
    return result
