from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.coordination.models import ReviewDecision, ReviewInstance
from app.domains.engineering_documents.files import read_file, store_file
from app.domains.engineering_documents.models import Drawing, ProjectFile, StoredFile
from app.domains.identity_projects.lifecycle import apply_transition
from .models import Area, Audit, Company, Membership, ProjectCompany, User

FILE_CATEGORIES = {
    "Contract/PO",
    "Scope of Work",
    "Site Layout",
    "Project Schedule",
    "Other Supporting Documents",
    "Setup",
}
from .router import audit, commit, company_blocked, holds, permitted, project, project_dict
from .schemas import AreaUpdate, CompanyUpdate, ParticipationUpdate, TransitionIn
from .security import admin, authenticated

router = APIRouter(prefix="/api")


def _bump(db, model, row_id, version, values):
    result = db.execute(
        update(model).where(model.id == row_id, model.version == version).values(
            **values, version=version + 1
        )
    )
    if result.rowcount != 1:
        raise HTTPException(409, "Record changed. Reload it and try again")


@router.put("/companies/{cid}")
def edit_company(
    cid: int, data: CompanyUpdate, u: User = Depends(admin), db: Session = Depends(get_db)
):
    row = db.get(Company, cid)
    if not row or row.organization_id != u.organization_id:
        raise HTTPException(404, "Company not found")
    if not data.active and row.active:
        if db.query(User).filter_by(company_id=cid, active=True).first():
            raise HTTPException(409, "Reassign active users before deactivating this company")
        if db.query(ProjectCompany).filter_by(company_id=cid, active=True).first():
            raise HTTPException(
                409, "Remove active project participation before deactivating this company"
            )
    _bump(
        db,
        Company,
        cid,
        data.version,
        {
            "name": data.name,
            "name_key": data.name.casefold(),
            "company_type": data.company_type,
            "active": data.active,
        },
    )
    audit(db, u, "update", "companies", cid, {"active": data.active})
    commit(db)
    db.refresh(row)
    return {
        "id": row.id,
        "name": row.name,
        "company_type": row.company_type,
        "active": row.active,
        "version": row.version,
    }


@router.delete("/companies/{cid}")
def delete_company(cid: int, u: User = Depends(admin), db: Session = Depends(get_db)):
    row = db.get(Company, cid)
    if not row or row.organization_id != u.organization_id:
        raise HTTPException(404, "Company not found")
    name = row.name
    db.delete(row)
    audit(db, u, "delete", "companies", cid, {"name": name})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "This company is still used by users, projects or records. Deactivate it instead.",
        )
    return {"deleted": cid}


@router.put("/projects/{pid}/companies/{link_id}")
def edit_participant(
    pid: int,
    link_id: int,
    data: ParticipationUpdate,
    u: User = Depends(admin),
    db: Session = Depends(get_db),
):
    project(db, u, pid)
    link = db.get(ProjectCompany, link_id)
    if not link or link.project_id != pid:
        raise HTTPException(404, "Participant not found")
    if not data.active and link.active:
        reason = company_blocked(db, pid, link.company_id)
        if reason:
            raise HTTPException(409, reason)
    _bump(
        db,
        ProjectCompany,
        link.id,
        data.version,
        {"participation_type": data.participation_type, "active": data.active},
    )
    audit(
        db,
        u,
        "update",
        "project_companies",
        link.id,
        {"active": data.active},
        project_id=pid,
    )
    commit(db)
    db.refresh(link)
    return {"id": link.id, "active": link.active, "version": link.version}


@router.put("/projects/{pid}/areas/{aid}")
def edit_area(
    pid: int,
    aid: int,
    data: AreaUpdate,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = project(db, u, pid)
    permitted(db, u, found, "projects.manage_areas")
    area = db.get(Area, aid)
    if not area or area.project_id != pid:
        raise HTTPException(404, "Location not found")
    if not data.active and area.active:
        if db.query(Area).filter_by(parent_id=area.id, active=True).first():
            raise HTTPException(409, "Deactivate child locations first")
        if db.query(Drawing).filter_by(project_id=pid, area_id=area.id).first():
            raise HTTPException(409, "This location is used by drawings")
    _bump(
        db,
        Area,
        area.id,
        data.version,
        {
            "code": data.code,
            "code_key": data.code.casefold(),
            "name": data.name,
            "description": data.description,
            "active": data.active,
        },
    )
    audit(db, u, "update", "areas", area.id, {"active": data.active}, project_id=pid)
    commit(db)
    db.refresh(area)
    return {"id": area.id, "active": area.active, "version": area.version}


@router.post("/projects/{pid}/transitions")
def transition(
    pid: int,
    data: TransitionIn,
    u: User = Depends(admin),
    db: Session = Depends(get_db),
):
    found = project(db, u, pid)
    if data.target == "Active":
        raise HTTPException(409, "Activation requires an approved review")
    apply_transition(db, u, found, data.target, data.reason, data.version)
    commit(db)
    return project_dict(db, found)


@router.get("/projects/{pid}/files")
def files(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = project(db, u, pid)
    permitted(db, u, found, "projects.view")
    commercial = holds(db, u, found, "projects.commercial.view")
    rows = db.query(ProjectFile).filter_by(project_id=pid).order_by(ProjectFile.id.desc())
    result = []
    for link in rows:
        if link.category == "Contract/PO" and not commercial:
            continue
        stored = db.get(StoredFile, link.file_id)
        actor = db.get(User, link.uploaded_by)
        result.append(
            {
                "id": link.id,
                "title": link.title or stored.original_name,
                "description": link.description or "",
                "category": link.category,
                "active": link.active,
                "name": stored.original_name,
                "content_type": stored.content_type,
                "size": stored.size,
                "sha256": stored.sha256,
                "uploaded_by": actor.name if actor else "",
                "created_at": link.created_at,
            }
        )
    return result


def _document_permission(db, user, found, ordinary):
    if user.organization_admin:
        return
    try:
        permitted(db, user, found, ordinary)
    except HTTPException:
        permitted(db, user, found, "projects.edit")


@router.post("/projects/{pid}/files", status_code=201)
async def upload(
    pid: int,
    category: str = Form(),
    title: str = Form(""),
    description: str = Form(""),
    upload: UploadFile = File(),
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = project(db, u, pid)
    label = category.strip()
    if label not in FILE_CATEGORIES:
        raise HTTPException(422, "Choose a document category from the list")
    if label == "Contract/PO":
        permitted(db, u, found, "projects.commercial.edit")
    else:
        _document_permission(db, u, found, "projects.documents.upload")
    stored = store_file(
        db,
        u,
        upload.filename or "file",
        upload.content_type or "",
        await upload.read(),
    )
    link = ProjectFile(
        project_id=pid,
        file_id=stored.id,
        category=label,
        title=(title or stored.original_name).strip()[:200],
        description=description.strip(),
        uploaded_by=u.id,
    )
    db.add(link)
    db.flush()
    audit(db, u, "upload", "project_files", link.id, {"name": stored.original_name}, project_id=pid)
    commit(db)
    return {"id": link.id}


@router.get("/projects/{pid}/files/{fid}")
def download(
    pid: int, fid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    found = project(db, u, pid)
    permitted(db, u, found, "projects.view")
    link = db.get(ProjectFile, fid)
    if not link or link.project_id != pid or not link.active:
        raise HTTPException(404, "File not found")
    if link.category == "Contract/PO":
        permitted(db, u, found, "projects.commercial.view")
    stored = db.get(StoredFile, link.file_id)
    if stored.organization_id != u.organization_id:
        raise HTTPException(404, "File not found")
    audit(db, u, "download", "project_files", link.id, project_id=pid)
    commit(db)
    filename = stored.original_name.replace('"', "").replace("\r", "").replace("\n", "")
    return Response(
        content=read_file(stored),
        media_type=stored.content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/projects/{pid}/files/{fid}")
def remove_file(
    pid: int, fid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    found = project(db, u, pid)
    link = db.get(ProjectFile, fid)
    if not link or link.project_id != pid:
        raise HTTPException(404, "File not found")
    if link.category == "Contract/PO":
        permitted(db, u, found, "projects.commercial.edit")
    else:
        _document_permission(db, u, found, "projects.documents.delete")
    link.active = False
    audit(db, u, "remove", "project_files", link.id, project_id=pid)
    commit(db)
    return {"ok": True}


@router.get("/projects/{pid}/history")
def history(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = project(db, u, pid)
    permitted(db, u, found, "projects.view")
    audits = (
        db.query(Audit)
        .filter_by(organization_id=u.organization_id, project_id=pid)
        .order_by(Audit.id.desc())
        .limit(100)
        .all()
    )
    reviews = db.query(ReviewInstance).filter_by(project_id=pid).all()
    decisions = []
    for review in reviews:
        for row in db.query(ReviewDecision).filter_by(instance_id=review.id):
            decisions.append(
                {
                    "action": row.action,
                    "reason": row.reason,
                    "reviewer_id": row.reviewer_id,
                    "attempt": row.attempt,
                    "reviewed_revision": row.reviewed_revision,
                    "created_at": row.created_at,
                }
            )
    commercial = holds(db, u, found, "projects.commercial.view")

    def visible(details):
        if commercial or not isinstance(details, dict):
            return details
        cleaned = {}
        for key, value in details.items():
            if key in {"contract_number", "contract_date", "contract_value", "currency"}:
                continue
            if isinstance(value, dict):
                cleaned[key] = {
                    inner: item
                    for inner, item in value.items()
                    if inner
                    not in {"contract_number", "contract_date", "contract_value", "currency"}
                }
            else:
                cleaned[key] = value
        return cleaned

    return {
        "audits": [
            {
                "id": row.id,
                "action": row.action,
                "resource": row.resource,
                "actor_id": row.actor_id,
                "actor": (db.get(User, row.actor_id).name if db.get(User, row.actor_id) else ""),
                "created_at": row.created_at,
                "details": visible(row.details),
            }
            for row in audits
        ],
        "decisions": decisions,
    }
