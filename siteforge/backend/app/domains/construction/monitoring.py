"""Blockers, holds, and the construction monitoring board.

A hold pauses an in-progress package. Resume uses the reviewer already saved
for work release. Rework stays on the daily line. No inspection, permit,
schedule baseline, attendance record, or billing certificate is created.
"""

from datetime import date

from fastapi import HTTPException
from sqlalchemy import update

from app.domains.coordination.jobs import notify
from app.domains.coordination.service import (
    REVIEW_GUARDS,
    _close_tasks,
    _lock,
    _open_stage,
    current_stage,
    review_payload,
)
from app.domains.engineering_documents.workflow import submit_record
from app.domains.identity_projects.models import Membership, Role, User
from app.domains.identity_projects.security import permitted
from app.domains.supply_chain.service import _authority, _policy

from .models import (
    ConstructionActivity,
    ConstructionBlocker,
    ProgressLine,
    ProgressReport,
    WorkHold,
    WorkPackage,
    now,
)
from .readiness import RELEASE
from .service import _member, day, qty

RESUME = "construction.resume"
OPEN_HOLD = {"Open", "In Review", "Returned", "Rejected"}
RESUME_FROM = {"Open", "Rejected"}
EXECUTING = {"In Progress", "On Hold"}
WATCH = {"Site Engineer", "Discipline Head", "Project Manager"}
HOLD_NOTE = (
    "This pause does not create an inspection or a permit. Readiness notes stay as they were."
)
REWORK_NOTE = "Rework is recorded on the daily line and stays out of verified progress."


def _bump_package(db, package, version, values):
    changed = db.execute(
        update(WorkPackage)
        .where(WorkPackage.id == package.id, WorkPackage.version == version)
        .values(version=version + 1, modified_at=now(), **values)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This work package changed. Reload it and try again")
    db.refresh(package)


def _bump_hold(db, hold, version, values):
    changed = db.execute(
        update(WorkHold)
        .where(WorkHold.id == hold.id, WorkHold.version == version)
        .values(version=version + 1, modified_at=now(), **values)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This hold changed. Reload it and try again")
    db.refresh(hold)


def _bump_blocker(db, row, version, values):
    changed = db.execute(
        update(ConstructionBlocker)
        .where(ConstructionBlocker.id == row.id, ConstructionBlocker.version == version)
        .values(version=version + 1, modified_at=now(), **values)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This blocker changed. Reload it and try again")
    db.refresh(row)


def _open_hold(db, package):
    return (
        db.query(WorkHold)
        .filter(WorkHold.package_id == package.id, WorkHold.status.in_(tuple(OPEN_HOLD)))
        .order_by(WorkHold.id.desc())
        .first()
    )


def _watchers(db, project):
    rows = (
        db.query(User)
        .join(Membership, Membership.user_id == User.id)
        .join(Role, Role.id == Membership.role_id)
        .filter(
            Membership.project_id == project.id,
            Membership.active.is_(True),
            User.active.is_(True),
            User.organization_id == project.organization_id,
            Role.name.in_(tuple(WATCH)),
        )
        .all()
    )
    return list({person.id: person for person in rows}.values())


def _tell(db, project, people, title, body, source_key):
    for person in people:
        notify(db, person, title, body, source_key, project_id=project.id, link=f"/projects/{project.id}")


def _latest_review(db, project, hold):
    from app.domains.coordination.models import ReviewInstance

    return (
        db.query(ReviewInstance)
        .filter_by(project_id=project.id, record_type=RESUME, record_id=hold.id)
        .order_by(ReviewInstance.id.desc())
        .first()
    )


def _executing(package):
    if package.status not in EXECUTING or package.release_state != "Released":
        raise HTTPException(422, "Record a blocker on work that is in progress or on hold")


def hold_view(db, user, project, hold):
    package = db.get(WorkPackage, hold.package_id)
    instance = _latest_review(db, project, hold)
    opener = db.get(User, hold.opened_by)
    return {
        "id": hold.id,
        "package_id": hold.package_id,
        "package_code": package.code if package else "",
        "package_status": package.status if package else "",
        "release_state": package.release_state if package else "",
        "package_version": package.version if package else None,
        "reason": hold.reason,
        "status": hold.status,
        "version": hold.version,
        "opened_by": opener.name if opener else "",
        "note": hold.note,
        "review": review_payload(db, user, instance) if instance else None,
    }


def blocker_view(db, row):
    package = db.get(WorkPackage, row.package_id)
    owner = db.get(User, row.owner_user_id)
    return {
        "id": row.id,
        "package_id": row.package_id,
        "package_code": package.code if package else "",
        "kind": row.kind,
        "description": row.description,
        "owner_user_id": row.owner_user_id,
        "owner_name": owner.name if owner else "",
        "recovery_note": row.recovery_note,
        "status": row.status,
        "resolution_note": row.resolution_note,
        "version": row.version,
    }


def hold_work(db, user, project, package, data):
    if package.status != "In Progress" or package.release_state != "Released":
        raise HTTPException(409, "Hold applies to work that is already in progress")
    if _open_hold(db, package):
        raise HTTPException(409, "This work package is already on hold")
    hold = WorkHold(
        project_id=project.id,
        package_id=package.id,
        reason=data.reason.strip(),
        status="Open",
        note=HOLD_NOTE,
        opened_by=user.id,
    )
    db.add(hold)
    db.flush()
    _bump_package(db, package, data.version, {"status": "On Hold", "modified_by": user.id})
    _tell(
        db,
        project,
        _watchers(db, project),
        "Work on hold",
        f"{package.code} is on hold. {hold.reason} Daily progress stays closed until work resumes.",
        f"construction.hold.{hold.id}",
    )
    return hold


def _release_policy(db, project, package):
    policy = _policy(db, project, RELEASE, package.company_id, package.discipline_id)
    if not policy:
        raise HTTPException(422, "Mandatory reviewer configuration is missing")
    _authority(db, project, policy)
    return policy


def request_resume(db, user, project, hold, version):
    package = db.get(WorkPackage, hold.package_id)
    if not package or package.project_id != project.id:
        raise HTTPException(404, "Hold not found")
    if package.status != "On Hold" or package.release_state != "Released":
        raise HTTPException(409, "Resume applies to a released package that is on hold")
    from app.domains.hse.field import raise_field_block
    from app.domains.hse.permits import _raise_block

    _raise_block(db, package, None)
    raise_field_block(db, package, None)
    from app.domains.hse.holds import raise_hold_block

    raise_hold_block(db, package, None)
    if hold.status == "Returned":
        raise HTTPException(409, "A returned resume is resubmitted, not submitted again")
    if hold.status == "In Review":
        raise HTTPException(409, "Resume is already in review")
    if hold.status not in RESUME_FROM:
        raise HTTPException(409, "This hold can no longer be resumed")
    policy = _release_policy(db, project, package)
    _bump_hold(db, hold, version, {"status": "In Review", "modified_by": user.id})
    return submit_record(db, user, project, RESUME, hold.id, hold.version, policy)


def apply_resubmit(db, user, instance, review_version):
    from app.domains.identity_projects.models import Project

    if instance.state != "Returned":
        raise HTTPException(409, "Only a returned review can be resubmitted")
    if user.id != instance.submitted_by and not user.organization_admin:
        raise HTTPException(403, "Only the submitter can resubmit")
    project = db.get(Project, instance.project_id)
    hold = db.get(WorkHold, instance.record_id)
    package = db.get(WorkPackage, hold.package_id) if hold else None
    if not project or not hold or not package or package.project_id != project.id:
        raise HTTPException(404, "Hold not found")
    permitted(db, user, project, "construction.edit")
    if hold.status != "Returned" or package.status != "On Hold":
        raise HTTPException(409, "Only a returned resume can be resubmitted")
    policy = _release_policy(db, project, package)
    _lock(db, instance, review_version)
    _close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    _bump_hold(db, hold, hold.version, {"status": "In Review", "modified_by": user.id})
    instance.record_version = hold.version
    instance.policy_id = policy.id
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def on_review_event(db, user, instance, project, action, stage=None):
    if instance.record_type != RESUME:
        return
    hold = db.get(WorkHold, instance.record_id)
    package = db.get(WorkPackage, hold.package_id) if hold else None
    if not hold or not package or package.project_id != project.id:
        return
    if action == "advance":
        return
    if action == "return":
        hold.status = "Returned"
    elif action == "reject":
        hold.status = "Rejected"
    elif instance.state == "Approved":
        from app.domains.hse.field import raise_field_block
        from app.domains.hse.permits import _raise_block

        _raise_block(db, package, None)
        raise_field_block(db, package, None)
        from app.domains.hse.holds import raise_hold_block

        raise_hold_block(db, package, None)
        hold.status = "Closed"
        package.status = "In Progress"
        package.version += 1
        package.modified_by = user.id
        package.modified_at = now()
        _tell(
            db,
            project,
            _watchers(db, project),
            "Work resumed",
            f"{package.code} is in progress again. Daily progress can be recorded.",
            f"construction.resume.{hold.id}",
        )
    else:
        return
    hold.version += 1
    hold.modified_by = user.id
    hold.modified_at = now()


def review_guard(db, user, instance, stage, action):
    if instance.record_type != RESUME or action != "approve":
        return
    from app.domains.identity_projects.models import Project

    project = db.get(Project, instance.project_id)
    hold = db.get(WorkHold, instance.record_id)
    package = db.get(WorkPackage, hold.package_id) if hold else None
    if (
        not project
        or not hold
        or not package
        or package.project_id != project.id
        or package.status != "On Hold"
        or package.release_state != "Released"
        or hold.status != "In Review"
    ):
        raise HTTPException(409, "This work package is not awaiting resume")


def add_blocker(db, user, project, data):
    package = db.get(WorkPackage, data.package_id)
    if not package or package.project_id != project.id:
        raise HTTPException(404, "Work package not found")
    _executing(package)
    _member(db, project, data.owner_user_id, "the blocker owner")
    row = ConstructionBlocker(
        organization_id=project.organization_id,
        project_id=project.id,
        package_id=package.id,
        kind=data.kind,
        description=data.description.strip(),
        owner_user_id=data.owner_user_id,
        recovery_note=data.recovery_note.strip(),
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    _tell(
        db,
        project,
        _watchers(db, project),
        "Construction blocker",
        f"{package.code} has a {data.kind.lower()} blocker. {row.description}",
        f"construction.blocker.{row.id}",
    )
    return row


def resolve_blocker(db, user, project, row, data):
    if row.project_id != project.id:
        raise HTTPException(404, "Blocker not found")
    if row.status != "Open":
        raise HTTPException(409, "This blocker is already resolved")
    _bump_blocker(
        db,
        row,
        data.version,
        {
            "status": "Resolved",
            "resolution_note": data.resolution_note.strip(),
            "resolved_at": now(),
            "modified_by": user.id,
        },
    )
    return row


def board(db, user, project):
    packages = (
        db.query(WorkPackage)
        .filter(WorkPackage.project_id == project.id, WorkPackage.status.in_(tuple(EXECUTING)))
        .order_by(WorkPackage.code)
        .all()
    )
    holds = []
    for package in packages:
        if package.status != "On Hold":
            continue
        hold = _open_hold(db, package)
        if hold:
            holds.append(hold_view(db, user, project, hold))
    blockers = (
        db.query(ConstructionBlocker)
        .filter_by(project_id=project.id)
        .order_by(ConstructionBlocker.id.desc())
        .all()
    )
    rework = []
    lines = (
        db.query(ProgressLine, ProgressReport, ConstructionActivity)
        .join(ProgressReport, ProgressReport.id == ProgressLine.report_id)
        .join(ConstructionActivity, ConstructionActivity.id == ProgressLine.activity_id)
        .filter(
            ProgressReport.project_id == project.id,
            ProgressReport.status != "Cancelled",
            ProgressLine.rework.is_(True),
        )
        .order_by(ProgressLine.id.desc())
        .all()
    )
    for line, report, activity in lines:
        rework.append(
            {
                "line_id": line.id,
                "report_number": report.number,
                "report_status": report.status,
                "activity_code": activity.code,
                "quantity": qty(line.quantity) if line.quantity is not None else None,
                "unit": line.unit,
            }
        )
    overdue = (
        db.query(ProgressReport)
        .filter(
            ProgressReport.project_id == project.id,
            ProgressReport.status.in_(("Draft", "Returned for Correction")),
            ProgressReport.report_date < date.today(),
        )
        .order_by(ProgressReport.report_date)
        .all()
    )
    return {
        "note": (
            "Open blockers, packages on hold, rework already recorded, and daily reports "
            "still in draft after their date are listed here."
        ),
        "packages": [
            {
                "id": package.id,
                "code": package.code,
                "status": package.status,
                "release_state": package.release_state,
                "version": package.version,
            }
            for package in packages
        ],
        "holds": holds,
        "blockers": [blocker_view(db, row) for row in blockers],
        "rework": rework,
        "rework_note": REWORK_NOTE,
        "overdue_reports": [
            {
                "id": report.id,
                "number": report.number,
                "report_date": day(report.report_date),
                "status": report.status,
                "shift": report.shift,
            }
            for report in overdue
        ],
    }


if review_guard not in REVIEW_GUARDS:
    REVIEW_GUARDS.append(review_guard)
