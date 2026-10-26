from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.router import audit, commit, project
from app.domains.identity_projects.security import authenticated

from . import extraction, takeoff
from .schemas import ExtractIn, TakeoffLineIn, TakeoffReasonIn, TakeoffRequirementIn, TakeoffVersionIn
from .workflow import _drawing, _require, revision_file

router = APIRouter(prefix="/api")
SHEET = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _revision(db, user, pid, did, rid):
    found = project(db, user, pid)
    drawing = _drawing(db, user, found, did)
    revision = takeoff.revision_for(db, user, found, drawing, rid)
    return found, drawing, revision


def _load(db, user, pid, tid):
    found = project(db, user, pid)
    row, _drawing_row = takeoff.load(db, user, found, tid)
    return found, row


def _out(db, user, found, row):
    db.refresh(row)
    return takeoff.payload(db, user, found, row)


@router.get("/projects/{pid}/takeoff-setup")
def setup(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = project(db, u, pid)
    _require(db, u, found, "drawings.view")
    return {
        "ocr": extraction.ocr_status(),
        "supported": [
            "PDF with a text layer: tables with Description and Quantity columns are read",
            "Scanned PDF and PNG/JPG/TIFF images: only when an OCR/table provider is configured",
            "CSV or Excel material list import",
            "Manual entry",
        ],
        "unsupported": [
            "DWG, DXF and other CAD files",
            "Quantities shown only as drawn geometry, dimensions or scale",
            "Tables without a description and a quantity column",
        ],
    }


@router.get("/projects/{pid}/takeoffs")
def takeoffs(
    pid: int,
    drawing_id: int = 0,
    status: str = "",
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = project(db, u, pid)
    _require(db, u, found, "drawings.view")
    return takeoff.list_rows(db, u, found, drawing_id or None, status)


@router.post("/projects/{pid}/drawings/{did}/revisions/{rid}/takeoffs/extract")
def extract(
    pid: int,
    did: int,
    rid: int,
    data: ExtractIn,
    response: Response,
    background: BackgroundTasks,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found, drawing, revision = _revision(db, u, pid, did, rid)
    row, job = takeoff.start_extraction(db, u, found, drawing, revision, data.pages)
    if job is None:
        response.status_code = 200
        return takeoff.payload(db, u, found, row)
    audit(db, u, "extract", "material_takeoffs", row.id, {"pages": row.pages}, project_id=pid)
    commit(db)
    background.add_task(takeoff.run_extraction, db.get_bind(), job.id)
    response.status_code = 202
    return takeoff.payload(db, u, found, row)


@router.post("/projects/{pid}/drawings/{did}/revisions/{rid}/takeoffs/manual")
def manual(
    pid: int,
    did: int,
    rid: int,
    response: Response,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found, drawing, revision = _revision(db, u, pid, did, rid)
    row, created = takeoff.create_manual(db, u, found, drawing, revision)
    if created:
        audit(db, u, "create", "material_takeoffs", row.id, project_id=pid)
        commit(db)
    response.status_code = 201 if created else 200
    return _out(db, u, found, row)


@router.post("/projects/{pid}/drawings/{did}/revisions/{rid}/takeoffs/import")
async def import_list(
    pid: int,
    did: int,
    rid: int,
    response: Response,
    mode: str = "preview",
    upload: UploadFile = File(...),
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found, drawing, revision = _revision(db, u, pid, did, rid)
    row, preview = takeoff.import_list(db, u, found, drawing, revision, upload.filename, await upload.read(), mode)
    if row is None:
        return {"rows": preview, "takeoff": None}
    audit(db, u, "import", "material_takeoffs", row.id, {"lines": len(preview)}, project_id=pid)
    commit(db)
    response.status_code = 201
    return {"rows": preview, "takeoff": _out(db, u, found, row)}


@router.get("/projects/{pid}/takeoffs/{tid}")
def one(pid: int, tid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found, row = _load(db, u, pid, tid)
    return takeoff.payload(db, u, found, row)


@router.get("/projects/{pid}/takeoffs/{tid}/source")
def source(pid: int, tid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    from .models import DrawingRevision

    found, row = _load(db, u, pid, tid)
    stored, content = revision_file(db, db.get(DrawingRevision, row.revision_id))
    audit(db, u, "preview", "drawing_revisions", row.revision_id, project_id=pid)
    commit(db)
    filename = stored.original_name.replace('"', "")
    return Response(
        content=content,
        media_type=stored.content_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post("/projects/{pid}/takeoffs/{tid}/retry")
def retry(
    pid: int,
    tid: int,
    response: Response,
    background: BackgroundTasks,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found, row = _load(db, u, pid, tid)
    job = takeoff.retry(db, u, found, row)
    audit(db, u, "retry", "material_takeoffs", row.id, project_id=pid)
    commit(db)
    background.add_task(takeoff.run_extraction, db.get_bind(), job.id)
    response.status_code = 202
    return takeoff.payload(db, u, found, row)


@router.post("/projects/{pid}/takeoffs/{tid}/lines", status_code=201)
def add_line(
    pid: int, tid: int, data: TakeoffLineIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    found, row = _load(db, u, pid, tid)
    takeoff.add_line(db, u, found, row, data.model_dump(exclude_unset=True))
    audit(db, u, "add-line", "material_takeoffs", row.id, project_id=pid)
    commit(db)
    return _out(db, u, found, row)


@router.put("/projects/{pid}/takeoffs/{tid}/lines/{lid}")
def edit_line(
    pid: int,
    tid: int,
    lid: int,
    data: TakeoffLineIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found, row = _load(db, u, pid, tid)
    takeoff.edit_line(db, u, found, row, lid, data.model_dump(exclude_unset=True))
    audit(db, u, "correct-line", "material_takeoffs", row.id, {"line": lid}, project_id=pid)
    commit(db)
    return _out(db, u, found, row)


@router.post("/projects/{pid}/takeoffs/{tid}/lines/{lid}/delete")
def delete_line(
    pid: int,
    tid: int,
    lid: int,
    data: TakeoffReasonIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found, row = _load(db, u, pid, tid)
    takeoff.delete_line(db, u, found, row, lid, data.version, data.reason)
    audit(db, u, "delete-line", "material_takeoffs", row.id, {"line": lid}, project_id=pid)
    commit(db)
    return _out(db, u, found, row)


@router.post("/projects/{pid}/takeoffs/{tid}/submit")
def submit(pid: int, tid: int, data: TakeoffVersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found, row = _load(db, u, pid, tid)
    takeoff.submit(db, u, found, row, data.version)
    audit(db, u, "submit", "material_takeoffs", row.id, project_id=pid)
    commit(db)
    return _out(db, u, found, row)


@router.post("/projects/{pid}/takeoffs/{tid}/verify")
def verify(pid: int, tid: int, data: TakeoffVersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found, row = _load(db, u, pid, tid)
    takeoff.verify(db, u, found, row, data.version)
    audit(db, u, "verify", "material_takeoffs", row.id, project_id=pid)
    commit(db)
    return _out(db, u, found, row)


@router.post("/projects/{pid}/takeoffs/{tid}/return")
def return_for_correction(
    pid: int, tid: int, data: TakeoffReasonIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    found, row = _load(db, u, pid, tid)
    takeoff.return_for_correction(db, u, found, row, data.version, data.reason)
    audit(db, u, "return", "material_takeoffs", row.id, {"reason": data.reason}, project_id=pid)
    commit(db)
    return _out(db, u, found, row)


@router.post("/projects/{pid}/takeoffs/{tid}/cancel")
def cancel(pid: int, tid: int, data: TakeoffReasonIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found, row = _load(db, u, pid, tid)
    takeoff.cancel(db, u, found, row, data.version, data.reason)
    audit(db, u, "cancel", "material_takeoffs", row.id, {"reason": data.reason}, project_id=pid)
    commit(db)
    return _out(db, u, found, row)


@router.post("/projects/{pid}/takeoffs/{tid}/apply")
def apply_changes(
    pid: int, tid: int, data: TakeoffVersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    found, row = _load(db, u, pid, tid)
    takeoff.apply_changes(db, u, found, row, data.version)
    audit(db, u, "apply-revision", "material_takeoffs", row.id, project_id=pid)
    commit(db)
    return _out(db, u, found, row)


@router.post("/projects/{pid}/takeoffs/{tid}/requirement")
def requirement(
    pid: int,
    tid: int,
    data: TakeoffRequirementIn,
    response: Response,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    from app.domains.supply_chain.service import requirement_payload

    found, row = _load(db, u, pid, tid)
    created_row, created = takeoff.create_requirement(db, u, found, row, data)
    if created:
        audit(db, u, "create", "material_requirements", created_row.id, {"takeoff": row.id}, project_id=pid)
        commit(db)
        db.refresh(created_row)
    response.status_code = 201 if created else 200
    return {"created": created, "requirement": requirement_payload(db, u, found, created_row)}


@router.get("/projects/{pid}/takeoffs/{tid}/export")
def export(
    pid: int,
    tid: int,
    view: str = Query("reviewed", pattern="^(reviewed|original)$"),
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found, row = _load(db, u, pid, tid)
    content = takeoff.export(db, u, found, row, view, format)
    audit(db, u, "export", "material_takeoffs", row.id, {"view": view, "format": format}, project_id=pid)
    commit(db)
    name = f"{row.number}-{view}.{format}".replace('"', "")
    return Response(
        content=content,
        media_type=SHEET if format == "xlsx" else "text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
