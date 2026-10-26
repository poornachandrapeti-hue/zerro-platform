"""Security-first, read-only external partner workspace endpoints.

These endpoints intentionally do NOT delegate transaction access. Procurement,
construction, QA and finance actions require separate resource-level checks.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.stores_inventory.router import NoticeIn
from app.domains.identity_projects.models import (
    Company, Membership, Project, ProjectCompany, Role, User,
)
from app.domains.identity_projects.security import authenticated

router = APIRouter(prefix="/api/partner", tags=["partner-portal"])


def _partner_company(db: Session, user: User) -> Company:
    # Organization administrators should use the internal workspace.
    if user.organization_admin or user.company_id is None:
        raise HTTPException(status_code=403, detail="Partner company access required")
    company = db.get(Company, user.company_id)
    if not company or not company.active or company.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Inactive or invalid partner company")
    return company


def _projects(db: Session, user: User, company: Company):
    # Require ALL three: organization ownership, active project-company
    # participation, and a matching active membership for this user/company.
    rows = (
        db.query(Project, ProjectCompany, Membership)
        .join(ProjectCompany, ProjectCompany.project_id == Project.id)
        .join(Membership, Membership.project_id == Project.id)
        .filter(
            Project.organization_id == user.organization_id,
            ProjectCompany.company_id == company.id,
            ProjectCompany.active.is_(True),
            Membership.company_id == company.id,
            Membership.user_id == user.id,
            Membership.active.is_(True),
        )
        .order_by(Project.id)
        .all()
    )
    projects = {}
    for project, association, membership in rows:
        role = db.get(Role, membership.role_id)
        if role is None:
            continue
        item = projects.setdefault(project.id, {
            "project_id": project.id,
            "code": project.code,
            "name": project.name,
            "status": project.status,
            "participation_type": association.participation_type,
            "roles": [],
        })
        if role.name not in item["roles"]:
            item["roles"].append(role.name)
    return list(projects.values())


@router.get("/context")
def partner_context(
    db: Session = Depends(get_db), user: User = Depends(authenticated)
):
    company = _partner_company(db, user)
    projects = _projects(db, user, company)
    return {
        "user": {"id": user.id, "name": user.name},
        "company": {"id": company.id, "name": company.name, "type": company.company_type},
        "projects": projects,
        "capabilities": {"project_list": True, "transactions": False, "billing": False},
    }


@router.get("/projects")
def partner_projects(
    db: Session = Depends(get_db), user: User = Depends(authenticated)
):
    company = _partner_company(db, user)
    return {"items": _projects(db, user, company)}


# Supplier may submit advance shipping notice only for a PO awarded to its company.
# The operation deliberately does NOT post a GRN or make stock available.
@router.get("/projects/{pid}/stores/delivery-notices")
def supplier_delivery_notices(pid: int, db: Session = Depends(get_db), user: User = Depends(authenticated)):
    from app.domains.stores_inventory.models import StoresDeliveryNotice
    company = _partner_company(db, user)
    if pid not in {p["project_id"] for p in _projects(db, user, company)}:
        raise HTTPException(403, "Partner project membership required")
    from app.domains.stores_inventory.router import _notice_payload
    return [_notice_payload(row) for row in db.query(StoresDeliveryNotice).filter_by(
        organization_id=user.organization_id, project_id=pid, vendor_company_id=company.id).all()]


@router.post("/projects/{pid}/stores/delivery-notices", status_code=201)
def supplier_submit_notice(pid: int, data: "NoticeIn", db: Session = Depends(get_db), user: User = Depends(authenticated)):
    from app.domains.stores_inventory.router import _save_notice
    company = _partner_company(db, user)
    if pid not in {p["project_id"] for p in _projects(db, user, company)}:
        raise HTTPException(403, "Partner project membership required")
    return _save_notice(db, user, pid, data, company_id=company.id)


@router.get("/projects/{pid}/stores/notice-sources")
def supplier_notice_sources(pid: int, db: Session = Depends(get_db), user: User = Depends(authenticated)):
    """Only the current supplier's eligible POs; no pricing or unrelated vendor data."""
    from app.domains.supply_chain.models import PurchaseOrder, PurchaseOrderLine, Vendor
    from app.domains.supply_chain.receipts import OPEN
    company = _partner_company(db, user)
    if pid not in {p["project_id"] for p in _projects(db, user, company)}:
        raise HTTPException(403, "Partner project membership required")
    rows = (db.query(PurchaseOrder).join(Vendor, Vendor.id == PurchaseOrder.vendor_id)
        .filter(PurchaseOrder.organization_id == user.organization_id,
                PurchaseOrder.project_id == pid, Vendor.company_id == company.id,
                PurchaseOrder.status.in_(OPEN)).order_by(PurchaseOrder.id.desc()).all())
    return [{"purchase_order_id": order.id, "number": order.number,
             "lines": [{"purchase_order_line_id": line.id, "quantity": str(line.quantity)}
                       for line in db.query(PurchaseOrderLine).filter_by(purchase_order_id=order.id)
                       .order_by(PurchaseOrderLine.position).all()]}
            for order in rows]


# Supplier-private evidence for its own ASN, never unrestricted project files.
@router.get("/projects/{pid}/stores/delivery-notices/{notice_id}/evidence")
def supplier_evidence_list(pid: int, notice_id: int, db: Session = Depends(get_db), user: User = Depends(authenticated)):
    from app.domains.stores_inventory.router import list_stores_evidence
    company = _partner_company(db, user)
    if pid not in {p["project_id"] for p in _projects(db, user, company)}:
        raise HTTPException(403, "Partner project membership required")
    return list_stores_evidence(db, user, pid, "notice", notice_id, partner_company_id=company.id)


@router.post("/projects/{pid}/stores/delivery-notices/{notice_id}/evidence", status_code=201)
async def supplier_evidence_upload(pid: int, notice_id: int, upload: UploadFile = File(...),
                                   db: Session = Depends(get_db), user: User = Depends(authenticated)):
    from app.domains.stores_inventory.router import add_stores_evidence
    company = _partner_company(db, user)
    if pid not in {p["project_id"] for p in _projects(db, user, company)}:
        raise HTTPException(403, "Partner project membership required")
    return await add_stores_evidence(db, user, pid, "notice", notice_id, upload, partner_company_id=company.id)


@router.get("/projects/{pid}/stores/delivery-notices/{notice_id}/evidence/{evidence_id}/download")
def supplier_evidence_download(pid: int, notice_id: int, evidence_id: int,
                               db: Session = Depends(get_db), user: User = Depends(authenticated)):
    from app.domains.stores_inventory.router import download_stores_evidence
    company = _partner_company(db, user)
    if pid not in {p["project_id"] for p in _projects(db, user, company)}:
        raise HTTPException(403, "Partner project membership required")
    return download_stores_evidence(db, user, pid, "notice", notice_id, evidence_id, partner_company_id=company.id)
