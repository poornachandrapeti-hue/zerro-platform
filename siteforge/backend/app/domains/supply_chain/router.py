from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.engineering_documents.files import read_file, store_file
from app.domains.engineering_documents.models import StoredFile
from app.domains.identity_projects.models import User
from app.domains.identity_projects.router import audit, commit
from app.domains.identity_projects.security import authenticated, permitted, admin

from .models import (
    MaterialRequirement,
    ProcurementFile,
    ProcurementItem,
    CatalogueItemReview,
    CatalogueItemAmendment,
    CatalogueItemSpecificationHistory,
    CatalogueSpecificationTemplate,
    PurchaseRequisition,
    UnitConversion,
    Vendor,
    Warehouse,
)
from .schemas import (
    AllocateIn,
    ReleaseIn,
    UncoveredIn,
    AcknowledgeIn,
    AwardIn,
    CommercialIn,
    ConversionIn,
    ImpactIn,
    ItemIn,
    PoAmendIn,
    PoIn,
    PoUpdateIn,
    QuoteIn,
    InvoiceIn,
    InvoiceUpdateIn,
    ReceiptIn,
    AcceptIn,
    IssueIn,
    ReservationIn,
    ReturnIn,
    ReasonIn,
    RequirementIn,
    RfqIn,
    TechnicalIn,
    VersionIn,
    RequisitionIn,
    ResubmitIn,
    VendorIn,
    WarehouseIn,
)
from . import fulfilment, invoices, orders, receipts, rfq, service, stock as stock_ledger

router = APIRouter(prefix="/api")
SHEET = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _load_requirement(db, user, pid, rid):
    project = service._project(db, user, pid)
    row = db.get(MaterialRequirement, rid)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "Requirement not found")
    return project, row


def _load_requisition(db, user, pid, rid):
    project = service._project(db, user, pid)
    row = db.get(PurchaseRequisition, rid)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "Requisition not found")
    return project, row


@router.get("/projects/{pid}/procurement/dashboard")
def dashboard(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = service._project(db, u, pid)
    return service.dashboard(db, project)


@router.get("/projects/{pid}/procurement/context")
def context(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = service._project(db, u, pid)
    return service.context(db, u, project)


@router.get("/procurement/items/specification-templates")
def item_specification_templates(u: User = Depends(authenticated), db: Session = Depends(get_db)):
    from .specification_templates import configured_templates
    return configured_templates(db, u.organization_id)


@router.put("/procurement/items/specification-templates/{discipline}/{category}")
def save_specification_template(
    discipline: str, category: str, data: dict,
    u: User = Depends(admin), db: Session = Depends(get_db),
):
    from .specification_templates import validate_template_fields
    if not (1 <= len(discipline) <= 100 and 1 <= len(category) <= 120):
        raise HTTPException(422, "Invalid discipline or category")
    if not isinstance(data, dict) or set(data) != {"fields"}:
        raise HTTPException(422, "Expected fields only")
    fields = validate_template_fields(data["fields"])
    row = db.query(CatalogueSpecificationTemplate).filter_by(
        organization_id=u.organization_id, discipline=discipline, category=category).first()
    if row is None:
        row = CatalogueSpecificationTemplate(organization_id=u.organization_id,
            discipline=discipline, category=category, fields=fields,
            modified_by=u.id)
        db.add(row)
    else:
        row.fields = fields
        row.active = True
        row.version += 1
        row.modified_by = u.id
    db.flush()
    audit(db, u, "update", "procurement_specification_templates", row.id,
          {"discipline": discipline, "category": category, "version": row.version})
    commit(db)
    return {"id": row.id, "version": row.version, "fields": row.fields}



@router.get("/procurement/items/approval-capability")
def catalogue_approval_capability(u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Expose approval UI eligibility; backend decision endpoint still enforces RBAC."""
    try:
        _catalogue_approve_role(db, u)
    except HTTPException as error:
        if error.status_code == 403:
            return {"can_approve": False}
        raise
    return {"can_approve": True}


@router.get("/procurement/items")
def items(u: User = Depends(authenticated), db: Session = Depends(get_db)):
    rows = (
        db.query(ProcurementItem)
        .filter_by(organization_id=u.organization_id)
        .order_by(ProcurementItem.code)
        .all()
    )
    return [service.item_payload(row, db) for row in rows]


@router.get("/procurement/items/export.csv")
def export_catalogue(u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Organization-scoped CSV export with structured technical attributes."""
    from .catalogue_exchange import export_catalogue_csv
    rows = (db.query(ProcurementItem).filter_by(organization_id=u.organization_id)
            .order_by(ProcurementItem.code).all())
    return Response(export_catalogue_csv(rows), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=catalogue-items.csv"})


@router.post("/procurement/items", status_code=201)
def create_item(data: ItemIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    row = service.save_item(db, u, data)
    from .catalogue_specification_history import record_item_history
    record_item_history(db, u, row, "Created")
    audit(db, u, "create", "procurement_items", row.id)
    commit(db)
    db.refresh(row)
    return service.item_payload(row, db)


@router.put("/procurement/items/{item_id}")
def update_item(
    item_id: int, data: ItemIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    row = db.get(ProcurementItem, item_id)
    if not row or row.organization_id != u.organization_id:
        raise HTTPException(404, "Item not found")
    service.save_item(db, u, data, row)
    from .catalogue_specification_history import record_item_history
    record_item_history(db, u, row, "Updated")
    audit(db, u, "update", "procurement_items", row.id)
    commit(db)
    db.refresh(row)
    return service.item_payload(row, db)


def _catalogue_item(db, u, item_id):
    item = db.get(ProcurementItem, item_id)
    if item is None or item.organization_id != u.organization_id:
        raise HTTPException(404, "Item not found")
    return item


def _catalogue_approve_role(db, user):
    # Explicit permission, not procurement.master.edit: a catalogue editor must not
    # become an approver automatically. Organization administrators retain authority.
    from .catalogue_authorization import can_approve_catalogue
    from app.domains.identity_projects.models import Membership, Project, Role

    if user.organization_admin:
        return
    memberships = (
        db.query(Membership)
        .join(Project, Project.id == Membership.project_id)
        .filter(
            Membership.user_id == user.id,
            Membership.active.is_(True),
            Project.organization_id == user.organization_id,
        )
    )
    permissions = []
    for membership in memberships:
        role = db.get(Role, membership.role_id)
        if role:
            permissions.extend(role.permissions or [])
    if not can_approve_catalogue(False, permissions):
        raise HTTPException(403, "Catalogue approval permission required")


def _catalogue_decision(db, u, item, action, reason):
    db.add(CatalogueItemReview(organization_id=u.organization_id, item_id=item.id,
        action=action, reason=reason, actor_id=u.id, item_version=item.version,
        specification_snapshot={"code": item.code, "description": item.description,
            "category": item.category, "unit": item.base_unit,
            "attributes": dict(item.specification_attributes or {})}))


@router.post("/procurement/items/{item_id}/submit")
def submit_catalogue_item(item_id: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    item = _catalogue_item(db, u, item_id)
    if item.approval_status not in ("Draft", "Rejected"):
        raise HTTPException(409, "Only draft or rejected items can be submitted")
    if item.created_by != u.id and not u.organization_admin:
        raise HTTPException(403, "Only the creator or organization administrator can submit")
    item.approval_status = "Pending Approval"
    item.submitted_by = u.id
    item.active = False
    _catalogue_decision(db, u, item, "Submitted", "Submitted for review")
    from .catalogue_specification_history import record_item_history
    record_item_history(db, u, item, "Submitted", "Submitted for review")
    audit(db, u, "submit", "procurement_items", item.id)
    commit(db)
    return service.item_payload(item, db)


@router.post("/procurement/items/{item_id}/decision")
def catalogue_decision(item_id: int, data: dict, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    from .catalogue_approval import validate_decision
    action, reason = validate_decision(data)
    _catalogue_approve_role(db, u)
    item = _catalogue_item(db, u, item_id)
    if item.approval_status != "Pending Approval":
        raise HTTPException(409, "Item is not pending approval")
    if item.submitted_by == u.id or item.created_by == u.id:
        raise HTTPException(403, "Creator/submitter cannot approve or reject own item")
    item.approval_status = "Approved" if action == "Approve" else "Rejected"
    item.active = action == "Approve"
    _catalogue_decision(db, u, item, action, reason)
    from .catalogue_specification_history import record_item_history
    record_item_history(db, u, item, action, reason)
    audit(db, u, action.lower(), "procurement_items", item.id, {"reason": reason})
    commit(db)
    return service.item_payload(item, db)


@router.get("/procurement/items/{item_id}/amendments")
def list_catalogue_amendments(item_id: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _catalogue_item(db, u, item_id)
    rows = db.query(CatalogueItemAmendment).filter_by(
        organization_id=u.organization_id, item_id=item_id
    ).order_by(CatalogueItemAmendment.id).all()
    return [{"id": r.id, "status": r.status, "base_version": r.base_version,
             "changes": r.proposed, "reason": r.reason, "submitted_by": r.submitted_by,
             "decided_by": r.decided_by, "decision_reason": r.decision_reason} for r in rows]


@router.post("/procurement/items/{item_id}/amendments", status_code=201)
def submit_catalogue_amendment(item_id: int, data: dict,
                               u: User = Depends(authenticated), db: Session = Depends(get_db)):
    from .catalogue_amendments import validate_amendment
    from .specification_templates import validate_configured_attributes
    # Reuse existing master-edit authorization, not merely authenticated access.
    service._org_master(db, u)
    item = db.query(ProcurementItem).filter_by(id=item_id, organization_id=u.organization_id).with_for_update().first()
    if not item:
        raise HTTPException(404, "Item not found")
    if item.approval_status != "Approved":
        raise HTTPException(409, "Only approved catalogue items can be amended")
    if db.query(CatalogueItemAmendment).filter_by(item_id=item.id, status="Pending Approval").first():
        raise HTTPException(409, "An amendment is already pending")
    changes, reason = validate_amendment(data)
    if "specification_attributes" in changes:
        # Do not accept arbitrary technical keys. Use the existing item discipline
        # and configured template, with no client-controlled category replacement.
        from app.domains.identity_projects.models import Discipline
        names = [db.get(Discipline, x).name for x in (item.discipline_ids or [])]
        if not names:
            raise HTTPException(422, "Item has no discipline for specification validation")
        changes = dict(changes)
        changes["specification_attributes"] = validate_configured_attributes(
            db, u.organization_id, names[0], item.category, changes["specification_attributes"])
    amendment = CatalogueItemAmendment(
        organization_id=u.organization_id, item_id=item.id, base_version=item.version,
        proposed=changes, reason=reason, submitted_by=u.id)
    db.add(amendment)
    db.flush()
    audit(db, u, "submit_amendment", "procurement_items", item.id, {"amendment_id": amendment.id})
    commit(db)
    return {"id": amendment.id, "status": amendment.status, "base_version": amendment.base_version}


@router.post("/procurement/items/{item_id}/amendments/{amendment_id}/decision")
def decide_catalogue_amendment(item_id: int, amendment_id: int, data: dict,
                               u: User = Depends(authenticated), db: Session = Depends(get_db)):
    from .catalogue_amendments import require_separation, require_current_version
    from .catalogue_approval import validate_decision
    from .catalogue_specification_history import record_item_history
    from datetime import datetime, timezone
    action, reason = validate_decision(data)
    _catalogue_approve_role(db, u)
    item = db.query(ProcurementItem).filter_by(id=item_id, organization_id=u.organization_id).with_for_update().first()
    if not item:
        raise HTTPException(404, "Item not found")
    amendment = db.query(CatalogueItemAmendment).filter_by(
        id=amendment_id, organization_id=u.organization_id, item_id=item.id
    ).with_for_update().first()
    if not amendment:
        raise HTTPException(404, "Amendment not found")
    if amendment.status != "Pending Approval" or item.approval_status != "Approved":
        raise HTTPException(409, "Amendment is not eligible for decision")
    require_separation(amendment.submitted_by, item.created_by, u.id)
    require_current_version(amendment.base_version, item.version)
    if action == "Approve":
        # Snapshot before mutating active item. Do not change item code, UOM,
        # category or its immutable identity used by downstream ledgers.
        record_item_history(db, u, item, "PreAmendment", amendment.reason)
        for field, value in amendment.proposed.items():
            setattr(item, field, value)
        item.version += 1
        item.modified_by = u.id
        record_item_history(db, u, item, "Amended", reason)
    amendment.status = "Approved" if action == "Approve" else "Rejected"
    amendment.decided_by = u.id
    amendment.decision_reason = reason
    amendment.decided_at = datetime.now(timezone.utc)
    audit(db, u, "decide_amendment", "procurement_items", item.id,
          {"amendment_id": amendment.id, "decision": action, "reason": reason})
    commit(db)
    return {"id": amendment.id, "status": amendment.status, "item_version": item.version}


@router.get("/procurement/items/{item_id}/specification-history")
def catalogue_specification_history(item_id: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Read-only, organization-scoped catalogue version history."""
    _catalogue_item(db, u, item_id)
    from .catalogue_specification_history import history_payload
    rows = db.query(CatalogueItemSpecificationHistory).filter_by(
        organization_id=u.organization_id, item_id=item_id
    ).order_by(CatalogueItemSpecificationHistory.sequence).all()
    return [history_payload(row) for row in rows]


@router.get("/procurement/items/{item_id}/review-history")
def catalogue_review_history(item_id: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _catalogue_item(db, u, item_id)
    rows = db.query(CatalogueItemReview).filter_by(organization_id=u.organization_id, item_id=item_id).order_by(CatalogueItemReview.id).all()
    return [{"action": x.action, "reason": x.reason, "actor_id": x.actor_id,
             "item_version": x.item_version, "specification_snapshot": x.specification_snapshot,
             "created_at": x.created_at.isoformat()} for x in rows]


@router.get("/procurement/items/template")
def item_template(u: User = Depends(authenticated)):
    _ = u
    return Response(service.item_template(), media_type=SHEET)


@router.post("/procurement/items/import")
async def import_items(
    mode: str = "preview",
    upload: UploadFile = File(...),
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    result = service.import_items(db, u, await upload.read(), mode)
    if result["saved"]:
        audit(db, u, "import", "procurement_items", u.organization_id, {"saved": result["saved"]})
        commit(db)
    return result


@router.get("/procurement/conversions")
def conversions(u: User = Depends(authenticated), db: Session = Depends(get_db)):
    rows = db.query(UnitConversion).filter_by(organization_id=u.organization_id).all()
    return [
        {
            "id": row.id,
            "from_unit": row.from_unit,
            "to_unit": row.to_unit,
            "factor": format(row.factor, "f"),
        }
        for row in rows
    ]


@router.post("/procurement/conversions", status_code=201)
def create_conversion(
    data: ConversionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    row = service.save_conversion(db, u, data)
    audit(db, u, "create", "procurement_conversions", row.id)
    commit(db)
    db.refresh(row)
    return {"id": row.id, "from_unit": row.from_unit, "to_unit": row.to_unit, "factor": format(row.factor, "f")}


@router.get("/procurement/vendors")
def vendors(u: User = Depends(authenticated), db: Session = Depends(get_db)):
    rows = db.query(Vendor).filter_by(organization_id=u.organization_id).order_by(Vendor.code).all()
    return [service.vendor_payload(db, u, row) for row in rows]


@router.post("/procurement/vendors", status_code=201)
def create_vendor(data: VendorIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    row = service.save_vendor(db, u, data)
    audit(db, u, "create", "procurement_vendors", row.id)
    commit(db)
    db.refresh(row)
    return service.vendor_payload(db, u, row)


@router.put("/procurement/vendors/{vendor_id}")
def update_vendor(
    vendor_id: int, data: VendorIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    row = db.get(Vendor, vendor_id)
    if not row or row.organization_id != u.organization_id:
        raise HTTPException(404, "Vendor not found")
    service.save_vendor(db, u, data, row)
    audit(db, u, "update", "procurement_vendors", row.id)
    commit(db)
    db.refresh(row)
    return service.vendor_payload(db, u, row)


@router.post("/procurement/vendors/{vendor_id}/files", status_code=201)
async def vendor_file(
    vendor_id: int,
    upload: UploadFile = File(...),
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    service._org_master(db, u)
    row = db.get(Vendor, vendor_id)
    if not row or row.organization_id != u.organization_id:
        raise HTTPException(404, "Vendor not found")
    stored = store_file(db, u, upload.filename or "file", upload.content_type or "", await upload.read())
    link = ProcurementFile(
        organization_id=u.organization_id,
        resource="vendors",
        resource_id=row.id,
        file_id=stored.id,
        created_by=u.id,
    )
    db.add(link)
    audit(db, u, "upload", "procurement_vendors", row.id)
    commit(db)
    return {"id": link.id, "name": stored.original_name}


@router.get("/projects/{pid}/procurement/warehouses")
def warehouses(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = service._project(db, u, pid)
    rows = db.query(Warehouse).filter_by(project_id=project.id).order_by(Warehouse.code).all()
    return [service.warehouse_payload(db, row) for row in rows]


@router.post("/projects/{pid}/procurement/warehouses", status_code=201)
def create_warehouse(
    pid: int, data: WarehouseIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project = service._project(db, u, pid, action=None)
    row = service.save_warehouse(db, u, project, data)
    audit(db, u, "create", "procurement_warehouses", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return service.warehouse_payload(db, row)


@router.get("/projects/{pid}/procurement/requirements")
def requirements(
    pid: int,
    status: str = "",
    discipline_id: int = 0,
    q: str = "",
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    project = service._project(db, u, pid)
    query = db.query(MaterialRequirement).filter_by(project_id=project.id)
    if status == "open":
        query = query.filter(MaterialRequirement.status.in_(service.OPEN_REQUIREMENTS))
    elif status:
        query = query.filter(MaterialRequirement.status == status)
    if discipline_id:
        query = query.filter(MaterialRequirement.discipline_id == discipline_id)
    if q:
        query = query.filter(MaterialRequirement.number.ilike("%" + q + "%"))
    total = query.count()
    rows = query.order_by(MaterialRequirement.id.desc()).offset(offset).limit(limit).all()
    return {"items": [service.requirement_payload(db, u, project, row) for row in rows], "total": total}


@router.post("/projects/{pid}/procurement/requirements", status_code=201)
def create_requirement(
    pid: int, data: RequirementIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project = service._project(db, u, pid, action=None)
    row = service.create_requirement(db, u, project, data)
    audit(db, u, "create", "material_requirements", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return service.requirement_payload(db, u, project, row)


@router.get("/projects/{pid}/procurement/requirements/{rid}")
def requirement(pid: int, rid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project, row = _load_requirement(db, u, pid, rid)
    return service.requirement_payload(db, u, project, row)


@router.put("/projects/{pid}/procurement/requirements/{rid}")
def update_requirement(
    pid: int,
    rid: int,
    data: RequirementIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    project, row = _load_requirement(db, u, pid, rid)
    service.update_requirement(db, u, project, row, data)
    audit(db, u, "update", "material_requirements", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return service.requirement_payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/requirements/{rid}/submit", status_code=201)
def submit_requirement(
    pid: int, rid: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _load_requirement(db, u, pid, rid)
    service.submit_requirement(db, u, project, row, data.version)
    audit(db, u, "submit", "material_requirements", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return service.requirement_payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/requirements/{rid}/resubmit")
def resubmit_requirement(
    pid: int,
    rid: int,
    data: ResubmitIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    project, row = _load_requirement(db, u, pid, rid)
    service.resubmit_requirement(db, u, project, row, data)
    audit(db, u, "resubmit", "material_requirements", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return service.requirement_payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/requirements/{rid}/cancel")
def cancel_requirement(
    pid: int, rid: int, data: ReasonIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _load_requirement(db, u, pid, rid)
    service.cancel_requirement(db, u, project, row, data)
    audit(db, u, "cancel", "material_requirements", row.id, {"reason": data.reason}, project_id=pid)
    commit(db)
    db.refresh(row)
    return service.requirement_payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/requirements/{rid}/amend")
def amend_requirement(
    pid: int, rid: int, data: ReasonIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _load_requirement(db, u, pid, rid)
    service.amend_requirement(db, u, project, row, data)
    audit(db, u, "amend", "material_requirements", row.id, {"reason": data.reason}, project_id=pid)
    commit(db)
    db.refresh(row)
    return service.requirement_payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/requirements/{rid}/impact")
def impact(
    pid: int, rid: int, data: ImpactIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _load_requirement(db, u, pid, rid)
    service.decide_impact(db, u, project, row, data)
    audit(db, u, "impact", "material_requirements", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return service.requirement_payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/requirements/{rid}/stock")
def stock(pid: int, rid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project, row = _load_requirement(db, u, pid, rid)
    service.allocate_stock(db, u, project, row)


@router.get("/projects/{pid}/procurement/requirements/{rid}/fulfilment")
def fulfilment_check(pid: int, rid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project, row = _load_requirement(db, u, pid, rid)
    return fulfilment.check(db, u, project, row)


@router.post("/projects/{pid}/procurement/requirements/{rid}/allocations", status_code=201)
def fulfilment_allocate(
    pid: int, rid: int, data: AllocateIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _load_requirement(db, u, pid, rid)
    made = fulfilment.allocate(db, u, project, row, data)
    audit(db, u, "allocate-stock", "material_requirements", row.id, {"allocations": [item.id for item in made]}, project_id=pid)
    commit(db)
    return fulfilment.check(db, u, project, row)


@router.post("/projects/{pid}/procurement/requirements/{rid}/allocations/{aid}/release")
def fulfilment_release(
    pid: int, rid: int, aid: int, data: ReleaseIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _load_requirement(db, u, pid, rid)
    fulfilment.release(db, u, project, row, aid, data.reason)
    audit(db, u, "release-stock", "material_requirements", row.id, {"allocation": aid}, project_id=pid)
    commit(db)
    return fulfilment.check(db, u, project, row)


@router.post("/projects/{pid}/procurement/requirements/{rid}/requisition", status_code=201)
def fulfilment_requisition(
    pid: int, rid: int, data: UncoveredIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _load_requirement(db, u, pid, rid)
    created = fulfilment.requisition_for_uncovered(db, u, project, row, data)
    audit(db, u, "create", "purchase_requisitions", created.id, {"requirement": row.id}, project_id=pid)
    commit(db)
    db.refresh(created)
    return service.requisition_payload(db, u, project, created)


@router.get("/projects/{pid}/procurement/purchase-needs")
def purchase_needs(
    pid: int, show_all: bool = False, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project = service._project(db, u, pid)
    return fulfilment.purchase_needs(db, u, project, show_all)


@router.get("/projects/{pid}/procurement/requirement-template")
def requirements_template(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    service._project(db, u, pid)
    return Response(service.requirement_template(), media_type=SHEET)


@router.post("/projects/{pid}/procurement/requirement-import")
async def import_requirements(
    pid: int,
    mode: str = "preview",
    upload: UploadFile = File(...),
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    project = service._project(db, u, pid, action=None)
    result = service.import_requirements(db, u, project, await upload.read(), mode)
    if result["saved"]:
        audit(db, u, "import", "material_requirements", pid, {"saved": result["saved"]}, project_id=pid)
        commit(db)
    return result


@router.get("/projects/{pid}/procurement/requisitions")
def requisitions(
    pid: int,
    status: str = "",
    q: str = "",
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    project = service._project(db, u, pid)
    query = db.query(PurchaseRequisition).filter_by(project_id=project.id)
    if status:
        query = query.filter(PurchaseRequisition.status == status)
    if q:
        query = query.filter(PurchaseRequisition.number.ilike("%" + q + "%"))
    total = query.count()
    rows = query.order_by(PurchaseRequisition.id.desc()).offset(offset).limit(limit).all()
    return {"items": [service.requisition_payload(db, u, project, row) for row in rows], "total": total}


@router.post("/projects/{pid}/procurement/requisitions", status_code=201)
def create_requisition(
    pid: int, data: RequisitionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project = service._project(db, u, pid, action=None)
    row = service.create_requisition(db, u, project, data)
    audit(db, u, "create", "purchase_requisitions", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return service.requisition_payload(db, u, project, row)


@router.get("/projects/{pid}/procurement/requisitions/{rid}")
def requisition(pid: int, rid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project, row = _load_requisition(db, u, pid, rid)
    return service.requisition_payload(db, u, project, row)


@router.put("/projects/{pid}/procurement/requisitions/{rid}")
def update_requisition(
    pid: int,
    rid: int,
    data: RequisitionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    project, row = _load_requisition(db, u, pid, rid)
    service.update_requisition(db, u, project, row, data)
    audit(db, u, "update", "purchase_requisitions", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return service.requisition_payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/requisitions/{rid}/submit", status_code=201)
def submit_requisition(
    pid: int, rid: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _load_requisition(db, u, pid, rid)
    service.submit_requisition(db, u, project, row, data.version)
    audit(db, u, "submit", "purchase_requisitions", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return service.requisition_payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/requisitions/{rid}/resubmit")
def resubmit_requisition(
    pid: int,
    rid: int,
    data: ResubmitIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    project, row = _load_requisition(db, u, pid, rid)
    service.resubmit_requisition(db, u, project, row, data)
    audit(db, u, "resubmit", "purchase_requisitions", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return service.requisition_payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/requisitions/{rid}/cancel")
def cancel_requisition(
    pid: int, rid: int, data: ReasonIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _load_requisition(db, u, pid, rid)
    service.cancel_requisition(db, u, project, row, data)
    audit(db, u, "cancel", "purchase_requisitions", row.id, {"reason": data.reason}, project_id=pid)
    commit(db)
    db.refresh(row)
    return service.requisition_payload(db, u, project, row)


@router.get("/procurement/files/{file_id}")
def download(file_id: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    link = db.get(ProcurementFile, file_id)
    stored = db.get(StoredFile, link.file_id) if link else None
    if not link or not stored or stored.organization_id != u.organization_id:
        raise HTTPException(404, "File not found")
    if link.project_id:
        service._project(db, u, link.project_id)
    elif not u.organization_admin:
        permitted_somewhere = False
        from app.domains.identity_projects.models import Membership, Project

        for member in db.query(Membership).filter_by(user_id=u.id, active=True):
            project = db.get(Project, member.project_id)
            if project and project.organization_id == u.organization_id:
                try:
                    permitted(db, u, project, "procurement.view")
                    permitted_somewhere = True
                    break
                except HTTPException:
                    continue
        if not permitted_somewhere:
            raise HTTPException(403, "Insufficient project permission")
    return Response(read_file(stored), media_type=stored.content_type)


@router.post("/projects/{pid}/procurement/requisitions/{rid}/files", status_code=201)
async def requisition_file(
    pid: int,
    rid: int,
    upload: UploadFile = File(...),
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    project, row = _load_requisition(db, u, pid, rid)
    permitted(db, u, project, "procurement.requisition.edit", row.discipline_id)
    stored = store_file(db, u, upload.filename or "file", upload.content_type or "", await upload.read())
    link = ProcurementFile(
        organization_id=u.organization_id,
        project_id=project.id,
        resource="requisitions",
        resource_id=row.id,
        file_id=stored.id,
        created_by=u.id,
    )
    db.add(link)
    audit(db, u, "upload", "purchase_requisitions", row.id, project_id=pid)
    commit(db)
    return {"id": link.id, "name": stored.original_name}


@router.get("/projects/{pid}/procurement/rfq-sources")
def rfq_sources(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = service._project(db, u, pid)
    return rfq.sources(db, project)


@router.get("/projects/{pid}/procurement/rfqs")
def rfq_list(
    pid: int,
    status: str = "",
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    project = service._project(db, u, pid)
    return rfq.list_rfqs(db, u, project, status)


@router.post("/projects/{pid}/procurement/rfqs", status_code=201)
def rfq_create(pid: int, data: RfqIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = service._project(db, u, pid)
    row = rfq.create_rfq(db, u, project, data)
    audit(db, u, "create", "request_for_quotations", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return rfq.payload(db, u, project, row)


def _rfq(db, user, pid, rid):
    project = service._project(db, user, pid)
    row = db.get(rfq.RequestForQuotation, rid)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "RFQ not found")
    return project, row


@router.get("/projects/{pid}/procurement/rfqs/{rid}")
def rfq_detail(pid: int, rid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project, row = _rfq(db, u, pid, rid)
    return rfq.payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/rfqs/{rid}/issue")
def rfq_issue(pid: int, rid: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project, row = _rfq(db, u, pid, rid)
    rfq.issue_rfq(db, u, project, row, data.version)
    audit(db, u, "issue", "request_for_quotations", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return rfq.payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/rfqs/{rid}/cancel")
def rfq_cancel(pid: int, rid: int, data: ReasonIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project, row = _rfq(db, u, pid, rid)
    rfq.cancel_rfq(db, u, project, row, data.reason, data.version)
    audit(db, u, "cancel", "request_for_quotations", row.id, {"reason": data.reason}, project_id=pid)
    commit(db)
    db.refresh(row)
    return rfq.payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/rfqs/{rid}/quotations", status_code=201)
def rfq_quote(pid: int, rid: int, data: QuoteIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project, row = _rfq(db, u, pid, rid)
    rfq.add_quotation(db, u, project, row, data)
    audit(db, u, "quote", "request_for_quotations", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return rfq.payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/rfqs/{rid}/technical-review")
def rfq_start_technical(
    pid: int, rid: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _rfq(db, u, pid, rid)
    rfq.start_technical(db, u, project, row, data.version)
    audit(db, u, "technical", "request_for_quotations", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return rfq.payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/rfqs/{rid}/technical")
def rfq_technical(
    pid: int, rid: int, data: TechnicalIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _rfq(db, u, pid, rid)
    rfq.decide_technical(db, u, project, row, data)
    audit(db, u, "technical-decision", "request_for_quotations", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return rfq.payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/rfqs/{rid}/commercial")
def rfq_commercial(
    pid: int, rid: int, data: CommercialIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _rfq(db, u, pid, rid)
    rfq.save_commercial(db, u, project, row, data)
    audit(db, u, "commercial", "request_for_quotations", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return rfq.payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/rfqs/{rid}/award")
def rfq_award(pid: int, rid: int, data: AwardIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project, row = _rfq(db, u, pid, rid)
    rfq.award(db, u, project, row, data)
    audit(db, u, "award", "request_for_quotations", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return rfq.payload(db, u, project, row)


@router.get("/projects/{pid}/procurement/order-sources")
def order_sources(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = service._project(db, u, pid)
    return orders.sources(db, project)


@router.get("/projects/{pid}/procurement/orders")
def order_list(
    pid: int,
    status: str = "",
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    project = service._project(db, u, pid)
    return orders.list_orders(db, u, project, status)


@router.post("/projects/{pid}/procurement/orders", status_code=201)
def order_create(pid: int, data: PoIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = service._project(db, u, pid)
    row = orders.create_order(db, u, project, data)
    audit(db, u, "create", "purchase_orders", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return orders.payload(db, u, project, row)


def _order(db, user, pid, oid):
    project = service._project(db, user, pid)
    row = db.get(orders.PurchaseOrder, oid)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "Purchase order not found")
    return project, row


@router.get("/projects/{pid}/procurement/orders/{oid}")
def order_detail(pid: int, oid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project, row = _order(db, u, pid, oid)
    return orders.payload(db, u, project, row)


@router.put("/projects/{pid}/procurement/orders/{oid}")
def order_update(
    pid: int, oid: int, data: PoUpdateIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _order(db, u, pid, oid)
    orders.update_order(db, u, project, row, data)
    audit(db, u, "update", "purchase_orders", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return orders.payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/orders/{oid}/submit", status_code=201)
def order_submit(
    pid: int, oid: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _order(db, u, pid, oid)
    orders.submit_order(db, u, project, row, data.version)
    audit(db, u, "submit", "purchase_orders", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return orders.payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/orders/{oid}/resubmit")
def order_resubmit(
    pid: int, oid: int, data: ResubmitIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _order(db, u, pid, oid)
    orders.resubmit_order(db, u, project, row, data)
    audit(db, u, "resubmit", "purchase_orders", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return orders.payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/orders/{oid}/issue")
def order_issue(
    pid: int, oid: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _order(db, u, pid, oid)
    orders.issue_order(db, u, project, row, data.version)
    audit(db, u, "issue", "purchase_orders", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return orders.payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/orders/{oid}/acknowledge")
def order_acknowledge(
    pid: int, oid: int, data: AcknowledgeIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _order(db, u, pid, oid)
    orders.acknowledge_order(db, u, project, row, data.note, data.version)
    audit(db, u, "acknowledge", "purchase_orders", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return orders.payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/orders/{oid}/cancel")
def order_cancel(
    pid: int, oid: int, data: ReasonIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _order(db, u, pid, oid)
    orders.cancel_order(db, u, project, row, data.reason, data.version)
    audit(db, u, "cancel", "purchase_orders", row.id, {"reason": data.reason}, project_id=pid)
    commit(db)
    db.refresh(row)
    return orders.payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/orders/{oid}/amendments", status_code=201)
def order_amend(
    pid: int, oid: int, data: PoAmendIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _order(db, u, pid, oid)
    created = orders.amend_order(db, u, project, row, data)
    audit(db, u, "amend", "purchase_orders", created.id, project_id=pid)
    commit(db)
    db.refresh(created)
    return orders.payload(db, u, project, created)


@router.post("/projects/{pid}/procurement/orders/{oid}/close")
def order_close(pid: int, oid: int, data: ReasonIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project, row = _order(db, u, pid, oid)
    orders.close_order(db, u, project, row, data.reason, data.version)
    audit(db, u, "close", "purchase_orders", row.id, {"reason": data.reason}, project_id=pid)
    commit(db)
    db.refresh(row)
    return orders.payload(db, u, project, row)


@router.get("/projects/{pid}/procurement/receipt-sources")
def receipt_sources(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = service._project(db, u, pid)
    return receipts.sources(db, project)


@router.get("/projects/{pid}/procurement/receipts")
def receipt_list(
    pid: int,
    status: str = "",
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    project = service._project(db, u, pid)
    return receipts.list_receipts(db, u, project, status)


@router.post("/projects/{pid}/procurement/receipts", status_code=201)
def receipt_create(pid: int, data: ReceiptIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = service._project(db, u, pid)
    row = receipts.create_receipt(db, u, project, data)
    audit(db, u, "create", "goods_receipts", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return receipts.payload(db, u, project, row)


def _receipt(db, user, pid, rid):
    project = service._project(db, user, pid)
    row = db.get(receipts.GoodsReceipt, rid)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "Goods receipt not found")
    return project, row


@router.get("/projects/{pid}/procurement/receipts/{rid}")
def receipt_detail(pid: int, rid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project, row = _receipt(db, u, pid, rid)
    return receipts.payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/receipts/{rid}/cancel")
def receipt_cancel(
    pid: int, rid: int, data: ReasonIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _receipt(db, u, pid, rid)
    receipts.cancel_receipt(db, u, project, row, data.reason, data.version)
    audit(db, u, "cancel", "goods_receipts", row.id, {"reason": data.reason}, project_id=pid)
    commit(db)
    db.refresh(row)
    return receipts.payload(db, u, project, row)


@router.get("/projects/{pid}/procurement/stock")
def stock_balances(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = service._project(db, u, pid)
    return stock_ledger.balances(db, project)


@router.get("/projects/{pid}/procurement/stock/accept-sources")
def stock_accept_sources(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = service._project(db, u, pid)
    return stock_ledger.accept_sources(db, project)


@router.get("/projects/{pid}/procurement/stock/issue-sources")
def stock_issue_sources(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = service._project(db, u, pid)
    return stock_ledger.issue_sources(db, project)


@router.get("/projects/{pid}/procurement/stock/postings")
def stock_postings(
    pid: int,
    kind: str = "",
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    project = service._project(db, u, pid)
    return stock_ledger.list_postings(db, project, kind)


def _post_stock(db, user, pid, creator):
    project = service._project(db, user, pid)
    row = creator(db, user, project)
    audit(db, user, "create", "stock_postings", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return stock_ledger.payload(db, project, row)


@router.post("/projects/{pid}/procurement/stock/acceptances", status_code=201)
def stock_accept(pid: int, data: AcceptIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    return _post_stock(db, u, pid, lambda db, user, project: stock_ledger.accept_receipt(db, user, project, data))


@router.post("/projects/{pid}/procurement/stock/reservations", status_code=201)
def stock_reserve(pid: int, data: ReservationIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    return _post_stock(db, u, pid, lambda db, user, project: stock_ledger.reserve_stock(db, user, project, data))


@router.post("/projects/{pid}/procurement/stock/issues", status_code=201)
def stock_issue(pid: int, data: IssueIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    return _post_stock(db, u, pid, lambda db, user, project: stock_ledger.issue_stock(db, user, project, data))


@router.post("/projects/{pid}/procurement/stock/returns", status_code=201)
def stock_return(pid: int, data: ReturnIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    return _post_stock(db, u, pid, lambda db, user, project: stock_ledger.return_stock(db, user, project, data))


@router.post("/projects/{pid}/procurement/stock/postings/{sid}/cancel")
def stock_cancel(
    pid: int, sid: int, data: ReasonIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project = service._project(db, u, pid)
    row = db.get(stock_ledger.StockPosting, sid)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "Stock movement not found")
    stock_ledger.cancel_posting(db, u, project, row, data.reason, data.version)
    audit(db, u, "cancel", "stock_postings", row.id, {"reason": data.reason}, project_id=pid)
    commit(db)
    db.refresh(row)
    return stock_ledger.payload(db, project, row)


@router.get("/projects/{pid}/procurement/invoice-sources")
def invoice_sources(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = service._project(db, u, pid)
    return invoices.sources(db, u, project)


@router.get("/projects/{pid}/procurement/invoices")
def invoice_list(
    pid: int,
    status: str = "",
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    project = service._project(db, u, pid)
    return invoices.list_invoices(db, u, project, status)


@router.post("/projects/{pid}/procurement/invoices", status_code=201)
def invoice_create(pid: int, data: InvoiceIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = service._project(db, u, pid)
    row = invoices.create_invoice(db, u, project, data)
    audit(db, u, "create", "vendor_invoices", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return invoices.payload(db, u, project, row)


def _invoice(db, user, pid, iid):
    project = service._project(db, user, pid)
    row = db.get(invoices.VendorInvoice, iid)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "Vendor invoice not found")
    return project, row


@router.get("/projects/{pid}/procurement/invoices/{iid}")
def invoice_detail(pid: int, iid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project, row = _invoice(db, u, pid, iid)
    return invoices.payload(db, u, project, row)


@router.put("/projects/{pid}/procurement/invoices/{iid}")
def invoice_update(
    pid: int, iid: int, data: InvoiceUpdateIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _invoice(db, u, pid, iid)
    invoices.update_invoice(db, u, project, row, data)
    audit(db, u, "update", "vendor_invoices", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return invoices.payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/invoices/{iid}/record")
def invoice_record(
    pid: int, iid: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _invoice(db, u, pid, iid)
    invoices.record_invoice(db, u, project, row, data.version)
    audit(db, u, "record", "vendor_invoices", row.id, project_id=pid)
    commit(db)
    db.refresh(row)
    return invoices.payload(db, u, project, row)


@router.post("/projects/{pid}/procurement/invoices/{iid}/cancel")
def invoice_cancel(
    pid: int, iid: int, data: ReasonIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    project, row = _invoice(db, u, pid, iid)
    invoices.cancel_invoice(db, u, project, row, data.reason, data.version)
    audit(db, u, "cancel", "vendor_invoices", row.id, {"reason": data.reason}, project_id=pid)
    commit(db)
    db.refresh(row)
    return invoices.payload(db, u, project, row)
