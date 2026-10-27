"""Read-only receipt-line/lot/QA/legacy-posting reconciliation.

No inferred allocation of QA decisions to receipt lots. This report is
intentionally NOT an eligible-to-issue inventory balance.
"""
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.supply_chain.models import GoodsReceipt, GoodsReceiptLine, StockPosting, StockPostingLine
from .models import StoresReceiptLot, StoresInspectionCase
from .router import receipt_access

router = APIRouter(prefix="/api/projects/{pid}/stores", tags=["Stores & Inventory"])


def decimal(value):
    return Decimal(str(value or 0))


def reconcile_line(received, lots, inspection, posting_rows, quality_approved=None):
    """Pure calculator; unit-specific quantities, never merges differing units."""
    lot_total = sum((decimal(lot.quantity) for lot in lots), Decimal(0))
    accepted = decimal(inspection.accepted_qty) if inspection else Decimal(0)
    rejected = decimal(inspection.rejected_qty) if inspection else Decimal(0)
    quarantined = decimal(inspection.quarantined_qty) if inspection else Decimal(0)
    pending = decimal(inspection.pending_qty) if inspection else decimal(received)
    posted_by_unit = defaultdict(Decimal)
    for posting in posting_rows:
        # Do not assume legacy posting kinds correspond to QA releases.
        posted_by_unit[posting.unit] += decimal(posting.quantity)
    flags = []
    if lot_total != decimal(received):
        flags.append("LOT_REGISTRATION_INCOMPLETE" if lot_total < decimal(received) else "LOT_REGISTRATION_OVERAGE")
    if inspection is None:
        flags.append("QA_CASE_MISSING")
    elif pending + accepted + rejected + quarantined != decimal(received):
        flags.append("QA_QUANTITIES_NOT_RECONCILED")
    # Quality-owned approval is evidence, not an instruction to release stock.
    # None means that the authoritative Quality projection was not supplied.
    quality_qty = decimal(quality_approved) if quality_approved is not None else None
    if quality_qty is not None:
        if quality_qty < 0 or quality_qty > decimal(received):
            flags.append("QUALITY_APPROVAL_OUT_OF_RANGE")
        if quality_qty != accepted:
            flags.append("QUALITY_STORES_ACCEPTANCE_MISMATCH")
    if inspection is not None and inspection.status == "Quality Revoked":
        flags.append("QUALITY_REVOKED")
    if pending or rejected or quarantined:
        flags.append("NON_ACCEPTED_MATERIAL_PRESENT")
    if posting_rows:
        flags.append("LEGACY_POSTINGS_NOT_LOT_ALLOCATED")
    if len(lots) > 1 and accepted:
        flags.append("ACCEPTANCE_NOT_ATTRIBUTED_TO_LOTS")
    return {
        "received_quantity": str(decimal(received)),
        "registered_lot_quantity": str(lot_total),
        "quality_module_approved_quantity": str(quality_qty) if quality_qty is not None else None,
        "quality_stores_quantity_difference": str(quality_qty - accepted) if quality_qty is not None else None,
        "unregistered_quantity": str(decimal(received) - lot_total),
        "qa": {"pending": str(pending), "accepted": str(accepted),
               "rejected": str(rejected), "quarantined": str(quarantined)},
        "legacy_posted_quantity_by_unit": {unit: str(qty) for unit, qty in sorted(posted_by_unit.items())},
        "flags": flags,
        "lot_issue_enabled": False,
    }


@router.get("/receipt-lot-reconciliation")
def receipt_lot_reconciliation(pid: int, grn_id: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    receipt_access(db, u, pid)
    receipt = db.query(GoodsReceipt).filter_by(id=grn_id, project_id=pid, organization_id=u.organization_id).first()
    if not receipt:
        raise HTTPException(404, "Receipt not found")
    lines = db.query(GoodsReceiptLine).filter_by(goods_receipt_id=receipt.id).all()
    line_ids = [line.id for line in lines]
    lots = db.query(StoresReceiptLot).filter(StoresReceiptLot.goods_receipt_line_id.in_(line_ids),
        StoresReceiptLot.project_id == pid, StoresReceiptLot.organization_id == u.organization_id).all() if line_ids else []
    cases = db.query(StoresInspectionCase).filter(StoresInspectionCase.goods_receipt_line_id.in_(line_ids),
        StoresInspectionCase.project_id == pid, StoresInspectionCase.organization_id == u.organization_id).all() if line_ids else []
    postings = (db.query(StockPostingLine, StockPosting)
        .join(StockPosting, StockPosting.id == StockPostingLine.posting_id)
        .filter(StockPostingLine.goods_receipt_line_id.in_(line_ids),
                StockPosting.project_id == pid, StockPosting.organization_id == u.organization_id).all()) if line_ids else []
    lots_by_line = defaultdict(list)
    cases_by_line = {case.goods_receipt_line_id: case for case in cases}
    postings_by_line = defaultdict(list)
    for lot in lots:
        lots_by_line[lot.goods_receipt_line_id].append(lot)
    for posting_line, posting in postings:
        postings_by_line[posting_line.goods_receipt_line_id].append(posting_line)
    # Compare the two existing approval projections without mutating either.
    # The Quality service is the owner of approved material dispositions.
    from app.domains.quality.material import quality_accepted

    result = []
    for line in lines:
        matching_lots = lots_by_line[line.id]
        result.append({
            "goods_receipt_line_id": line.id,
            "quantity_summary": reconcile_line(line.quantity, matching_lots, cases_by_line.get(line.id), postings_by_line[line.id], quality_approved=quality_accepted(db, line.id)),
            "lots": [{"lot_id": lot.id, "lot_code": lot.lot_code, "quantity": str(lot.quantity),
                      "owner_company_id": lot.owner_company_id, "custodian_company_id": lot.custodian_company_id,
                      "warehouse_id": lot.warehouse_id, "location_id": lot.location_id,
                      "batch_number": lot.batch_number, "heat_number": lot.heat_number,
                      "serial_number": lot.serial_number, "expiry_date": str(lot.expiry_date) if lot.expiry_date else None}
                     for lot in matching_lots],
            "legacy_posting_ids": sorted({p.posting_id for p in postings_by_line[line.id]}),
        })
    return {"receipt_id": receipt.id, "project_id": pid, "lines": result,
            "posting_owner": "existing Procurement stock ledger",
            "warning": "Audit/reconciliation only: receipt-line QA approval is not lot-level release. No lot can be issued based on this response."}
