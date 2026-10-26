"""Partner PO acknowledgment requests, pending buyer authorization.

Never mutates approved procurement records on behalf of an external partner.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.domains.identity_projects.security import authenticated, holds
from app.domains.identity_projects.models import User, Project
from app.domains.supply_chain.models import PurchaseOrder, Vendor
from app.domains.supply_chain.orders import acknowledge_order
from .router import _partner_company, _projects
from .models import PartnerPOAcknowledgment

router = APIRouter(prefix="/api/partner", tags=["partner-po-acknowledgment"])

class SubmitAck(BaseModel):
    note: str = Field(min_length=1, max_length=2000)
    po_version: int = Field(ge=1)

class ReviewAck(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=2000)


def _partner_po(db: Session, user: User, project_id: int, po_id: int):
    company = _partner_company(db, user)
    if project_id not in {p["project_id"] for p in _projects(db, user, company)}:
        raise HTTPException(403, "Not an active member of the partner project")
    po = db.query(PurchaseOrder).filter_by(id=po_id, organization_id=user.organization_id,
                                          project_id=project_id).first()
    if po is None:
        raise HTTPException(404, "Order not found")
    vendor = db.query(Vendor).filter_by(id=po.vendor_id, organization_id=user.organization_id,
                                        company_id=company.id, active=True).first()
    if vendor is None:
        raise HTTPException(404, "Order not found")
    return company, po


@router.post("/projects/{project_id}/purchase-orders/{po_id}/acknowledgments", status_code=201)
def submit_acknowledgment(project_id: int, po_id: int, payload: SubmitAck,
                          db: Session = Depends(get_db), user: User = Depends(authenticated)):
    company, po = _partner_po(db, user, project_id, po_id)
    if po.status != "Issued" or po.version != payload.po_version:
        raise HTTPException(409, "Order is not issued or version has changed")
    note = payload.note.strip()
    if not note:
        raise HTTPException(422, "Acknowledgment note is required")
    prior = db.query(PartnerPOAcknowledgment).filter_by(purchase_order_id=po.id,
                                                        submitted_version=po.version).first()
    if prior:
        raise HTTPException(409, "An acknowledgment has already been submitted for this order version")
    record = PartnerPOAcknowledgment(organization_id=user.organization_id, project_id=project_id,
        company_id=company.id, purchase_order_id=po.id, submitted_version=po.version,
        note=note, submitted_by=user.id, state="Pending")
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An acknowledgment already exists for this order version")
    db.refresh(record)
    return {"id": record.id, "state": record.state, "purchase_order_id": po.id,
            "message": "Submitted for buyer review. Purchase order has not been changed."}


@router.get("/projects/{project_id}/purchase-orders/{po_id}/acknowledgments")
def list_acknowledgments(project_id: int, po_id: int, db: Session = Depends(get_db),
                         user: User = Depends(authenticated)):
    _company, po = _partner_po(db, user, project_id, po_id)
    records = db.query(PartnerPOAcknowledgment).filter_by(purchase_order_id=po.id,
        organization_id=user.organization_id).order_by(PartnerPOAcknowledgment.id.desc()).all()
    return {"items": [{"id": r.id, "state": r.state, "submitted_version": r.submitted_version,
        "note": r.note, "review_note": r.review_note} for r in records]}


@router.post("/internal/projects/{project_id}/acknowledgments/{ack_id}/review")
def review_acknowledgment(project_id: int, ack_id: int, payload: ReviewAck,
                          db: Session = Depends(get_db), user: User = Depends(authenticated)):
    project = db.query(Project).filter_by(id=project_id, organization_id=user.organization_id).first()
    if project is None:
        raise HTTPException(404, "Project not found")
    if not holds(db, user, project, "procurement.po.edit"):
        raise HTTPException(403, "Buyer access required")
    record = db.query(PartnerPOAcknowledgment).filter_by(id=ack_id, project_id=project_id,
            organization_id=user.organization_id).with_for_update().first()
    if not record:
        raise HTTPException(404, "Request not found")
    if record.state != "Pending":
        raise HTTPException(409, "Request already reviewed")
    po = db.query(PurchaseOrder).filter_by(id=record.purchase_order_id, project_id=project_id,
            organization_id=user.organization_id).with_for_update().first()
    if po is None:
        raise HTTPException(404, "Order not found")
    if payload.approve:
        if po.status != "Issued" or po.version != record.submitted_version:
            raise HTTPException(409, "Order has changed since partner submission")
        acknowledge_order(db, user, project, po, record.note, record.submitted_version)
    record.state = "Approved" if payload.approve else "Rejected"
    record.review_note = payload.note.strip()
    record.reviewed_by = user.id
    record.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": record.id, "state": record.state, "purchase_order_id": po.id}
