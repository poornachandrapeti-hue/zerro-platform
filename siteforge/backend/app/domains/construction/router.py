from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.identity_projects.models import Audit, Project, User
from app.domains.identity_projects.security import authenticated, permitted

from . import connections, handover, impact, monitoring, progress, readiness, service
from .models import (
    CompletionDossier,
    ConstructionActivity,
    ConstructionBlocker,
    ConstructionItem,
    ConstructionTemplate,
    ProgressLabour,
    ProgressLine,
    ProgressReport,
    ReadinessCheck,
    WorkHold,
    WorkPackage,
)
from .schemas import (
    ActivityIn,
    ActivityUpdateIn,
    CancelIn,
    ItemIn,
    ItemUpdateIn,
    LabourIn,
    PackageIn,
    PackageUpdateIn,
    ReadinessIn,
    ReadinessUpdateIn,
    BlockerIn,
    BlockerResolveIn,
    DossierIn,
    HoldIn,
    ImpactIn,
    ReleaseIn,
    LineIn,
    MilestonesIn,
    ReportIn,
    ReportUpdateIn,
    TemplateIn,
    TemplateUpdateIn,
    VersionIn,
)

router = APIRouter(prefix="/api")


def _project(db, user, pid):
    found = db.get(Project, pid)
    if not found or found.organization_id != user.organization_id:
        raise HTTPException(404, "Project not found")
    return found


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


def _view(db, user, project):
    permitted(db, user, project, "construction.view")


def _edit(db, user, project):
    permitted(db, user, project, "construction.edit")


@router.get("/projects/{pid}/construction/summary")
def construction_summary(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return service.summary(db, found)


@router.get("/projects/{pid}/construction/sources")
def construction_sources(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return service.sources(db, found)


@router.get("/projects/{pid}/construction/templates")
def construction_templates(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return service.list_templates(db, found)


@router.post("/projects/{pid}/construction/templates", status_code=201)
def create_template(
    pid: int, data: TemplateIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = service._save_template(db, u, found, data)
    _audit(db, u, "create", "construction_templates", row.id, pid, {"code": row.code})
    _commit(db)
    return service._template_row(db, row)


@router.post("/projects/{pid}/construction/templates/examples", status_code=201)
def create_examples(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _edit(db, u, found)
    added = service.add_examples(db, u, found)
    _audit(db, u, "create", "construction_templates", found.id, pid, {"added": added})
    _commit(db)
    return {"added": added, "templates": service.list_templates(db, found)}


@router.put("/projects/{pid}/construction/templates/{tid}")
def update_template(
    pid: int,
    tid: int,
    data: TemplateUpdateIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(ConstructionTemplate, tid)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Template not found")
    service._save_template(db, u, found, data, row)
    _audit(db, u, "update", "construction_templates", row.id, pid, {"code": data.code})
    _commit(db)
    return service._template_row(db, row)


@router.get("/projects/{pid}/construction/packages")
def construction_packages(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return service.list_packages(db, found)


@router.post("/projects/{pid}/construction/packages", status_code=201)
def create_package(
    pid: int, data: PackageIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = service.add_package(db, u, found, data)
    _audit(db, u, "create", "work_packages", row.id, pid, {"code": row.code})
    _commit(db)
    return service._package_row(db, row)


@router.put("/projects/{pid}/construction/packages/{package_id}")
def update_package(
    pid: int,
    package_id: int,
    data: PackageUpdateIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(WorkPackage, package_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Work package not found")
    service.save_package(db, u, found, row, data)
    _audit(db, u, "update", "work_packages", row.id, pid, {"code": data.code})
    _commit(db)
    return service._package_row(db, row)


@router.post("/projects/{pid}/construction/packages/{package_id}/cancel")
def cancel_package(
    pid: int,
    package_id: int,
    data: CancelIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(WorkPackage, package_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Work package not found")
    service.cancel_package(db, u, row, data)
    _audit(db, u, "cancel", "work_packages", row.id, pid, {"reason": data.reason})
    _commit(db)
    return service._package_row(db, row)


def _package(db, pid, package_id):
    row = db.get(WorkPackage, package_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Work package not found")
    return row


@router.get("/projects/{pid}/construction/readiness")
def readiness_board(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return readiness.board(db, u, found)


@router.post("/projects/{pid}/construction/packages/{package_id}/checks", status_code=201)
def add_readiness(
    pid: int,
    package_id: int,
    data: ReadinessIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    package = _package(db, pid, package_id)
    row = readiness.add_check(db, u, found, package, data)
    _audit(db, u, "create", "construction_readiness", row.id, pid, {"check_type": row.check_type})
    _commit(db)
    return readiness.package_view(db, u, found, package)


@router.put("/projects/{pid}/construction/packages/{package_id}/checks/{check_id}")
def update_readiness(
    pid: int,
    package_id: int,
    check_id: int,
    data: ReadinessUpdateIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    package = _package(db, pid, package_id)
    row = db.get(ReadinessCheck, check_id)
    if not row or row.package_id != package.id:
        raise HTTPException(404, "Readiness check not found")
    readiness.update_check(db, u, found, package, row, data)
    _audit(db, u, "update", "construction_readiness", row.id, pid, {"status": data.status})
    _commit(db)
    return readiness.package_view(db, u, found, package)


@router.post("/projects/{pid}/construction/packages/{package_id}/release")
def release_package(
    pid: int,
    package_id: int,
    data: ReleaseIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    package = _package(db, pid, package_id)
    instance, warnings = readiness.submit_release(db, u, found, package, data.version)
    _audit(db, u, "submit", "work_packages", package.id, pid, {"review_id": instance.id})
    _commit(db)
    view = readiness.package_view(db, u, found, package)
    view["warnings"] = warnings
    return view


@router.post("/projects/{pid}/construction/packages/{package_id}/resubmit")
def resubmit_package(
    pid: int,
    package_id: int,
    data: ReleaseIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    package = _package(db, pid, package_id)
    if package.version != data.version:
        raise HTTPException(409, "This work package changed. Reload it and try again")
    instance = readiness._latest_review(db, found, package)
    if not instance or instance.state != "Returned":
        raise HTTPException(409, "Only a returned release can be resubmitted")
    readiness.apply_resubmit(db, u, instance, instance.version)
    _audit(db, u, "resubmit", "work_packages", package.id, pid, {"review_id": instance.id})
    _commit(db)
    return readiness.package_view(db, u, found, package)


@router.post("/projects/{pid}/construction/packages/{package_id}/start")
def start_package(
    pid: int,
    package_id: int,
    data: ReleaseIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    package = _package(db, pid, package_id)
    readiness.start_work(db, u, found, package, data.version)
    _audit(db, u, "start", "work_packages", package.id, pid)
    _commit(db)
    return readiness.package_view(db, u, found, package)


@router.post("/projects/{pid}/construction/packages/{package_id}/drawing-impact")
def resolve_drawing_impact(
    pid: int,
    package_id: int,
    data: ImpactIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    package = _package(db, pid, package_id)
    impact.resolve(db, u, found, package, data)
    _audit(db, u, "drawing_impact", "work_packages", package.id, pid, {"action": data.action})
    _commit(db)
    return readiness.package_view(db, u, found, package)


@router.get("/projects/{pid}/construction/activities")
def construction_activities(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return service.list_activities(db, found)


@router.post("/projects/{pid}/construction/activities", status_code=201)
def create_activity(
    pid: int, data: ActivityIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = service.add_activity(db, u, found, data)
    _audit(db, u, "create", "construction_activities", row.id, pid, {"code": row.code})
    _commit(db)
    return service._activity_row(db, row)


@router.put("/projects/{pid}/construction/activities/{activity_id}")
def update_activity(
    pid: int,
    activity_id: int,
    data: ActivityUpdateIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(ConstructionActivity, activity_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Activity not found")
    service.save_activity(db, u, found, row, data)
    _audit(db, u, "update", "construction_activities", row.id, pid, {"code": data.code})
    _commit(db)
    return service._activity_row(db, row)


@router.get("/projects/{pid}/construction/items")
def construction_items(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return service.list_items(db, found)


@router.post("/projects/{pid}/construction/items", status_code=201)
def create_item(
    pid: int, data: ItemIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = service.add_item(db, u, found, data)
    _audit(db, u, "create", "construction_items", row.id, pid, {"identifier": row.identifier})
    _commit(db)
    return service._item_row(db, row)


@router.put("/projects/{pid}/construction/items/{item_id}")
def update_item(
    pid: int,
    item_id: int,
    data: ItemUpdateIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(ConstructionItem, item_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Work item not found")
    service.save_item(db, u, found, row, data)
    _audit(db, u, "update", "construction_items", row.id, pid, {"identifier": data.identifier})
    _commit(db)
    return service._item_row(db, row)


@router.get("/projects/{pid}/construction/connections")
def construction_connections(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return connections.board(db, found)


@router.get("/projects/{pid}/construction/progress")
def progress_board(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return progress.board(db, u, found)


@router.post("/projects/{pid}/construction/progress", status_code=201)
def create_progress(
    pid: int, data: ReportIn, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = progress.add_report(db, u, found, data)
    _audit(db, u, "create", "progress_reports", row.id, pid, {"number": row.number})
    _commit(db)
    return progress.report_view(db, u, found, row)


@router.put("/projects/{pid}/construction/progress/{report_id}")
def update_progress(
    pid: int,
    report_id: int,
    data: ReportUpdateIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(ProgressReport, report_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Daily report not found")
    progress.save_report(db, u, found, row, data)
    _audit(db, u, "update", "progress_reports", row.id, pid, {"number": row.number})
    _commit(db)
    return progress.report_view(db, u, found, row)


@router.post("/projects/{pid}/construction/progress/{report_id}/lines", status_code=201)
def add_progress_line(
    pid: int,
    report_id: int,
    data: LineIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(ProgressReport, report_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Daily report not found")
    progress.add_line(db, u, found, row, data)
    _audit(db, u, "create", "progress_lines", row.id, pid, {"activity_id": data.activity_id})
    _commit(db)
    return progress.report_view(db, u, found, row)


@router.delete("/projects/{pid}/construction/progress/{report_id}/lines/{line_id}")
def delete_progress_line(
    pid: int,
    report_id: int,
    line_id: int,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(ProgressReport, report_id)
    line = db.get(ProgressLine, line_id)
    if not row or row.project_id != pid or not line:
        raise HTTPException(404, "Progress line not found")
    progress.remove_line(db, row, line)
    _audit(db, u, "delete", "progress_lines", line_id, pid)
    _commit(db)
    return progress.report_view(db, u, found, row)


@router.post("/projects/{pid}/construction/progress/{report_id}/lines/{line_id}/labour", status_code=201)
def add_progress_labour(
    pid: int,
    report_id: int,
    line_id: int,
    data: LabourIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(ProgressReport, report_id)
    line = db.get(ProgressLine, line_id)
    if not row or row.project_id != pid or not line:
        raise HTTPException(404, "Progress line not found")
    entry = progress.add_labour(db, u, found, row, line, data)
    _audit(db, u, "create", "progress_labour", entry.id, pid, {"line_id": line_id, "personnel_id": entry.personnel_id})
    _commit(db)
    return progress.report_view(db, u, found, row)


@router.delete("/projects/{pid}/construction/progress/{report_id}/labour/{labour_id}")
def delete_progress_labour(
    pid: int,
    report_id: int,
    labour_id: int,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(ProgressReport, report_id)
    entry = db.get(ProgressLabour, labour_id)
    if not row or row.project_id != pid or not entry:
        raise HTTPException(404, "Labour entry not found")
    progress.remove_labour(db, row, entry)
    _audit(db, u, "delete", "progress_labour", labour_id, pid)
    _commit(db)
    return progress.report_view(db, u, found, row)


@router.post("/projects/{pid}/construction/progress/{report_id}/submit")
def submit_progress(
    pid: int,
    report_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(ProgressReport, report_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Daily report not found")
    instance, warnings = progress.submit_report(db, u, found, row, data.version)
    _audit(db, u, "submit", "progress_reports", row.id, pid, {"review_id": instance.id})
    _commit(db)
    view = progress.report_view(db, u, found, row)
    view["warnings"] = warnings
    return view


@router.post("/projects/{pid}/construction/progress/{report_id}/resubmit")
def resubmit_progress(
    pid: int,
    report_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(ProgressReport, report_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Daily report not found")
    if row.version != data.version:
        raise HTTPException(409, "This daily report changed. Reload it and try again")
    instance = progress._latest_review(db, found, row)
    if not instance or instance.state != "Returned":
        raise HTTPException(409, "Only a returned daily report can be resubmitted")
    progress.apply_resubmit(db, u, instance, instance.version)
    _audit(db, u, "resubmit", "progress_reports", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return progress.report_view(db, u, found, row)


@router.post("/projects/{pid}/construction/progress/{report_id}/cancel")
def cancel_progress(
    pid: int,
    report_id: int,
    data: CancelIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(ProgressReport, report_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Daily report not found")
    progress.cancel_report(db, u, row, data)
    _audit(db, u, "cancel", "progress_reports", row.id, pid, {"reason": data.reason})
    _commit(db)
    return progress.report_view(db, u, found, row)


@router.get("/projects/{pid}/construction/monitoring")
def construction_monitoring(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return monitoring.board(db, u, found)


@router.post("/projects/{pid}/construction/packages/{package_id}/hold")
def hold_package(
    pid: int,
    package_id: int,
    data: HoldIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    package = _package(db, pid, package_id)
    row = monitoring.hold_work(db, u, found, package, data)
    _audit(db, u, "hold", "construction_holds", row.id, pid, {"reason": row.reason})
    _commit(db)
    return monitoring.hold_view(db, u, found, row)


@router.post("/projects/{pid}/construction/holds/{hold_id}/resume")
def resume_package(
    pid: int,
    hold_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(WorkHold, hold_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Hold not found")
    instance = monitoring.request_resume(db, u, found, row, data.version)
    _audit(db, u, "resume", "construction_holds", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return monitoring.hold_view(db, u, found, row)


@router.post("/projects/{pid}/construction/holds/{hold_id}/resubmit")
def resubmit_resume(
    pid: int,
    hold_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(WorkHold, hold_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Hold not found")
    if row.version != data.version:
        raise HTTPException(409, "This hold changed. Reload it and try again")
    instance = monitoring._latest_review(db, found, row)
    if not instance or instance.state != "Returned":
        raise HTTPException(409, "Only a returned resume can be resubmitted")
    monitoring.apply_resubmit(db, u, instance, instance.version)
    _audit(db, u, "resubmit", "construction_holds", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return monitoring.hold_view(db, u, found, row)


@router.post("/projects/{pid}/construction/blockers", status_code=201)
def create_blocker(
    pid: int,
    data: BlockerIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = monitoring.add_blocker(db, u, found, data)
    _audit(db, u, "create", "construction_blockers", row.id, pid, {"kind": row.kind})
    _commit(db)
    return monitoring.blocker_view(db, row)


@router.post("/projects/{pid}/construction/blockers/{blocker_id}/resolve")
def resolve_blocker(
    pid: int,
    blocker_id: int,
    data: BlockerResolveIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(ConstructionBlocker, blocker_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Blocker not found")
    monitoring.resolve_blocker(db, u, found, row, data)
    _audit(db, u, "resolve", "construction_blockers", row.id, pid)
    _commit(db)
    return monitoring.blocker_view(db, row)


@router.get("/projects/{pid}/construction/handover")
def handover_board(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return handover.board(db, u, found)


@router.post("/projects/{pid}/construction/handover", status_code=201)
def create_dossier(
    pid: int,
    data: DossierIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = handover.add_dossier(db, u, found, data)
    _audit(db, u, "create", "completion_dossiers", row.id, pid, {"number": row.number})
    _commit(db)
    return handover.dossier_view(db, u, found, row)


@router.post("/projects/{pid}/construction/handover/{dossier_id}/submit")
def submit_dossier(
    pid: int,
    dossier_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(CompletionDossier, dossier_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Dossier not found")
    instance = handover.submit_dossier(db, u, found, row, data.version)
    _audit(db, u, "submit", "completion_dossiers", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return handover.dossier_view(db, u, found, row)


@router.post("/projects/{pid}/construction/handover/{dossier_id}/resubmit")
def resubmit_dossier(
    pid: int,
    dossier_id: int,
    data: VersionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(CompletionDossier, dossier_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Dossier not found")
    if row.version != data.version:
        raise HTTPException(409, "This dossier changed. Reload it and try again")
    instance = handover._latest_review(db, found, row)
    if not instance or instance.state != "Returned":
        raise HTTPException(409, "Only a returned dossier can be resubmitted")
    handover.apply_resubmit(db, u, instance, instance.version)
    _audit(db, u, "resubmit", "completion_dossiers", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return handover.dossier_view(db, u, found, row)


@router.post("/projects/{pid}/construction/handover/{dossier_id}/cancel")
def cancel_dossier(
    pid: int,
    dossier_id: int,
    data: CancelIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(CompletionDossier, dossier_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Dossier not found")
    handover.cancel_dossier(db, u, row, data)
    _audit(db, u, "cancel", "completion_dossiers", row.id, pid, {"reason": data.reason})
    _commit(db)
    return handover.dossier_view(db, u, found, row)


@router.put("/projects/{pid}/construction/activities/{activity_id}/milestones")
def save_milestones(
    pid: int,
    activity_id: int,
    data: MilestonesIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    row = db.get(ConstructionActivity, activity_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Activity not found")
    progress.save_milestones(db, found, row, data)
    _audit(db, u, "update", "activity_milestones", row.id, pid)
    _commit(db)
    return progress.activity_measures(db, row)
