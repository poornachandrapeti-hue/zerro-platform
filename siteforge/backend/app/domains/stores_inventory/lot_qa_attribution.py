"""QA-approved lot attribution against existing receipt-line dispositions.

This is evidence of which lot belongs to a line-level QA decision, NOT a stock
posting, available balance, or permission to issue. Both the inspection case and
lot row are locked while allocating to avoid concurrent overallocation.
"""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from .models import StoresInspectionCase, StoresReceiptLot, StoresLotQAAttribution
from .router import qa_access, receipt_access, audit, commit

router = APIRouter(prefix="/api/projects/{pid}/stores", tags=["Stores & Inventory"])
DISPOSITIONS = ("Accepted", "Rejected", "Quarantined")


class LotQAAttributionIn(BaseModel):
    lot_id: int = Field(gt=0)
    disposition: str
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    reason: str = Field(min_length=5, max_length=2000)
    idempotency_key: str = Field(min_length=8, max_length=120)
    expected_case_version: int = Field(ge=1)


def available_to_attribute(line_totals, lot_totals, disposition, requested):
    """Pure guard used by the endpoint and regression tests."""
    if disposition not in DISPOSITIONS:
        raise ValueError("Invalid disposition")
    requested = Decimal(str(requested))
    if requested <= 0:
        raise ValueError("Quantity must be positive")
    if requested > Decimal(str(line_totals[disposition])):
        raise ValueError("Exceeded QA-approved receipt-line quantity")
    if requested > Decimal(str(lot_totals["unallocated"])):
        raise ValueError("Exceeded unallocated receipt-lot quantity")


def payload(record):
    return {"id": record.id, "lot_id": record.receipt_lot_id,
            "inspection_case_id": record.inspection_case_id,
            "disposition": record.disposition, "quantity": str(record.quantity),
            "reason": record.reason, "created_by": record.created_by,
            "created_at": record.created_at.isoformat() if record.created_at else None}


@router.post("/lot-qa-attributions", status_code=201)
def attribute_lot_qa(pid: int, data: LotQAAttributionIn,
                     u: User = Depends(authenticated), db: Session = Depends(get_db)):
    qa_access(db, u, pid, edit=True)
    if data.disposition not in DISPOSITIONS:
        raise HTTPException(422, "Unsupported QA disposition")
    lot = (db.query(StoresReceiptLot).filter_by(id=data.lot_id,
        organization_id=u.organization_id, project_id=pid).with_for_update().first())
    if not lot:
        raise HTTPException(404, "Receipt lot not found")
    case = (db.query(StoresInspectionCase).filter_by(
        goods_receipt_line_id=lot.goods_receipt_line_id,
        organization_id=u.organization_id, project_id=pid).with_for_update().first())
    if not case:
        raise HTTPException(409, "Receipt line has no QA inspection case")
    previous = db.query(StoresLotQAAttribution).filter_by(
        inspection_case_id=case.id, idempotency_key=data.idempotency_key).first()
    if previous:
        if (previous.receipt_lot_id != lot.id or previous.disposition != data.disposition
            or previous.quantity != data.quantity or previous.reason != data.reason.strip()):
            raise HTTPException(409, "Idempotency key reused with different payload")
        return payload(previous)
    if case.version != data.expected_case_version:
        raise HTTPException(409, "QA case changed; refresh before attributing")
    allocated_by_disposition = dict(db.query(
        StoresLotQAAttribution.disposition, func.coalesce(func.sum(StoresLotQAAttribution.quantity), 0)
    ).filter_by(inspection_case_id=case.id).group_by(StoresLotQAAttribution.disposition).all())
    attributed_lot = db.query(func.coalesce(func.sum(StoresLotQAAttribution.quantity), 0)).filter_by(
        receipt_lot_id=lot.id).scalar() or Decimal(0)
    approved = {"Accepted": case.accepted_qty, "Rejected": case.rejected_qty,
                "Quarantined": case.quarantined_qty}
    remaining = {k: Decimal(str(v)) - Decimal(str(allocated_by_disposition.get(k, 0)))
                 for k, v in approved.items()}
    try:
        available_to_attribute(remaining, {"unallocated": Decimal(str(lot.quantity)) - Decimal(str(attributed_lot))},
                               data.disposition, data.quantity)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    row = StoresLotQAAttribution(organization_id=u.organization_id, project_id=pid,
        inspection_case_id=case.id, receipt_lot_id=lot.id, disposition=data.disposition,
        quantity=data.quantity, reason=data.reason.strip(), idempotency_key=data.idempotency_key,
        case_version_at_entry=case.version, created_by=u.id)
    db.add(row)
    audit(db, u, "lot_qa_attribution", "stores_receipt_lots", lot.id,
          project_id=pid, details={"case_id": case.id, "disposition": data.disposition,
              "quantity": str(data.quantity)})
    commit(db)
    return payload(row)


@router.get("/lot-qa-attributions")
def list_lot_qa(pid: int, grn_line_id: int,
                u: User = Depends(authenticated), db: Session = Depends(get_db)):
    receipt_access(db, u, pid)
    case = db.query(StoresInspectionCase).filter_by(goods_receipt_line_id=grn_line_id,
        organization_id=u.organization_id, project_id=pid).first()
    if not case:
        return {"rows": [], "issue_enabled": False, "warning": "No inspection case"}
    lots = db.query(StoresReceiptLot).filter_by(goods_receipt_line_id=grn_line_id,
        organization_id=u.organization_id, project_id=pid).all()
    lot_ids = [r.id for r in lots]
    rows = db.query(StoresLotQAAttribution).filter(
        StoresLotQAAttribution.inspection_case_id == case.id,
        StoresLotQAAttribution.receipt_lot_id.in_(lot_ids)).order_by(
        StoresLotQAAttribution.id).all() if lot_ids else []
    totals = {k: Decimal(0) for k in DISPOSITIONS}
    for row in rows:
        totals[row.disposition] += row.quantity
    current = {"Accepted": case.accepted_qty, "Rejected": case.rejected_qty,
               "Quarantined": case.quarantined_qty}
    return {"rows": [payload(r) for r in rows],
        "attributed": {k: str(v) for k, v in totals.items()},
        "qa_line_dispositions": {k: str(v) for k, v in current.items()},
        "qa_case_version": case.version,
        "requires_reconciliation": any(totals[k] != current[k] for k in DISPOSITIONS),
        "issue_enabled": False,
        "warning": "Lot attribution is not stock release. Revocations, outbound movements and legacy balance migration must be reconciled before lot-level issue."}
