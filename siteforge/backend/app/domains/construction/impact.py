"""Drawing supersession and withdrawal on work packages.

A newer release does not switch a package to it. The package is flagged, its
owners get a task, and the responsible engineer relinks or accepts with a reason.
"""

from fastapi import HTTPException

from app.domains.coordination.jobs import notify
from app.domains.coordination.service import _close_tasks, _task
from app.domains.engineering_documents.models import Drawing, DrawingRevision
from app.domains.identity_projects.models import Project, User

from .models import ConstructionActivity, WorkPackage, WorkPackageDrawing, now

IMPACT = "construction.drawing_impact"
LIVE = ("Draft", "Ready", "In Progress", "On Hold")
OPEN = "Review required"


def _packages(db, revision):
    ids = {row.package_id for row in db.query(WorkPackageDrawing).filter_by(revision_id=revision.id)}
    ids |= {row.package_id for row in db.query(ConstructionActivity).filter_by(drawing_revision_id=revision.id)}
    if not ids:
        return []
    return db.query(WorkPackage).filter(WorkPackage.id.in_(ids), WorkPackage.status.in_(LIVE)).all()


def flag_revision(db, user, revision, detail):
    drawing = db.get(Drawing, revision.drawing_id)
    project = db.get(Project, drawing.project_id) if drawing else None
    if not project:
        return
    for package in _packages(db, revision):
        if package.impact_state == OPEN and package.impact_revision_id == revision.id:
            continue
        package.impact_state = OPEN
        package.impact_detail = detail
        package.impact_revision_id = revision.id
        package.version += 1
        package.modified_by = user.id
        package.modified_at = now()
        for owner_id in {package.responsible_user_id, package.supervisor_user_id} - {None}:
            person = db.get(User, owner_id)
            if not person or not person.active:
                continue
            _task(
                db, user, project, owner_id, f"Review drawing impact on {package.code}", IMPACT, package.id, priority="High"
            )
            notify(
                db,
                person,
                "Drawing impact on work package",
                f"{package.code}: {detail}",
                f"package-impact:{package.id}:{revision.id}:{revision.release_state}:{owner_id}",
                project_id=project.id,
                link=f"/projects/{project.id}",
            )
    db.flush()


def choices(db, package):
    if package.impact_state != OPEN or not package.impact_revision_id:
        return []
    old = db.get(DrawingRevision, package.impact_revision_id)
    if not old:
        return []
    rows = (
        db.query(DrawingRevision)
        .filter_by(drawing_id=old.drawing_id, release_state="Released")
        .order_by(DrawingRevision.id)
        .all()
    )
    return [{"id": row.id, "code": row.code} for row in rows]


def resolve(db, user, project, package, data):
    from .readiness import _bump

    if package.impact_state != OPEN:
        raise HTTPException(409, "This work package has no open drawing impact")
    if user.id != package.responsible_user_id:
        raise HTTPException(403, "Only the responsible engineer resolves a drawing impact")
    reason = data.reason.strip()
    old = db.get(DrawingRevision, package.impact_revision_id)
    new = None
    if data.action == "relink":
        new = db.get(DrawingRevision, data.revision_id) if data.revision_id else None
        if not new or not old or new.drawing_id != old.drawing_id or new.release_state != "Released":
            raise HTTPException(422, "Choose the released revision of the same drawing")
    elif len(reason) < 10:
        raise HTTPException(422, "Record why the work is not affected")
    note = f"Relinked to rev {new.code}. {reason}".strip() if new else f"Accepted without change: {reason}"
    _bump(db, package, data.version, {"impact_state": "Reviewed", "impact_detail": note, "modified_by": user.id})
    if new:
        link = db.query(WorkPackageDrawing).filter_by(package_id=package.id, revision_id=old.id).first()
        if link:
            if db.query(WorkPackageDrawing).filter_by(package_id=package.id, revision_id=new.id).first():
                db.delete(link)
            else:
                link.revision_id = new.id
        for activity in db.query(ConstructionActivity).filter_by(package_id=package.id, drawing_revision_id=old.id):
            activity.drawing_revision_id = new.id
            activity.version += 1
    _close_tasks(db, project.id, IMPACT, package.id, "Completed", note)
    db.flush()
    return package
