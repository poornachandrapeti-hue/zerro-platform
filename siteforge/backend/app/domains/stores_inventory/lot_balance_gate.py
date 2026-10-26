"""Phase 3 reconciliation gate: intentionally read-only, never authorizes an issue.

Conservatively evaluates *all* posted movements for an item in one warehouse.
Balances remain owned by the Procurement ledger until a validated transactional
migration installs an atomic lot-qualified posting path.
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.supply_chain.models import StockPosting, StockPostingLine, StockBalance
from .models import (StoresReceiptLot, StoresPostingLotAllocation,
                     StoresOutboundLotAllocation, StoresLotQAAttribution, StoresInspectionCase)
from .router import receipt_access

router = APIRouter(prefix="/api/projects/{pid}/stores", tags=["Stores & Inventory"])


def dec(value):
    return Decimal(str(value if value is not None else 0))


def summarize_ledger(postings, receipt_allocations, outbound_allocations, lot_qa,
                     legacy_on_hand, legacy_reserved, *, current_lots, today=None):
    """Pure calculation; data input must include every posted line in the scope.

    postings tuples: (posting_line_id, kind, quantity)
    allocations tuples: (posting_line_id, lot_id, quantity)
    lot_qa mapping: lot_id -> (accepted, up_to_date, is_expired)
    Returns no releasable balance even when reconciliation matches.
    """
    today = today or date.today()
    errors = set()
    if not postings:
        errors.add("NO_POSTED_MOVEMENT_HISTORY")
    receipt_by_line = defaultdict(Decimal)
    outgoing_by_line = defaultdict(Decimal)
    per_lot = defaultdict(lambda: defaultdict(Decimal))
    for line_id, lot_id, quantity in receipt_allocations:
        qty = dec(quantity)
        receipt_by_line[line_id] += qty
        per_lot[lot_id]["Accept"] += qty
        if qty <= 0: errors.add("NONPOSITIVE_ALLOCATION")
    for line_id, lot_id, kind, quantity in outbound_allocations:
        qty = dec(quantity)
        outgoing_by_line[line_id] += qty
        per_lot[lot_id][kind] += qty
        if qty <= 0: errors.add("NONPOSITIVE_ALLOCATION")
    legacy_net = Decimal(0)
    for line_id, kind, quantity in postings:
        qty = dec(quantity)
        if qty <= 0: errors.add("NONPOSITIVE_POSTING")
        if kind == "Accept":
            legacy_net += qty
            mapped = receipt_by_line[line_id]
        elif kind == "Issue":
            legacy_net -= qty
            mapped = outgoing_by_line[line_id]
        elif kind == "Return":
            legacy_net += qty
            mapped = outgoing_by_line[line_id]
        else:
            errors.add("UNSUPPORTED_MOVEMENT_KIND")
            continue
        if mapped != qty: errors.add("POSTING_LOT_COVERAGE_MISMATCH")
    if dec(legacy_on_hand) != legacy_net: errors.add("LEGACY_BALANCE_MISMATCH")
    if dec(legacy_reserved) < 0: errors.add("INVALID_LEGACY_RESERVATION")
    calculated_net = Decimal(0)
    result = []
    for lot in current_lots:
        lot_id, lot_code, registered_qty, expiry_date = lot
        movements = per_lot[lot_id]
        accepted = movements["Accept"]
        issued = movements["Issue"]
        returned = movements["Return"]
        net = accepted - issued + returned
        calculated_net += net
        accepted_qa, qa_current, qa_expired = lot_qa.get(lot_id, (Decimal(0), False, False))
        flags = []
        if accepted > dec(registered_qty): flags.append("ACCEPT_EXCEEDS_RECEIPT_LOT")
        if issued > accepted: flags.append("ISSUE_EXCEEDS_ACCEPTED_PROVENANCE")
        if returned > issued: flags.append("RETURN_EXCEEDS_ISSUES")
        if net < 0: flags.append("NEGATIVE_LOT_NET")
        if not qa_current: flags.append("STALE_OR_MISSING_QA")
        if dec(accepted_qa) < accepted: flags.append("QA_ACCEPTED_BELOW_POSTED_ACCEPT")
        if qa_expired or (expiry_date and expiry_date < today): flags.append("EXPIRED_LOT")
        errors.update(flags)
        result.append({"lot_id": lot_id, "lot_code": lot_code,
            "allocated_accept": str(accepted), "allocated_issue": str(issued),
            "allocated_return": str(returned), "provisional_net": str(net),
            "qa_accepted": str(dec(accepted_qa)), "flags": flags,
            "available_to_issue": None})
    if len(set(per_lot) - {x[0] for x in current_lots}): errors.add("UNRESOLVED_LOT_REFERENCE")
    if legacy_net != calculated_net: errors.add("LOT_TOTAL_MISMATCH")
    if dec(legacy_on_hand) - dec(legacy_reserved) < 0: errors.add("RESERVED_EXCEEDS_ON_HAND")
    # A matching historical allocation alone cannot prove effective custody,
    # quality holds or lot-specific reservations at the instant of posting.
    return {"legacy_on_hand": str(dec(legacy_on_hand)),
            "legacy_reserved": str(dec(legacy_reserved)),
            "provisional_lot_net": str(calculated_net),
            "reconciliation_passed": not errors, "flags": sorted(errors),
            "lots": result, "available_to_issue": None, "issue_authorized": False,
            "warning": "Historical read-only reconciliation; never an issue authorization."}


@router.get("/lot-ledger-gate")
def lot_ledger_gate(pid: int, warehouse_id: int, item_id: int,
                    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    receipt_access(db, u, pid)
    scope = dict(project_id=pid, organization_id=u.organization_id)
    balance = db.query(StockBalance).filter_by(**scope, warehouse_id=warehouse_id, item_id=item_id).first()
    if balance is None: raise HTTPException(404, "Stock balance not found for item and warehouse")
    lines = (db.query(StockPostingLine, StockPosting).join(StockPosting, StockPosting.id == StockPostingLine.posting_id)
        .filter(StockPosting.project_id == pid, StockPosting.organization_id == u.organization_id,
                StockPosting.warehouse_id == warehouse_id, StockPosting.status == "Posted",
                StockPostingLine.item_id == item_id).all())
    line_ids = [line.id for line, _ in lines]
    receipts = (db.query(StoresPostingLotAllocation).filter(
        StoresPostingLotAllocation.project_id == pid,
        StoresPostingLotAllocation.organization_id == u.organization_id,
        StoresPostingLotAllocation.stock_posting_line_id.in_(line_ids)).all()) if line_ids else []
    outbounds = (db.query(StoresOutboundLotAllocation).filter(
        StoresOutboundLotAllocation.project_id == pid,
        StoresOutboundLotAllocation.organization_id == u.organization_id,
        StoresOutboundLotAllocation.stock_posting_line_id.in_(line_ids)).all()) if line_ids else []
    lots = db.query(StoresReceiptLot).filter_by(**scope, warehouse_id=warehouse_id).all()
    lots = [l for l in lots if any(a.receipt_lot_id == l.id for a in receipts + outbounds)]
    lot_ids = [l.id for l in lots]
    qa_rows = (db.query(StoresLotQAAttribution).filter(
        StoresLotQAAttribution.project_id == pid,
        StoresLotQAAttribution.organization_id == u.organization_id,
        StoresLotQAAttribution.receipt_lot_id.in_(lot_ids)).all()) if lot_ids else []
    cases = {c.id: c.version for c in db.query(StoresInspectionCase).filter(
        StoresInspectionCase.project_id == pid, StoresInspectionCase.organization_id == u.organization_id).all()}
    qa = defaultdict(lambda: [Decimal(0), True, False])
    for row in qa_rows:
        if row.disposition.lower() == "accepted": qa[row.receipt_lot_id][0] += dec(row.quantity)
        if cases.get(row.inspection_case_id) != row.case_version_at_entry:
            qa[row.receipt_lot_id][1] = False
    for l in lots:
        if not any(a.receipt_lot_id == l.id for a in qa_rows): qa[l.id][1] = False
    kind_by_line = {ln.id: post.kind for ln, post in lines}
    result = summarize_ledger(
        [(ln.id, post.kind, ln.quantity) for ln, post in lines],
        [(a.stock_posting_line_id, a.receipt_lot_id, a.quantity) for a in receipts],
        [(a.stock_posting_line_id, a.receipt_lot_id,
          kind_by_line.get(a.stock_posting_line_id, "Unknown"), a.quantity) for a in outbounds],
        qa, balance.on_hand, balance.reserved,
        current_lots=[(l.id, l.lot_code, l.quantity, l.expiry_date) for l in lots])
    return {"project_id": pid, "warehouse_id": warehouse_id, "item_id": item_id,
            "movement_line_count": len(lines), **result}
