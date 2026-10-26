"""Completion dossiers and construction handover.

Approving a dossier marks the package handed over. It records the verified
quantity already stored. It does not accept the work for quality, certify it
for billing, or create a commissioning test, inspection, or permit.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import update

from app.domains.coordination.service import (
    REVIEW_GUARDS,
    _close_tasks,
    _lock,
    _open_stage,
    current_stage,
    review_payload,
)
from app.domains.engineering_documents.models import Drawing, DrawingRevision
from app.domains.engineering_documents.workflow import submit_record
from app.domains.identity_projects.security import permitted
from app.domains.supply_chain.service import _authority, _policy

from .models import (
    CompletionDossier,
    ConstructionActivity,
    ConstructionBlocker,
    ProgressLine,
    ProgressReport,
    ReadinessCheck,
    WorkPackage,
    WorkPackageDrawing,
    now,
)
from .monitoring import _tell, _watchers
from .progress import activity_measures

HANDOVER = "construction.handover"
OPEN = {"Draft", "Pending Review", "Returned for Correction"}
EDITABLE = {"Draft", "Returned for Correction"}
OPEN_REPORTS = {"Draft", "Pending Review", "Returned for Correction"}
STATEMENT = (
    "This dossier records the verified construction quantity. "
    "It does not accept the work for quality or certify it for billing. "
    "No commissioning test, inspection, or permit was created."
)


def _bump(db, row, version, values):
    changed = db.execute(
        update(type(row))
        .where(type(row).id == row.id, type(row).version == version)
        .values(version=version + 1, modified_at=now(), **values)
    )
    if changed.rowcount != 1:
        db.rollback()
        label = "dossier" if isinstance(row, CompletionDossier) else "work package"
        raise HTTPException(409, f"This {label} changed. Reload it and try again")
    db.refresh(row)


def _latest_review(db, project, dossier):
    from app.domains.coordination.models import ReviewInstance

    return (
        db.query(ReviewInstance)
        .filter_by(project_id=project.id, record_type=HANDOVER, record_id=dossier.id)
        .order_by(ReviewInstance.id.desc())
        .first()
    )


def _open_dossier(db, package, ignore_id=None):
    rows = (
        db.query(CompletionDossier)
        .filter(
            CompletionDossier.package_id == package.id,
            CompletionDossier.status.in_(tuple(OPEN)),
        )
        .all()
    )
    return next((row for row in rows if row.id != ignore_id), None)


def _approved(db, package):
    return (
        db.query(CompletionDossier)
        .filter_by(package_id=package.id, status="Approved")
        .first()
    )


def _problem(db, project, package):
    from app.domains.quality.findings import handover_problem

    if handover_problem(db, package):
        return "A quality hold blocks handover"
    if package.release_state != "Released":
        return "Handover applies to a released work package"
    if package.status == "On Hold":
        return "Resume the work package before handover"
    if package.status == "Handed Over" or _approved(db, package):
        return "This work package already has a handover record"
    if package.status not in {"In Progress", "Physically Complete"}:
        return "Handover applies to work that is in progress"
    from .monitoring import _open_hold

    if _open_hold(db, package):
        return "Resume the work package before handover"
    if (
        db.query(ConstructionBlocker)
        .filter_by(package_id=package.id, status="Open")
        .first()
    ):
        return "Resolve open blockers before handover"
    activities = (
        db.query(ConstructionActivity)
        .filter_by(package_id=package.id, active=True)
        .all()
    )
    if not activities:
        return "Add the work before preparing a handover"
    activity_ids = {row.id for row in activities}
    open_line = (
        db.query(ProgressLine, ProgressReport)
        .join(ProgressReport, ProgressReport.id == ProgressLine.report_id)
        .filter(
            ProgressLine.activity_id.in_(activity_ids),
            ProgressReport.status.in_(tuple(OPEN_REPORTS)),
        )
        .first()
    )
    if open_line:
        return "Approve or cancel the open daily report before handover"
    for activity in activities:
        measured = activity_measures(db, activity)
        if measured["method"] == "Weighted milestones":
            if measured["verified_percent"] != "100.00":
                return "Verified quantity is still below the approved scope"
        elif Decimal(measured["verified_quantity"]) < Decimal(measured["scope_quantity"]):
            return "Verified quantity is still below the approved scope"
    for check in db.query(ReadinessCheck).filter_by(package_id=package.id):
        if check.classification == "Mandatory" and check.status != "Satisfied":
            return "A mandatory readiness check is not satisfied"
    for link in db.query(WorkPackageDrawing).filter_by(package_id=package.id):
        revision = db.get(DrawingRevision, link.revision_id)
        drawing = db.get(Drawing, revision.drawing_id) if revision else None
        if not revision or not drawing or drawing.project_id != project.id or revision.release_state != "Released":
            return "A linked drawing is no longer released"
    return None


def _snapshot(db, project, package):
    activities = []
    for activity in (
        db.query(ConstructionActivity)
        .filter_by(package_id=package.id, active=True)
        .order_by(ConstructionActivity.code)
    ):
        measured = activity_measures(db, activity)
        activities.append(
            {
                "code": activity.code,
                "method": measured["method"],
                "scope_quantity": measured["scope_quantity"],
                "unit": measured["unit"],
                "verified_quantity": measured["verified_quantity"],
                "verified_percent": measured["verified_percent"],
                "rework_quantity": measured["rework_quantity"],
                "accepted_quantity": None,
                "certified_quantity": None,
            }
        )
    checks = [
        {
            "check_type": row.check_type,
            "status": row.status,
            "evidence": row.evidence,
            "source_label": row.source_label,
        }
        for row in db.query(ReadinessCheck).filter_by(package_id=package.id).order_by(ReadinessCheck.id)
    ]
    drawings = []
    for link in db.query(WorkPackageDrawing).filter_by(package_id=package.id):
        revision = db.get(DrawingRevision, link.revision_id)
        drawing = db.get(Drawing, revision.drawing_id) if revision else None
        if drawing and revision:
            drawings.append(
                {
                    "label": f"{drawing.number} rev {revision.code}",
                    "release_state": revision.release_state,
                }
            )
    return {
        "package_code": package.code,
        "activities": activities,
        "checks": checks,
        "drawings": drawings,
        "accepted_quantity": None,
        "certified_quantity": None,
        "statement": STATEMENT,
    }


def _policy_for(db, project, package):
    policy = _policy(db, project, HANDOVER, package.company_id, package.discipline_id)
    if not policy:
        raise HTTPException(422, "Mandatory reviewer configuration is missing")
    _authority(db, project, policy)
    return policy


def _raise(problem):
    if problem:
        raise HTTPException(422, problem)


def dossier_view(db, user, project, dossier):
    package = db.get(WorkPackage, dossier.package_id)
    instance = _latest_review(db, project, dossier)
    return {
        "id": dossier.id,
        "number": dossier.number,
        "package_id": dossier.package_id,
        "package_code": package.code if package else "",
        "package_status": package.status if package else "",
        "release_state": package.release_state if package else "",
        "status": dossier.status,
        "statement": dossier.statement,
        "payload": dossier.payload or {},
        "cancellation_reason": dossier.cancellation_reason,
        "version": dossier.version,
        "review": review_payload(db, user, instance) if instance else None,
    }


def add_dossier(db, user, project, data):
    package = db.get(WorkPackage, data.package_id)
    if not package or package.project_id != project.id:
        raise HTTPException(404, "Work package not found")
    if package.status != "In Progress" or package.release_state != "Released":
        raise HTTPException(409, "Prepare a handover from work that is in progress")
    if _approved(db, package) or _open_dossier(db, package):
        raise HTTPException(409, "This work package already has a handover dossier")
    key = data.number.strip().casefold()
    if db.query(CompletionDossier).filter_by(project_id=project.id, number_key=key).first():
        raise HTTPException(409, "Dossier number already exists on this project")
    row = CompletionDossier(
        organization_id=project.organization_id,
        project_id=project.id,
        package_id=package.id,
        number=data.number.strip(),
        number_key=key,
        statement=STATEMENT,
        payload={},
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def submit_dossier(db, user, project, dossier, version):
    if dossier.status == "Returned for Correction":
        raise HTTPException(409, "A returned dossier is resubmitted, not submitted again")
    if dossier.status != "Draft":
        raise HTTPException(409, "Only a draft dossier can be submitted")
    package = db.get(WorkPackage, dossier.package_id)
    if not package or package.project_id != project.id:
        raise HTTPException(404, "Work package not found")
    _raise(_problem(db, project, package))
    policy = _policy_for(db, project, package)
    payload = _snapshot(db, project, package)
    _bump(db, dossier, version, {"status": "Pending Review", "payload": payload, "modified_by": user.id})
    _bump(db, package, package.version, {"status": "Physically Complete", "modified_by": user.id})
    return submit_record(db, user, project, HANDOVER, dossier.id, dossier.version, policy)


def apply_resubmit(db, user, instance, review_version):
    from app.domains.identity_projects.models import Project

    if instance.state != "Returned":
        raise HTTPException(409, "Only a returned review can be resubmitted")
    if user.id != instance.submitted_by and not user.organization_admin:
        raise HTTPException(403, "Only the submitter can resubmit")
    project = db.get(Project, instance.project_id)
    dossier = db.get(CompletionDossier, instance.record_id)
    package = db.get(WorkPackage, dossier.package_id) if dossier else None
    if not project or not dossier or not package or package.project_id != project.id:
        raise HTTPException(404, "Dossier not found")
    permitted(db, user, project, "construction.edit")
    if dossier.status != "Returned for Correction":
        raise HTTPException(409, "Only a returned dossier can be resubmitted")
    _raise(_problem(db, project, package))
    policy = _policy_for(db, project, package)
    payload = _snapshot(db, project, package)
    _lock(db, instance, review_version)
    _close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    _bump(
        db,
        dossier,
        dossier.version,
        {"status": "Pending Review", "payload": payload, "modified_by": user.id},
    )
    if package.status != "Physically Complete":
        _bump(db, package, package.version, {"status": "Physically Complete", "modified_by": user.id})
    instance.record_version = dossier.version
    instance.policy_id = policy.id
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def cancel_dossier(db, user, dossier, data):
    if dossier.status == "Pending Review":
        raise HTTPException(409, "This dossier is in review")
    if dossier.status not in EDITABLE:
        raise HTTPException(409, "Only a draft dossier can be cancelled here")
    _bump(
        db,
        dossier,
        data.version,
        {"status": "Cancelled", "cancellation_reason": data.reason.strip(), "modified_by": user.id},
    )


def on_review_event(db, user, instance, project, action, stage=None):
    if instance.record_type != HANDOVER:
        return
    dossier = db.get(CompletionDossier, instance.record_id)
    package = db.get(WorkPackage, dossier.package_id) if dossier else None
    if not dossier or not package or package.project_id != project.id:
        return
    if action == "advance":
        return
    if action == "return":
        dossier.status = "Returned for Correction"
        if package.status == "Physically Complete":
            package.status = "In Progress"
            package.version += 1
            package.modified_by = user.id
            package.modified_at = now()
    elif action == "reject":
        dossier.status = "Rejected"
        if package.status == "Physically Complete":
            package.status = "In Progress"
            package.version += 1
            package.modified_by = user.id
            package.modified_at = now()
    elif instance.state == "Approved":
        dossier.status = "Approved"
        package.status = "Handed Over"
        package.version += 1
        package.modified_by = user.id
        package.modified_at = now()
        _tell(
            db,
            project,
            _watchers(db, project),
            "Work handed over",
            f"{package.code} has a handover record. No commissioning test was created.",
            f"construction.handover.{dossier.id}",
        )
    else:
        return
    dossier.version += 1
    dossier.modified_by = user.id
    dossier.modified_at = now()


def review_guard(db, user, instance, stage, action):
    if instance.record_type != HANDOVER or action != "approve":
        return
    from app.domains.identity_projects.models import Project

    project = db.get(Project, instance.project_id)
    dossier = db.get(CompletionDossier, instance.record_id)
    package = db.get(WorkPackage, dossier.package_id) if dossier else None
    if (
        not project
        or not dossier
        or not package
        or package.project_id != project.id
        or dossier.status != "Pending Review"
        or package.status != "Physically Complete"
    ):
        raise HTTPException(409, "This dossier is not awaiting handover")
    problem = _problem(db, project, package)
    if problem:
        raise HTTPException(409, problem)


def board(db, user, project):
    rows = (
        db.query(CompletionDossier)
        .filter_by(project_id=project.id)
        .filter(CompletionDossier.status != "Cancelled")
        .order_by(CompletionDossier.id.desc())
        .all()
    )
    packages = (
        db.query(WorkPackage)
        .filter(
            WorkPackage.project_id == project.id,
            WorkPackage.status == "In Progress",
            WorkPackage.release_state == "Released",
        )
        .order_by(WorkPackage.code)
        .all()
    )
    return {
        "note": STATEMENT,
        "dossiers": [dossier_view(db, user, project, row) for row in rows],
        "packages": [
            {"id": package.id, "code": package.code, "status": package.status, "version": package.version}
            for package in packages
            if not _approved(db, package) and not _open_dossier(db, package)
        ],
    }


if review_guard not in REVIEW_GUARDS:
    REVIEW_GUARDS.append(review_guard)
