"""Read-only provenance reconciliation; this endpoint never authorizes stock issue."""
from collections import defaultdict
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.supply_chain.models import StockPosting, StockPostingLine
from .models import (StoresReceiptLot, StoresPostingLotAllocation,
                     StoresOutboundLotAllocation, StoresLotQAAttribution, StoresInspectionCase)
from .router import receipt_access

router = APIRouter(prefix="/api/projects/{pid}/stores", tags=["Stores & Inventory"])

def d(value):
    return Decimal(str(value or 0))

def assess_lot(*, received, accepted_posting, issued, returned, qa_accepted, qa_rejected,
               qa_quarantined, qa_pending, attribution_current, expired, unmapped_outbound):
    """Do not publish available/on-hand values from incomplete historical allocations."""
    received, acceptance, issue, ret = map(d, (received, accepted_posting, issued, returned))
    accepted, rejected, quarantined, pending = map(d, (qa_accepted, qa_rejected, qa_quarantined, qa_pending))
    flags = []
    if acceptance != received: flags.append("RECEIPT_POSTING_NOT_FULLY_ATTRIBUTED")
    if accepted + rejected + quarantined + pending != received: flags.append("QA_ATTRIBUTION_INCOMPLETE")
    if not attribution_current: flags.append("QA_VERSION_STALE_OR_MISSING")
    if accepted < acceptance: flags.append("ACCEPTED_QTY_BELOW_POSTED_PROVENANCE")
    if issue > acceptance: flags.append("OUTBOUND_EXCEEDS_RECEIPT_PROVENANCE")
    if ret > issue: flags.append("RETURNS_EXCEED_ISSUES")
    if expired: flags.append("LOT_EXPIRED")
    if unmapped_outbound: flags.append("LEGACY_OUTBOUND_NOT_FULLY_ATTRIBUTED")
    return {"registered_quantity": str(received), "mapped_receipt_quantity": str(acceptance),
            "qa_accepted_quantity": str(accepted), "attributed_issued_quantity": str(issue),
            "attributed_returned_quantity": str(ret), "reconciliation_flags": flags,
            "provenance_reconciled": not flags, "physical_on_hand": None,
            "available_to_issue": None, "issue_authorized": False}

@router.get("/lot-movement-review")
def lot_movement_review(pid: int, lot_id: int, u: User = Depends(authenticated),
                        db: Session = Depends(get_db)):
    receipt_access(db, u, pid)
    lot = db.query(StoresReceiptLot).filter_by(id=lot_id, project_id=pid,
        organization_id=u.organization_id).first()
    if not lot:
        raise HTTPException(404, "Receipt lot not found")
    case = db.query(StoresInspectionCase).filter_by(goods_receipt_line_id=lot.goods_receipt_line_id,
        project_id=pid, organization_id=u.organization_id).first()
    mapped = (db.query(StoresPostingLotAllocation, StockPostingLine, StockPosting)
        .join(StockPostingLine, StockPostingLine.id == StoresPostingLotAllocation.stock_posting_line_id)
        .join(StockPosting, StockPosting.id == StockPostingLine.posting_id)
        .filter(StoresPostingLotAllocation.receipt_lot_id == lot_id,
            StoresPostingLotAllocation.project_id == pid,
            StoresPostingLotAllocation.organization_id == u.organization_id,
            StockPosting.status == "Posted", StockPosting.kind == "Accept").all())
    outbound = (db.query(StoresOutboundLotAllocation, StockPostingLine, StockPosting)
        .join(StockPostingLine, StockPostingLine.id == StoresOutboundLotAllocation.stock_posting_line_id)
        .join(StockPosting, StockPosting.id == StockPostingLine.posting_id)
        .filter(StoresOutboundLotAllocation.receipt_lot_id == lot_id,
            StoresOutboundLotAllocation.project_id == pid,
            StoresOutboundLotAllocation.organization_id == u.organization_id,
            StockPosting.status == "Posted", StockPosting.kind.in_(["Issue", "Return"])).all())
    qa = db.query(StoresLotQAAttribution).filter_by(receipt_lot_id=lot_id,
        project_id=pid, organization_id=u.organization_id).all()
    q = defaultdict(Decimal)
    for a in qa:
        q[a.disposition.lower()] += d(a.quantity)
    receipt_qty = sum((d(a.quantity) for a, _, _ in mapped), Decimal(0))
    issue_qty = sum((d(a.quantity) for a, _, p in outbound if p.kind == "Issue"), Decimal(0))
    return_qty = sum((d(a.quantity) for a, _, p in outbound if p.kind == "Return"), Decimal(0))
    # A warehouse/item-level posting may have other lots, so we cannot confirm full
    # historical outbound allocation here; report this explicitly and never release stock.
    assessment = assess_lot(received=lot.quantity, accepted_posting=receipt_qty,
        issued=issue_qty, returned=return_qty, qa_accepted=q['accepted'],
        qa_rejected=q['rejected'], qa_quarantined=q['quarantined'],
        qa_pending=d(lot.quantity)-sum(q.values(), Decimal(0)),
        attribution_current=bool(case and qa and all(a.case_version_at_entry == case.version for a in qa)),
        expired=bool(lot.expiry_date and lot.expiry_date < date.today()),
        unmapped_outbound=True)
    return {"project_id": pid, "receipt_lot_id": lot_id, "lot_code": lot.lot_code,
        "owner_company_id": lot.owner_company_id, "custodian_company_id": lot.custodian_company_id,
        "warehouse_id": lot.warehouse_id, "location_id": lot.location_id,
        "batch_number": lot.batch_number, "heat_number": lot.heat_number,
        "serial_number": lot.serial_number, **assessment,
        "source_of_truth": "Legacy Procurement posting ledger",
        "warning": "Historical provenance review only; missing movement allocations and stock restrictions prevent authoritative lot availability."}
