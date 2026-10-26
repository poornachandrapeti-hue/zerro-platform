"""Conservative lot posting/QA reconciliation. Not authoritative inventory or issue permission."""
from collections import defaultdict
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.supply_chain.models import GoodsReceiptLine, GoodsReceipt, StockPostingLine, StockPosting
from .models import StoresReceiptLot, StoresPostingLotAllocation, StoresInspectionCase
from .router import receipt_access

router = APIRouter(prefix="/api/projects/{pid}/stores", tags=["Stores & Inventory"])

def dec(value):
    return Decimal(str(value or 0))

def review_lot(registered_qty, allocated_qty, accepted_qty, receipt_qty, lot_count, pending_qty,
               rejected_qty, quarantined_qty, posting_unallocated_qty, has_expired=False):
    """Never infer line-level acceptance for one of multiple lots."""
    registered, allocated, accepted, received = map(dec, (registered_qty, allocated_qty, accepted_qty, receipt_qty))
    flags = []
    if allocated > registered:
        flags.append("ALLOCATIONS_EXCEED_LOT")
    if allocated == 0:
        flags.append("NO_POSTING_PROVENANCE")
    if allocated < registered:
        flags.append("POSTING_PROVENANCE_INCOMPLETE")
    if dec(posting_unallocated_qty) != 0:
        flags.append("RECEIPT_POSTING_NOT_FULLY_ALLOCATED")
    if registered > received:
        flags.append("RECEIPT_QUANTITY_EXCEEDED")
    if not accepted or dec(pending_qty) or dec(rejected_qty) or dec(quarantined_qty):
        flags.append("QA_NOT_FULLY_ACCEPTED")
    if int(lot_count) != 1:
        flags.append("QA_NOT_ATTRIBUTED_TO_INDIVIDUAL_LOT")
    elif accepted != received:
        flags.append("QA_QUANTITY_MISMATCH")
    if has_expired:
        flags.append("EXPIRED")
    # This is only a diagnostic comparison. A real issue-eligible balance also requires
    # lot-specific outgoing movements, reservations, ownership and all stock restrictions.
    return {"registered_qty": str(registered), "mapped_receipt_accept_qty": str(allocated),
            "qa_accepted_at_receipt_line": str(accepted), "flags": flags,
            "ledger_migration_ready": not flags,
            "physical_on_hand": None, "available_to_issue": None,
            "lot_issue_enabled": False}

@router.get("/lot-balance-review")
def lot_balance_review(pid: int, grn_id: int, u: User = Depends(authenticated),
                       db: Session = Depends(get_db)):
    receipt_access(db, u, pid)
    grn = db.query(GoodsReceipt).filter_by(id=grn_id, organization_id=u.organization_id, project_id=pid).first()
    if grn is None:
        raise HTTPException(404, "Receipt not found")
    lines = db.query(GoodsReceiptLine).filter_by(goods_receipt_id=grn_id).all()
    line_ids = [x.id for x in lines]
    lots = db.query(StoresReceiptLot).filter(StoresReceiptLot.goods_receipt_line_id.in_(line_ids),
            StoresReceiptLot.project_id == pid, StoresReceiptLot.organization_id == u.organization_id).all() if line_ids else []
    cases = db.query(StoresInspectionCase).filter(StoresInspectionCase.goods_receipt_line_id.in_(line_ids),
            StoresInspectionCase.project_id == pid, StoresInspectionCase.organization_id == u.organization_id).all() if line_ids else []
    postings = (db.query(StockPostingLine, StockPosting).join(StockPosting, StockPosting.id == StockPostingLine.posting_id)
        .filter(StockPostingLine.goods_receipt_line_id.in_(line_ids), StockPosting.project_id == pid,
            StockPosting.organization_id == u.organization_id, StockPosting.status == "Posted",
            StockPosting.kind == "Accept").all()) if line_ids else []
    posting_ids = [p.id for p, _ in postings]
    allocs = db.query(StoresPostingLotAllocation).filter(
        StoresPostingLotAllocation.stock_posting_line_id.in_(posting_ids),
        StoresPostingLotAllocation.project_id == pid,
        StoresPostingLotAllocation.organization_id == u.organization_id).all() if posting_ids else []
    lot_by_line = defaultdict(list)
    case_by_line = {c.goods_receipt_line_id: c for c in cases}
    posting_by_line = defaultdict(list)
    alloc_by_posting = defaultdict(Decimal)
    alloc_by_lot = defaultdict(Decimal)
    for lot in lots:
        lot_by_line[lot.goods_receipt_line_id].append(lot)
    for p, _ in postings:
        posting_by_line[p.goods_receipt_line_id].append(p)
    for a in allocs:
        alloc_by_posting[a.stock_posting_line_id] += dec(a.quantity)
        alloc_by_lot[a.receipt_lot_id] += dec(a.quantity)
    result = []
    for line in lines:
        group = lot_by_line[line.id]
        case = case_by_line.get(line.id)
        unallocated = sum((dec(p.quantity) - alloc_by_posting[p.id] for p in posting_by_line[line.id]), Decimal(0))
        result.append({"goods_receipt_line_id": line.id,
          "unallocated_posted_receipt_qty": str(unallocated),
          "lots": [{"lot_id": lot.id, "lot_code": lot.lot_code,
                   "owner_company_id": lot.owner_company_id, "custodian_company_id": lot.custodian_company_id,
                   "warehouse_id": lot.warehouse_id, "location_id": lot.location_id,
                   "batch_number": lot.batch_number, "heat_number": lot.heat_number, "serial_number": lot.serial_number,
                   **review_lot(lot.quantity, alloc_by_lot[lot.id], case.accepted_qty if case else 0,
                       line.quantity, len(group), case.pending_qty if case else line.quantity,
                       case.rejected_qty if case else 0, case.quarantined_qty if case else 0,
                       unallocated, bool(lot.expiry_date and lot.expiry_date < __import__('datetime').date.today()))}
                  for lot in group]})
    return {"project_id": pid, "goods_receipt_id": grn_id, "lines": result,
            "source_of_truth": "legacy Procurement stock posting ledger",
            "warning": "Diagnostic only. QA decisions are on receipt lines and outgoing movements are not assigned to lots. Physical/available balances and issue authorization are intentionally unavailable."}
