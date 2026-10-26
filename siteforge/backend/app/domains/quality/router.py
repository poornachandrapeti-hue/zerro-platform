from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.identity_projects.models import Audit, Project, User
from app.domains.identity_projects.security import authenticated, holds, permitted

from . import competence, dashboard, dossiers, findings, material, plans, requests, service
from .models import (
    Calibration,
    Concession,
    ConstructionRequest,
    MaterialInspection,
    Nonconformance,
    Qualification,
    QualityDocument,
    QualityForm,
    QualityDossier,
    QualityHold,
    QualityOffer,
    QualityPunch,
)
from .schemas import (
    CancelIn,
    CheckpointsIn,
    ClosureIn,
    ConcessionIn,
    DossierIn,
    DocumentIn,
    DocumentUpdate,
    FormIn,
    FormUpdate,
    HoldIn,
    MaterialIn,
    MaterialUpdate,
    NcrIn,
    NcrUpdate,
    OfferIn,
    PunchIn,
    CalibrationIn,
    QualificationIn,
    ReleaseIn,
    RequestIn,
    RequestUpdate,
    ReviseIn,
    VersionIn,
    WithdrawIn,
)

router = APIRouter(prefix="/api")


def _commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Duplicate value or invalid record reference")


def _audit(db, user, action, resource, rid, project_id, details=None):
    db.add(
        Audit(
            organization_id=user.organization_id,
            actor_id=user.id,
            action=action,
            resource=resource,
            resource_id=rid,
            details=details or {},
            project_id=project_id,
        )
    )


def _project(db, user, pid):
    project = db.get(Project, pid)
    if not project or project.organization_id != user.organization_id:
        raise HTTPException(404, "Project not found")
    return project


def _view(db, user, project):
    permitted(db, user, project, "quality.view")


def _edit(db, user, project):
    permitted(db, user, project, "quality.edit")


def _plan(db, user, project):
    permitted(db, user, project, "quality.plan")


def _request(db, user, project):
    if holds(db, user, project, "quality.edit") or holds(db, user, project, "quality.plan"):
        return
    permitted(db, user, project, "quality.edit")


def _either(db, user, project):
    if holds(db, user, project, "quality.edit") or holds(db, user, project, "quality.plan"):
        return
    permitted(db, user, project, "quality.plan")


@router.get("/projects/{pid}/quality")
def quality_board(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return service.board(db, u, found)


@router.post("/projects/{pid}/quality/offers", status_code=201)
def create_offer(pid: int, data: OfferIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = service.add_offer(db, u, found, data)
    _audit(db, u, "create", "quality_offers", row.id, pid, {"number": row.number})
    _commit(db)
    return service.offer_view(db, u, found, row)


@router.post("/projects/{pid}/quality/offers/{offer_id}/submit")
def submit_offer(
    pid: int,
    offer_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(QualityOffer, offer_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Inspection offer not found")
    instance = service.submit_offer(db, u, found, row, data.version)
    _audit(db, u, "submit", "quality_offers", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return service.offer_view(db, u, found, row)


@router.post("/projects/{pid}/quality/offers/{offer_id}/resubmit")
def resubmit_offer(
    pid: int,
    offer_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(QualityOffer, offer_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Inspection offer not found")
    if row.version != data.version:
        raise HTTPException(409, "This inspection offer changed. Reload it and try again")
    instance = service._latest_review(db, found, row)
    if not instance or instance.state != "Returned":
        raise HTTPException(409, "Only a returned offer can be resubmitted")
    service.apply_resubmit(db, u, instance, instance.version)
    _audit(db, u, "resubmit", "quality_offers", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return service.offer_view(db, u, found, row)


@router.post("/projects/{pid}/quality/offers/{offer_id}/cancel")
def cancel_offer(
    pid: int,
    offer_id: int,
    data: CancelIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(QualityOffer, offer_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Inspection offer not found")
    service.cancel_offer(db, u, row, data)
    _audit(db, u, "cancel", "quality_offers", row.id, pid, {"reason": data.reason})
    _commit(db)
    return service.offer_view(db, u, found, row)


@router.get("/projects/{pid}/quality/plans")
def quality_plans(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return plans.register(db, u, found)


@router.post("/projects/{pid}/quality/documents", status_code=201)
def create_document(pid: int, data: DocumentIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = plans.add_document(db, u, found, data)
    _audit(db, u, "create", "quality_documents", row.id, pid, {"number": row.number})
    _commit(db)
    return plans.document_view(db, u, found, row)


@router.put("/projects/{pid}/quality/documents/{document_id}")
def update_document(
    pid: int,
    document_id: int,
    data: DocumentUpdate,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(QualityDocument, document_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Quality document not found")
    plans.update_document(db, u, found, row, data)
    _audit(db, u, "update", "quality_documents", row.id, pid, {"number": row.number})
    _commit(db)
    return plans.document_view(db, u, found, row)


@router.put("/projects/{pid}/quality/documents/{document_id}/checkpoints")
def update_checkpoints(
    pid: int,
    document_id: int,
    data: CheckpointsIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(QualityDocument, document_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Quality document not found")
    plans.save_checkpoints(db, u, found, row, data)
    _audit(db, u, "update", "quality_checkpoints", row.id, pid, {"count": len(data.checkpoints)})
    _commit(db)
    return plans.document_view(db, u, found, row)


@router.post("/projects/{pid}/quality/documents/{document_id}/submit")
def submit_document(
    pid: int,
    document_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(QualityDocument, document_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Quality document not found")
    instance = plans.submit_document(db, u, found, row, data.version)
    _audit(db, u, "submit", "quality_documents", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return plans.document_view(db, u, found, row)


@router.post("/projects/{pid}/quality/documents/{document_id}/resubmit")
def resubmit_document(
    pid: int,
    document_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(QualityDocument, document_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Quality document not found")
    if row.version != data.version:
        raise HTTPException(409, "This quality record changed. Reload it and try again")
    instance = plans._latest_review(db, found, plans.DOCUMENT, row.id)
    if not instance or instance.state != "Returned":
        raise HTTPException(409, "Only a returned quality document can be resubmitted")
    plans.apply_resubmit(db, u, instance, instance.version)
    _audit(db, u, "resubmit", "quality_documents", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return plans.document_view(db, u, found, row)


@router.post("/projects/{pid}/quality/documents/{document_id}/revise", status_code=201)
def revise_document(
    pid: int,
    document_id: int,
    data: ReviseIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(QualityDocument, document_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Quality document not found")
    copy = plans.revise_document(db, u, found, row, data)
    _audit(db, u, "revise", "quality_documents", copy.id, pid, {"number": copy.number, "revision": copy.revision_label})
    _commit(db)
    return plans.document_view(db, u, found, copy)


@router.post("/projects/{pid}/quality/documents/{document_id}/cancel")
def cancel_document(
    pid: int,
    document_id: int,
    data: CancelIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(QualityDocument, document_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Quality document not found")
    plans.cancel_document(db, u, row, data)
    _audit(db, u, "cancel", "quality_documents", row.id, pid, {"reason": data.reason})
    _commit(db)
    return plans.document_view(db, u, found, row)


@router.post("/projects/{pid}/quality/forms", status_code=201)
def create_form(pid: int, data: FormIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = plans.add_form(db, u, found, data)
    _audit(db, u, "create", "quality_forms", row.id, pid, {"code": row.code})
    _commit(db)
    return plans.form_view(db, u, found, row)


@router.put("/projects/{pid}/quality/forms/{form_id}")
def update_form(
    pid: int,
    form_id: int,
    data: FormUpdate,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(QualityForm, form_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Inspection template not found")
    plans.update_form(db, u, found, row, data)
    _audit(db, u, "update", "quality_forms", row.id, pid, {"code": row.code})
    _commit(db)
    return plans.form_view(db, u, found, row)


@router.post("/projects/{pid}/quality/forms/{form_id}/submit")
def submit_form(
    pid: int,
    form_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(QualityForm, form_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Inspection template not found")
    instance = plans.submit_form(db, u, found, row, data.version)
    _audit(db, u, "submit", "quality_forms", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return plans.form_view(db, u, found, row)


@router.post("/projects/{pid}/quality/forms/{form_id}/resubmit")
def resubmit_form(
    pid: int,
    form_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(QualityForm, form_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Inspection template not found")
    if row.version != data.version:
        raise HTTPException(409, "This quality record changed. Reload it and try again")
    instance = plans._latest_review(db, found, plans.FORM, row.id)
    if not instance or instance.state != "Returned":
        raise HTTPException(409, "Only a returned template can be resubmitted")
    plans.apply_resubmit(db, u, instance, instance.version)
    _audit(db, u, "resubmit", "quality_forms", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return plans.form_view(db, u, found, row)


@router.post("/projects/{pid}/quality/forms/{form_id}/revise", status_code=201)
def revise_form(
    pid: int,
    form_id: int,
    data: ReviseIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(QualityForm, form_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Inspection template not found")
    copy = plans.revise_form(db, u, found, row, data)
    _audit(db, u, "revise", "quality_forms", copy.id, pid, {"code": copy.code, "revision": copy.revision_label})
    _commit(db)
    return plans.form_view(db, u, found, copy)


@router.post("/projects/{pid}/quality/forms/{form_id}/cancel")
def cancel_form(
    pid: int,
    form_id: int,
    data: CancelIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(QualityForm, form_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Inspection template not found")
    plans.cancel_form(db, u, row, data)
    _audit(db, u, "cancel", "quality_forms", row.id, pid, {"reason": data.reason})
    _commit(db)
    return plans.form_view(db, u, found, row)


@router.get("/projects/{pid}/quality/materials")
def material_board(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return material.register(db, u, found)


@router.post("/projects/{pid}/quality/materials", status_code=201)
def create_material(pid: int, data: MaterialIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = material.add_inspection(db, u, found, data)
    _audit(db, u, "create", "quality_material_inspections", row.id, pid, {"number": row.number})
    _commit(db)
    return material.inspection_view(db, u, found, row)


@router.put("/projects/{pid}/quality/materials/{inspection_id}")
def update_material(
    pid: int,
    inspection_id: int,
    data: MaterialUpdate,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(MaterialInspection, inspection_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Material inspection not found")
    material.update_inspection(db, u, found, row, data)
    _audit(db, u, "update", "quality_material_inspections", row.id, pid, {"number": row.number})
    _commit(db)
    return material.inspection_view(db, u, found, row)


@router.post("/projects/{pid}/quality/materials/{inspection_id}/submit")
def submit_material(
    pid: int,
    inspection_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(MaterialInspection, inspection_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Material inspection not found")
    instance = material.submit_inspection(db, u, found, row, data.version)
    _audit(db, u, "submit", "quality_material_inspections", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return material.inspection_view(db, u, found, row)


@router.post("/projects/{pid}/quality/materials/{inspection_id}/resubmit")
def resubmit_material(
    pid: int,
    inspection_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(MaterialInspection, inspection_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Material inspection not found")
    if row.version != data.version:
        raise HTTPException(409, "This material inspection changed. Reload it and try again")
    instance = material._latest_review(db, found, row)
    if not instance or instance.state != "Returned":
        raise HTTPException(409, "Only a returned inspection can be resubmitted")
    material.apply_resubmit(db, u, instance, instance.version)
    _audit(db, u, "resubmit", "quality_material_inspections", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return material.inspection_view(db, u, found, row)


@router.post("/projects/{pid}/quality/materials/{inspection_id}/cancel")
def cancel_material(
    pid: int,
    inspection_id: int,
    data: CancelIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(MaterialInspection, inspection_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Material inspection not found")
    material.cancel_inspection(db, u, row, data)
    _audit(db, u, "cancel", "quality_material_inspections", row.id, pid, {"reason": data.reason})
    _commit(db)
    return material.inspection_view(db, u, found, row)


@router.get("/projects/{pid}/quality/requests")
def construction_board(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return requests.register(db, u, found)


@router.post("/projects/{pid}/quality/requests", status_code=201)
def create_request(pid: int, data: RequestIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _request(db, u, found)
    row = requests.add_request(db, u, found, data)
    _audit(db, u, "create", "quality_construction_requests", row.id, pid, {"number": row.number})
    _commit(db)
    return requests.request_view(db, u, found, row)


@router.put("/projects/{pid}/quality/requests/{request_id}")
def update_request(
    pid: int,
    request_id: int,
    data: RequestUpdate,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _request(db, u, found)
    row = db.get(ConstructionRequest, request_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Inspection request not found")
    requests.update_request(db, u, found, row, data)
    _audit(db, u, "update", "quality_construction_requests", row.id, pid, {"number": row.number})
    _commit(db)
    return requests.request_view(db, u, found, row)


@router.post("/projects/{pid}/quality/requests/{request_id}/submit")
def submit_construction_request(
    pid: int,
    request_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _request(db, u, found)
    row = db.get(ConstructionRequest, request_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Inspection request not found")
    instance = requests.submit_request(db, u, found, row, data.version)
    _audit(db, u, "submit", "quality_construction_requests", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return requests.request_view(db, u, found, row)


@router.post("/projects/{pid}/quality/requests/{request_id}/resubmit")
def resubmit_construction_request(
    pid: int,
    request_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _request(db, u, found)
    row = db.get(ConstructionRequest, request_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Inspection request not found")
    if row.version != data.version:
        raise HTTPException(409, "This inspection request changed. Reload it and try again")
    instance = requests._latest_review(db, found, row)
    if not instance or instance.state != "Returned":
        raise HTTPException(409, "Only a returned request can be resubmitted")
    requests.apply_resubmit(db, u, instance, instance.version)
    _audit(db, u, "resubmit", "quality_construction_requests", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return requests.request_view(db, u, found, row)


@router.post("/projects/{pid}/quality/requests/{request_id}/cancel")
def cancel_construction_request(
    pid: int,
    request_id: int,
    data: CancelIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _request(db, u, found)
    row = db.get(ConstructionRequest, request_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Inspection request not found")
    requests.cancel_request(db, u, row, data)
    _audit(db, u, "cancel", "quality_construction_requests", row.id, pid, {"reason": data.reason})
    _commit(db)
    return requests.request_view(db, u, found, row)


@router.get("/projects/{pid}/quality/ncrs")
def ncr_board(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return findings.ncr_register(db, u, found)


@router.post("/projects/{pid}/quality/ncrs", status_code=201)
def create_ncr(pid: int, data: NcrIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = findings.add_ncr(db, u, found, data)
    _audit(db, u, "create", "quality_ncrs", row.id, pid, {"number": row.number})
    _commit(db)
    return findings.ncr_view(db, u, found, row)


@router.put("/projects/{pid}/quality/ncrs/{ncr_id}")
def update_ncr(pid: int, ncr_id: int, data: NcrUpdate, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(Nonconformance, ncr_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "NCR not found")
    findings.update_ncr(db, u, found, row, data)
    _audit(db, u, "update", "quality_ncrs", row.id, pid, {"number": row.number})
    _commit(db)
    return findings.ncr_view(db, u, found, row)


@router.post("/projects/{pid}/quality/ncrs/{ncr_id}/submit")
def submit_ncr(pid: int, ncr_id: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(Nonconformance, ncr_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "NCR not found")
    instance = findings.submit_ncr(db, u, found, row, data.version)
    _audit(db, u, "submit", "quality_ncrs", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return findings.ncr_view(db, u, found, row)


@router.post("/projects/{pid}/quality/ncrs/{ncr_id}/close")
def close_ncr(pid: int, ncr_id: int, data: ClosureIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = db.get(Nonconformance, ncr_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "NCR not found")
    instance = findings.submit_closure(db, u, found, row, data)
    _audit(db, u, "submit", "quality_ncrs", row.id, pid, {"review_id": instance.id if instance else None})
    _commit(db)
    return findings.ncr_view(db, u, found, row)


@router.post("/projects/{pid}/quality/ncrs/{ncr_id}/cancel")
def cancel_ncr(pid: int, ncr_id: int, data: CancelIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(Nonconformance, ncr_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "NCR not found")
    findings.cancel_ncr(db, u, row, data)
    _audit(db, u, "cancel", "quality_ncrs", row.id, pid, {"reason": data.reason})
    _commit(db)
    return findings.ncr_view(db, u, found, row)


@router.post("/projects/{pid}/quality/concessions", status_code=201)
def create_concession(pid: int, data: ConcessionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = findings.add_concession(db, u, found, data)
    _audit(db, u, "create", "quality_concessions", row.id, pid, {"number": row.number})
    _commit(db)
    return findings.concession_view(db, u, found, row)


@router.post("/projects/{pid}/quality/concessions/{concession_id}/submit")
def submit_concession(
    pid: int,
    concession_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = db.get(Concession, concession_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Concession not found")
    instance = findings.submit_concession(db, u, found, row, data.version)
    _audit(db, u, "submit", "quality_concessions", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return findings.concession_view(db, u, found, row)


@router.get("/projects/{pid}/quality/holds")
def hold_board(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return findings.hold_register(db, u, found)


@router.post("/projects/{pid}/quality/holds", status_code=201)
def create_hold(pid: int, data: HoldIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = findings.add_hold(db, u, found, data)
    _audit(db, u, "create", "quality_holds", row.id, pid, {"number": row.number})
    _commit(db)
    return findings.hold_view(db, u, found, row)


@router.post("/projects/{pid}/quality/holds/{hold_id}/release")
def release_hold(
    pid: int,
    hold_id: int,
    data: ReleaseIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = db.get(QualityHold, hold_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Quality hold not found")
    instance = findings.submit_release(db, u, found, row, data)
    _audit(db, u, "submit", "quality_holds", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return findings.hold_view(db, u, found, row)


@router.get("/projects/{pid}/quality/dashboard")
def quality_dashboard(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    dashboard.raise_alerts(db, found)
    _commit(db)
    return dashboard.board(db, found)


@router.get("/projects/{pid}/quality/qualifications")
def qualification_board(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return competence.qualification_register(db, u, found)


@router.post("/projects/{pid}/quality/qualifications", status_code=201)
def create_qualification(
    pid: int, data: QualificationIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = competence.add_qualification(db, u, found, data)
    _audit(db, u, "create", "quality_qualifications", row.id, pid, {"number": row.number})
    _commit(db)
    return competence.qualification_view(db, u, found, row)


@router.post("/projects/{pid}/quality/qualifications/{qualification_id}/submit")
def submit_qualification(
    pid: int,
    qualification_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(Qualification, qualification_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Qualification not found")
    instance = competence.submit_qualification(db, u, found, row, data.version)
    _audit(db, u, "submit", "quality_qualifications", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return competence.qualification_view(db, u, found, row)


@router.post("/projects/{pid}/quality/qualifications/{qualification_id}/withdraw")
def withdraw_qualification(
    pid: int,
    qualification_id: int,
    data: WithdrawIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(Qualification, qualification_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Qualification not found")
    competence.withdraw(db, u, Qualification, row, data)
    _audit(db, u, "withdraw", "quality_qualifications", row.id, pid, {"reason": data.reason})
    _commit(db)
    return competence.qualification_view(db, u, found, row)


@router.get("/projects/{pid}/quality/calibrations")
def calibration_board(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return competence.calibration_register(db, u, found)


@router.post("/projects/{pid}/quality/calibrations", status_code=201)
def create_calibration(
    pid: int, data: CalibrationIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = competence.add_calibration(db, u, found, data)
    _audit(db, u, "create", "quality_calibrations", row.id, pid, {"number": row.number})
    _commit(db)
    return competence.calibration_view(db, u, found, row)


@router.post("/projects/{pid}/quality/calibrations/{calibration_id}/submit")
def submit_calibration(
    pid: int,
    calibration_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(Calibration, calibration_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Calibration not found")
    instance = competence.submit_calibration(db, u, found, row, data.version)
    _audit(db, u, "submit", "quality_calibrations", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return competence.calibration_view(db, u, found, row)


@router.post("/projects/{pid}/quality/calibrations/{calibration_id}/withdraw")
def withdraw_calibration(
    pid: int,
    calibration_id: int,
    data: WithdrawIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(Calibration, calibration_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Calibration not found")
    competence.withdraw(db, u, Calibration, row, data)
    _audit(db, u, "withdraw", "quality_calibrations", row.id, pid, {"reason": data.reason})
    _commit(db)
    return competence.calibration_view(db, u, found, row)


def _resubmit_competence(db, user, project, row, version, record_type):
    if row.version != version:
        raise HTTPException(409, "This record changed. Reload it and try again")
    instance = competence._latest(db, project, record_type, row.id)
    if not instance or instance.state != "Returned":
        raise HTTPException(409, "Only a returned record can be resubmitted")
    competence.apply_resubmit(db, user, instance, instance.version)


@router.post("/projects/{pid}/quality/qualifications/{qualification_id}/resubmit")
def resubmit_qualification(
    pid: int,
    qualification_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(Qualification, qualification_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Qualification not found")
    _resubmit_competence(db, u, found, row, data.version, competence.QUALIFICATION)
    _audit(db, u, "resubmit", "quality_qualifications", row.id, pid, {})
    _commit(db)
    return competence.qualification_view(db, u, found, row)


@router.post("/projects/{pid}/quality/calibrations/{calibration_id}/resubmit")
def resubmit_calibration(
    pid: int,
    calibration_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(Calibration, calibration_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Calibration not found")
    _resubmit_competence(db, u, found, row, data.version, competence.CALIBRATION)
    _audit(db, u, "resubmit", "quality_calibrations", row.id, pid, {})
    _commit(db)
    return competence.calibration_view(db, u, found, row)


@router.get("/projects/{pid}/quality/dossiers")
def dossier_board(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return dossiers.register(db, u, found)


@router.post("/projects/{pid}/quality/dossiers", status_code=201)
def create_dossier(pid: int, data: DossierIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = dossiers.add_dossier(db, u, found, data)
    _audit(db, u, "create", "quality_dossiers", row.id, pid, {"number": row.number})
    _commit(db)
    return dossiers.dossier_view(db, u, found, row)


@router.post("/projects/{pid}/quality/dossiers/{dossier_id}/submit")
def submit_dossier(
    pid: int, dossier_id: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(QualityDossier, dossier_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Quality dossier not found")
    instance = dossiers.submit_dossier(db, u, found, row, data.version)
    _audit(db, u, "submit", "quality_dossiers", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return dossiers.dossier_view(db, u, found, row)


@router.post("/projects/{pid}/quality/dossiers/{dossier_id}/resubmit")
def resubmit_dossier(
    pid: int, dossier_id: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(QualityDossier, dossier_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Quality dossier not found")
    if row.version != data.version:
        raise HTTPException(409, "This record changed. Reload it and try again")
    instance = dossiers._latest(db, found, dossiers.DOSSIER, row.id)
    if not instance or instance.state != "Returned":
        raise HTTPException(409, "Only a returned dossier can be resubmitted")
    dossiers.apply_resubmit(db, u, instance, instance.version)
    _audit(db, u, "resubmit", "quality_dossiers", row.id, pid, {})
    _commit(db)
    return dossiers.dossier_view(db, u, found, row)


@router.get("/projects/{pid}/quality/eligibility")
def quality_eligibility(
    pid: int, package_id: int, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    found = _project(db, u, pid)
    _view(db, u, found)
    package = dossiers._package(db, found, package_id)
    return dossiers.eligibility(db, found, package)


@router.post("/projects/{pid}/quality/punches", status_code=201)
def create_punch(pid: int, data: PunchIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = dossiers.add_punch(db, u, found, data)
    _audit(db, u, "create", "quality_punches", row.id, pid, {"number": row.number})
    _commit(db)
    return dossiers.punch_view(db, u, found, row)


@router.post("/projects/{pid}/quality/punches/{punch_id}/close")
def close_punch(
    pid: int, punch_id: int, data: ClosureIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = db.get(QualityPunch, punch_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Punch item not found")
    instance = dossiers.submit_punch_closure(db, u, found, row, data)
    _audit(db, u, "submit", "quality_punches", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return dossiers.punch_view(db, u, found, row)


@router.post("/projects/{pid}/quality/punches/{punch_id}/resubmit")
def resubmit_punch(
    pid: int, punch_id: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = db.get(QualityPunch, punch_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Punch item not found")
    if row.version != data.version:
        raise HTTPException(409, "This record changed. Reload it and try again")
    instance = dossiers._latest(db, found, dossiers.PUNCH_CLOSE, row.id)
    if not instance or instance.state != "Returned":
        raise HTTPException(409, "Only a returned punch closure can be resubmitted")
    dossiers.apply_resubmit(db, u, instance, instance.version)
    _audit(db, u, "resubmit", "quality_punches", row.id, pid, {})
    _commit(db)
    return dossiers.punch_view(db, u, found, row)
