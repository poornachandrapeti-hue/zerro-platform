"""Partner-owned, read-only transaction APIs.

Every endpoint constrains results by the authenticated user's organization,
active project/company membership and the actual vendor/contractor association.
Never use these views as a substitute for authorization on internal routes.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.models import User
from app.domains.supply_chain.models import (Vendor, RfqInvite, RequestForQuotation,
    VendorQuotation, PurchaseOrder, VendorInvoice)
from app.domains.construction.models import WorkPackage
from app.domains.engineering_documents.models import Drawing, DrawingRevision, MaterialTakeoff
from app.domains.supply_chain.models import MaterialRequirement
from app.domains.construction.models import WorkPackageDrawing, WorkPackageRequirement
from .router import _partner_company, _projects

router = APIRouter(prefix="/api/partner", tags=["partner-transactions"])


def _scope(db: Session, user: User, project_id: int):
    company = _partner_company(db, user)
    if not any(p["project_id"] == project_id for p in _projects(db, user, company)):
        raise HTTPException(403, "No active company and user membership for this project")
    return company


def _vendor_ids(db: Session, user: User, company_id: int):
    return [v.id for v in db.query(Vendor.id).filter(Vendor.organization_id == user.organization_id,
                                                      Vendor.company_id == company_id, Vendor.active.is_(True)).all()]


@router.get("/projects/{project_id}/overview")
def overview(project_id: int, db: Session = Depends(get_db), user: User = Depends(authenticated)):
    company = _scope(db, user, project_id)
    vendors = _vendor_ids(db, user, company.id)
    po_query = db.query(PurchaseOrder).filter(PurchaseOrder.organization_id == user.organization_id,
        PurchaseOrder.project_id == project_id, PurchaseOrder.vendor_id.in_(vendors))
    return {"project_id": project_id, "company_id": company.id,
        "purchase_orders": po_query.count(),
        "quotations": db.query(VendorQuotation).join(RequestForQuotation,
            VendorQuotation.rfq_id == RequestForQuotation.id).filter(
            RequestForQuotation.organization_id == user.organization_id,
            RequestForQuotation.project_id == project_id, VendorQuotation.vendor_id.in_(vendors)).count(),
        "work_packages": db.query(WorkPackage).filter(WorkPackage.organization_id == user.organization_id,
            WorkPackage.project_id == project_id, WorkPackage.company_id == company.id).count(),
        "payments": {"available": False, "reason": "Verified payment ledger not connected"}}


@router.get("/projects/{project_id}/transactions")
def transactions(project_id: int, kind: str = Query("purchase_orders", pattern="^(rfqs|quotations|purchase_orders|invoices|work_packages)$"),
                 limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(authenticated)):
    company = _scope(db, user, project_id)
    vendors = _vendor_ids(db, user, company.id)
    scope_po = (PurchaseOrder.organization_id == user.organization_id,
                PurchaseOrder.project_id == project_id, PurchaseOrder.vendor_id.in_(vendors))
    if kind == "purchase_orders":
        rows = db.query(PurchaseOrder).filter(*scope_po).order_by(PurchaseOrder.id.desc()).limit(limit).all()
        items = [{"id": r.id, "reference": r.number, "status": r.status, "currency": r.currency,
                  "version": r.version,
                  "promised_date": r.promised_date.isoformat() if r.promised_date else None} for r in rows]
    elif kind == "invoices":
        rows = db.query(VendorInvoice).join(PurchaseOrder, VendorInvoice.purchase_order_id == PurchaseOrder.id).filter(
            VendorInvoice.organization_id == user.organization_id, VendorInvoice.project_id == project_id,
            *scope_po).order_by(VendorInvoice.id.desc()).limit(limit).all()
        items = [{"id": r.id, "reference": r.number, "status": r.status,
                  "invoice_date": r.invoice_date.isoformat() if r.invoice_date else None} for r in rows]
    elif kind == "rfqs":
        rows = db.query(RequestForQuotation).join(RfqInvite, RfqInvite.rfq_id == RequestForQuotation.id).filter(
            RequestForQuotation.organization_id == user.organization_id,
            RequestForQuotation.project_id == project_id, RfqInvite.vendor_id.in_(vendors)).distinct().order_by(RequestForQuotation.id.desc()).limit(limit).all()
        items = [{"id": r.id, "reference": r.number, "status": r.status,
                  "due_date": r.due_date.isoformat() if r.due_date else None} for r in rows]
    elif kind == "quotations":
        rows = db.query(VendorQuotation).join(RequestForQuotation, VendorQuotation.rfq_id == RequestForQuotation.id).filter(
            RequestForQuotation.organization_id == user.organization_id,
            RequestForQuotation.project_id == project_id, VendorQuotation.vendor_id.in_(vendors)).order_by(VendorQuotation.id.desc()).limit(limit).all()
        items = [{"id": r.id, "reference": r.reference, "currency": r.currency,
                  "quotation_date": r.quotation_date.isoformat() if r.quotation_date else None} for r in rows]
    else:
        rows = db.query(WorkPackage).filter(WorkPackage.organization_id == user.organization_id,
            WorkPackage.project_id == project_id, WorkPackage.company_id == company.id).order_by(WorkPackage.id.desc()).limit(limit).all()
        items = [{"id": r.id, "reference": r.code, "name": r.name, "status": r.status,
                  "release_state": r.release_state} for r in rows]
    return {"kind": kind, "project_id": project_id, "items": items}


@router.get("/projects/{project_id}/trace/drawings/{drawing_id}")
def drawing_trace(project_id: int, drawing_id: int, db: Session = Depends(get_db), user: User = Depends(authenticated)):
    """Conservative tracing: only partner-owned packages and requisitions are exposed.

    Other organizations' engineering or commercial records must never leak.
    """
    company = _scope(db, user, project_id)
    drawing = db.query(Drawing).filter(Drawing.id == drawing_id, Drawing.project_id == project_id,
        Drawing.organization_id == user.organization_id).first()
    if drawing is None:
        raise HTTPException(404, "Drawing not found")
    packages = db.query(WorkPackage).join(WorkPackageDrawing, WorkPackageDrawing.package_id == WorkPackage.id).join(
        DrawingRevision, WorkPackageDrawing.revision_id == DrawingRevision.id).filter(
        WorkPackage.organization_id == user.organization_id, WorkPackage.project_id == project_id,
        WorkPackage.company_id == company.id, DrawingRevision.drawing_id == drawing_id).distinct().all()
    requirements = db.query(MaterialRequirement).filter(MaterialRequirement.organization_id == user.organization_id,
        MaterialRequirement.project_id == project_id, MaterialRequirement.company_id == company.id,
        MaterialRequirement.drawing_id == drawing_id).all()
    if drawing.company_id != company.id and not packages and not requirements:
        raise HTTPException(404, "No authorized trace records")
    revisions = db.query(DrawingRevision).filter(DrawingRevision.drawing_id == drawing_id).order_by(DrawingRevision.sequence).all()
    return {"drawing": {"id": drawing.id, "number": drawing.number, "title": drawing.title},
            "revisions": [{"id": r.id, "code": r.code, "release_state": r.release_state} for r in revisions],
            "requirements": [{"id": r.id, "reference": r.number, "impact_state": r.impact_state} for r in requirements],
            "work_packages": [{"id": p.id, "reference": p.code, "status": p.status} for p in packages],
            "billing": {"available": False, "reason": "Certified RA billing is not implemented"}}
