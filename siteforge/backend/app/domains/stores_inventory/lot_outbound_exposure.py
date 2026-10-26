"""Read-only outbound exposure for receipt lots; does not infer lot consumption."""
from collections import defaultdict
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.supply_chain.models import GoodsReceipt, GoodsReceiptLine, StockPosting, StockPostingLine
from .models import StoresReceiptLot, StoresInspectionCase, StoresLotQAAttribution, StoresPostingLotAllocation
from .router import receipt_access

router = APIRouter(prefix="/api/projects/{pid}/stores", tags=["Stores & Inventory"])


def decimal(value):
    return Decimal(str(value or 0))


def exposure_flags(attributed, case_version, current_case_version, accepted, mapped_accept, outbound):
    """Pure conservative eligibility diagnostic; never authorizes issue."""
    flags = []
    if not attributed:
        flags.append("LOT_QA_ATTRIBUTION_MISSING")
    if attributed and any(version != current_case_version for version in case_version):
        flags.append("LOT_QA_DECISION_STALE")
    if decimal(accepted) != decimal(mapped_accept):
        flags.append("QA_ACCEPTED_VS_RECEIPT_MAPPING_MISMATCH")
    if decimal(outbound) > 0:
        flags.append("UNATTRIBUTED_OUTBOUND_MOVEMENTS")
    return flags


@router.get("/lot-outbound-exposure")
def lot_outbound_exposure(pid: int, grn_id: int,
                          u: User = Depends(authenticated), db: Session = Depends(get_db)):
    receipt_access(db, u, pid)
    grn = db.query(GoodsReceipt).filter_by(id=grn_id, project_id=pid,
                                          organization_id=u.organization_id).first()
    if not grn:
        raise HTTPException(404, "Goods receipt not found")
    lines = db.query(GoodsReceiptLine).filter_by(goods_receipt_id=grn_id).all()
    line_ids = [line.id for line in lines]
    lots = (db.query(StoresReceiptLot).filter(
        StoresReceiptLot.project_id == pid,
        StoresReceiptLot.organization_id == u.organization_id,
        StoresReceiptLot.goods_receipt_line_id.in_(line_ids)).all()) if line_ids else []
    cases = (db.query(StoresInspectionCase).filter(
        StoresInspectionCase.project_id == pid,
        StoresInspectionCase.organization_id == u.organization_id,
        StoresInspectionCase.goods_receipt_line_id.in_(line_ids)).all()) if line_ids else []
    cases_by_line = {c.goods_receipt_line_id: c for c in cases}
    lot_ids = [lot.id for lot in lots]
    attributions = (db.query(StoresLotQAAttribution).filter(
        StoresLotQAAttribution.project_id == pid,
        StoresLotQAAttribution.organization_id == u.organization_id,
        StoresLotQAAttribution.receipt_lot_id.in_(lot_ids)).all()) if lot_ids else []
    allocated = (db.query(StoresPostingLotAllocation).filter(
        StoresPostingLotAllocation.project_id == pid,
        StoresPostingLotAllocation.organization_id == u.organization_id,
        StoresPostingLotAllocation.receipt_lot_id.in_(lot_ids)).all()) if lot_ids else []
    qa_by_lot = defaultdict(list)
    mapped_by_lot = defaultdict(lambda: Decimal(0))
    for row in attributions:
        qa_by_lot[row.receipt_lot_id].append(row)
    for row in allocated:
        mapped_by_lot[row.receipt_lot_id] += decimal(row.quantity)
    # Existing issue/return lines have no trustworthy provenance back to a receipt lot.
    # Report aggregate movement exposure by (warehouse, item, UOM), not lot depletion.
    stock = (db.query(StockPostingLine, StockPosting)
        .join(StockPosting, StockPosting.id == StockPostingLine.posting_id)
        .filter(StockPosting.organization_id == u.organization_id,
                StockPosting.project_id == pid,
                StockPosting.warehouse_id == grn.warehouse_id,
                StockPosting.status == "Posted",
                StockPosting.kind.in_(["Issue", "Return"])).all())
    movements = defaultdict(lambda: {"issued": Decimal(0), "returned": Decimal(0), "posting_ids": set()})
    for line, posting in stock:
        key = (line.item_id, line.unit)
        field = "issued" if posting.kind == "Issue" else "returned"
        movements[key][field] += decimal(line.quantity)
        movements[key]["posting_ids"].add(posting.id)
    result = []
    for lot in lots:
        case = cases_by_line.get(lot.goods_receipt_line_id)
        grn_line = next((line for line in lines if line.id == lot.goods_receipt_line_id), None)
        accepted_rows = [row for row in qa_by_lot[lot.id] if row.disposition == "Accepted"]
        accepted = sum((decimal(row.quantity) for row in accepted_rows), Decimal(0))
        qa_versions = [row.case_version_at_entry for row in qa_by_lot[lot.id]]
        # The GRN line does not expose a stock item ID directly; its purchase-order line does.
        # Locate item/UOM only through matching accepted legacy posting lines.
        sources = (db.query(StockPostingLine, StockPosting)
            .join(StockPosting, StockPosting.id == StockPostingLine.posting_id)
            .filter(StockPostingLine.goods_receipt_line_id == lot.goods_receipt_line_id,
                    StockPosting.organization_id == u.organization_id,
                    StockPosting.project_id == pid,
                    StockPosting.status == "Posted", StockPosting.kind == "Accept").all())
        keys = sorted({(line.item_id, line.unit) for line, _ in sources})
        exposure = []
        for key in keys:
            summary = movements[key]
            exposure.append({"item_id": key[0], "unit": key[1],
                             "warehouse_issued_total": str(summary["issued"]),
                             "warehouse_returned_total": str(summary["returned"]),
                             "posting_ids": sorted(summary["posting_ids"])})
        total_outbound = sum((movements[key]["issued"] for key in keys), Decimal(0))
        flags = exposure_flags(bool(qa_by_lot[lot.id]), qa_versions,
            case.version if case else None, accepted, mapped_by_lot[lot.id], total_outbound)
        if not case:
            flags.append("QA_CASE_MISSING")
        if not keys:
            flags.append("ACCEPT_POSTING_ITEM_NOT_RESOLVED")
        result.append({"lot_id": lot.id, "lot_code": lot.lot_code,
            "goods_receipt_line_id": lot.goods_receipt_line_id,
            "registered_quantity": str(lot.quantity),
            "qa_accepted_attributed": str(accepted),
            "receipt_accept_posting_mapped": str(mapped_by_lot[lot.id]),
            "outbound_exposure_same_warehouse_item": exposure,
            "blocking_flags": flags,
            "physical_on_hand": None, "available_to_issue": None,
            "lot_issue_enabled": False})
    return {"goods_receipt_id": grn_id, "project_id": pid, "lots": result,
      "ledger_owner": "Existing Procurement stock_postings",
      "warning": "Outbound is warehouse/item exposure, NOT proven movement of these lots. No inferred consumption, stock balance or lot release."}
