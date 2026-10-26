"""Finance-owned receipt cost eligibility gate, not an accounting posting.

Supply entries only from a verified Finance source; a PO rate or supplier invoice
alone is not proof of landed receipt cost. No database writes are performed.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from .inventory_valuation_engine import CostLayer, _positive, calculate_issue_preview


@dataclass(frozen=True)
class ReceiptCostEvidence:
    receipt_line_id: int
    project_id: int
    organization_id: int
    material_id: int
    unit: str
    quantity_available: Decimal
    landed_unit_cost: Decimal
    currency: str
    source_document_id: str
    approved_by: int
    approved_at: datetime
    receipt_posted_at: datetime
    status: str


def eligible_receipt_layers(*, evidence: list[ReceiptCostEvidence], project_id: int,
                            organization_id: int, material_id: int, unit: str,
                            currency: str, issue_at: datetime) -> list[CostLayer]:
    """Fail closed on incomplete/mixed or future-dated Finance cost evidence.

    The caller must independently prove source-document authenticity, available
    quantities and reservation/chronology against authoritative DB records.
    """
    if issue_at.tzinfo is None:
        raise ValueError('Issue timestamp must include timezone')
    if not evidence:
        raise ValueError('No Finance-approved landed receipt cost evidence')
    result = []
    seen = set()
    for row in evidence:
        if row.receipt_line_id in seen or row.receipt_line_id <= 0:
            raise ValueError('Duplicate or invalid receipt line')
        seen.add(row.receipt_line_id)
        if (row.project_id, row.organization_id, row.material_id, row.unit, row.currency) != (project_id, organization_id, material_id, unit, currency):
            raise ValueError('Receipt evidence scope, material, unit or currency mismatch')
        if row.status != 'APPROVED' or row.approved_by <= 0 or not row.source_document_id.strip():
            raise ValueError('Receipt cost lacks independent Finance approval or source reference')
        if row.approved_at.tzinfo is None or row.receipt_posted_at.tzinfo is None:
            raise ValueError('Evidence timestamps must include timezone')
        if row.receipt_posted_at > issue_at or row.approved_at > issue_at or row.approved_at < row.receipt_posted_at:
            raise ValueError('Receipt cost is not approved and posted by issue time')
        result.append((row.receipt_posted_at.astimezone(timezone.utc), row.receipt_line_id,
                       CostLayer(row.receipt_line_id, _positive(row.quantity_available, 'Available quantity'),
                                 _positive(row.landed_unit_cost, 'Landed unit cost'), currency)))
    result.sort(key=lambda x: (x[0], x[1]))
    return [layer for _, _, layer in result]


def preview_from_approved_evidence(*, method: str, issue_quantity, evidence: list[ReceiptCostEvidence],
                                   project_id: int, organization_id: int, material_id: int,
                                   unit: str, currency: str, issue_at: datetime):
    layers = eligible_receipt_layers(evidence=evidence, project_id=project_id,
                                     organization_id=organization_id, material_id=material_id,
                                     unit=unit, currency=currency, issue_at=issue_at)
    out = calculate_issue_preview(method, issue_quantity, layers, currency)
    out['receipt_evidence_status'] = 'SUPPLIED_APPROVED_METADATA_NOT_DB_VERIFIED'
    out['source_receipt_line_ids'] = [r.receipt_line_id for r in layers]
    out['warning'] = ('Unposted preview only. Source-document authenticity, independent approval, '
                      'receipt availability, approved costing policy and journals still require live Finance verification.')
    return out
