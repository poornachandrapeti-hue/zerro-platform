from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.domains.identity_projects.lifecycle import apply_activation, project_input
from app.domains.identity_projects.models import Project, User
from app.domains.identity_projects.security import permitted
from .jobs import notify, schedule_task
from .models import (
    ApprovalPolicy,
    PolicyReviewer,
    PolicyStage,
    ReminderPolicy,
    ReviewDecision,
    ReviewInstance,
    Task,
)

ACTIVATION = "project.activation"
OPEN = {"Open", "In Progress", "Blocked"}
TASK_MOVES = {
    "Open": {"In Progress", "Blocked", "Completed", "Cancelled"},
    "In Progress": {"Blocked", "Completed", "Cancelled"},
    "Blocked": {"In Progress", "Completed", "Cancelled"},
    "Completed": set(),
    "Cancelled": set(),
}


def _stages(db, policy_id):
    return (
        db.query(PolicyStage)
        .filter_by(policy_id=policy_id)
        .order_by(PolicyStage.position)
        .all()
    )


def _reviewers(db, stage_id):
    return db.query(PolicyReviewer).filter_by(stage_id=stage_id).all()


def _decisions(db, instance, stage_id):
    return (
        db.query(ReviewDecision)
        .filter_by(instance_id=instance.id, stage_id=stage_id, attempt=instance.attempt)
        .all()
    )


def current_stage(db, instance):
    if instance.state != "In Review":
        return None
    for stage in _stages(db, instance.policy_id):
        approvals = {
            row.reviewer_id
            for row in _decisions(db, instance, stage.id)
            if row.action in {"approve", "approve_with_comments"}
        }
        reviewers = _reviewers(db, stage.id)
        needed = len(reviewers) if stage.rule == "all" else stage.quorum_count
        if approvals - {row.user_id for row in reviewers}:
            continue
        if not reviewers or needed < 1 or len(approvals) < needed:
            return stage
    return None


def active_policy(db, project, record_type):
    from app.domains.identity_projects.models import ProjectDiscipline

    rows = (
        db.query(ApprovalPolicy)
        .filter_by(project_id=project.id, record_type=record_type, active=True)
        .all()
    )
    disciplines = {
        row.discipline_id
        for row in db.query(ProjectDiscipline).filter_by(project_id=project.id, active=True)
    }

    def fits(policy):
        if policy.company_id and policy.company_id != project.client_company_id:
            return False
        if policy.discipline_id and policy.discipline_id not in disciplines:
            return False
        return True

    matches = [row for row in rows if fits(row)]
    if not matches:
        return None
    return max(
        matches,
        key=lambda row: (
            int(row.company_id is not None) + int(row.discipline_id is not None),
            row.policy_version,
        ),
    )


def _stage_reviewers(stage):
    if stage.reviewers:
        return [(row.user_id, row.approval_limit) for row in stage.reviewers]
    return [(user_id, None) for user_id in stage.reviewer_ids]


def save_policy(db, user, project, data):
    if not data.stages or any(not _stage_reviewers(stage) for stage in data.stages):
        raise HTTPException(422, "Mandatory reviewer configuration is missing")
    for stage in data.stages:
        reviewers = _stage_reviewers(stage)
        ids = [user_id for user_id, _limit in reviewers]
        if len(ids) != len(set(ids)):
            raise HTTPException(422, "A reviewer can appear only once in a stage")
        if stage.rule == "quorum" and (
            stage.quorum_count < 1 or stage.quorum_count > len(reviewers)
        ):
            raise HTTPException(
                422, "Quorum must count assigned reviewers and cannot skip a stage"
            )
    previous = (
        db.query(ApprovalPolicy)
        .filter_by(
            project_id=project.id,
            record_type=data.record_type,
            company_id=data.company_id,
            discipline_id=data.discipline_id,
            active=True,
        )
        .order_by(ApprovalPolicy.policy_version.desc())
        .first()
    )
    version = (previous.policy_version + 1) if previous else 1
    if previous:
        previous.active = False
    policy = ApprovalPolicy(
        organization_id=user.organization_id,
        project_id=project.id,
        record_type=data.record_type,
        company_id=data.company_id,
        discipline_id=data.discipline_id,
        policy_version=version,
        allow_self_approval=data.allow_self_approval,
        created_by=user.id,
    )
    db.add(policy)
    db.flush()
    for index, stage in enumerate(data.stages, start=1):
        row = PolicyStage(
            policy_id=policy.id,
            position=index,
            name=stage.name,
            rule=stage.rule,
            quorum_count=stage.quorum_count or len(_stage_reviewers(stage)),
            purpose=(getattr(stage, "purpose", "") or "")[:40],
        )
        db.add(row)
        db.flush()
        for reviewer_id, limit in _stage_reviewers(stage):
            person = db.get(User, reviewer_id)
            if not person or person.organization_id != user.organization_id or not person.active:
                raise HTTPException(422, "Reviewer must be an active user in this organization")
            db.add(
                PolicyReviewer(
                    stage_id=row.id, user_id=reviewer_id, approval_limit=limit
                )
            )
    return policy


def _project_visible(db, user, project):
    if project.organization_id != user.organization_id:
        raise HTTPException(404, "Project not found")
    if not user.organization_admin:
        permitted(db, user, project, "projects.view")


def _task(
    db, user, project, owner_id, title, source_type, source_id, priority="Normal", due_date=None
):
    policy = (
        db.query(ReminderPolicy)
        .filter_by(project_id=project.id, record_type=source_type)
        .first()
    )
    due = due_date
    if due is None and policy:
        from datetime import timedelta

        due = (datetime.now(timezone.utc) + timedelta(hours=policy.reminder_hours)).date()
    task = Task(
        organization_id=user.organization_id,
        project_id=project.id,
        source_type=source_type,
        source_id=source_id,
        title=title,
        owner_id=owner_id,
        creator_id=user.id,
        priority=priority,
        due_date=due,
        status="Open",
    )
    db.add(task)
    db.flush()
    owner = db.get(User, owner_id)
    notify(
        db,
        owner,
        "Task assigned",
        title,
        f"task:{task.id}:assigned",
        project_id=project.id,
        link=f"/projects/{project.id}",
    )
    if policy and due:
        schedule_task(
            db,
            task,
            policy.reminder_hours,
            policy.escalate_after_hours,
            policy.recipient_ids or [],
        )
    return task


def _close_tasks(db, project_id, source_type, source_id, status, evidence):
    for task in db.query(Task).filter_by(
        project_id=project_id, source_type=source_type, source_id=source_id
    ):
        if task.status in OPEN:
            task.status = status
            task.evidence = evidence


def _drawing_parts(db, instance):
    if instance.record_type != "drawing.revision":
        return None
    from app.domains.engineering_documents.models import Drawing, DrawingRevision

    revision = db.get(DrawingRevision, instance.record_id)
    drawing = db.get(Drawing, revision.drawing_id) if revision else None
    if not drawing or not revision:
        return None
    return drawing, revision, f"{drawing.number} rev {revision.code}"


def _notice_subject(instance):
    return {
        "drawing.revision": "Drawing review",
        ACTIVATION: "Activation",
        "procurement.requirement": "Requirement review",
        "procurement.requisition": "Requisition review",
        "procurement.purchase_order": "Purchase order review",
        "construction.release": "Work release",
        "construction.resume": "Resume work",
        "construction.progress": "Daily progress",
        "construction.handover": "Handover",
        "quality.inspection": "Inspection",
        "quality.document": "Quality document",
        "quality.template": "Inspection template",
        "quality.material": "Material inspection",
        "quality.construction": "Construction inspection",
        "quality.ncr": "NCR",
        "quality.ncr.close": "NCR closure",
        "quality.concession": "Concession",
        "quality.hold": "Quality hold",
        "quality.qualification": "Qualification",
        "quality.calibration": "Calibration",
        "quality.dossier": "Quality dossier",
        "quality.punch.close": "Punch closure",
        "hse.document": "HSE document",
        "hse.assessment": "Risk assessment",
        "hse.permit": "Permit",
        "hse.incident": "Incident",
        "hse.hold": "Safety hold",
        "hr.deployment": "Mobilization",
        "hr.request": "Workforce demand",
        "hr.attendance": "Attendance",
        "hr.correction": "Attendance correction",
        "hr.leave": "Leave",
        "hr.overtime": "Overtime",
        "hr.offboarding": "Demobilization",
    }.get(instance.record_type, "Review")


def _stage_notice(db, instance, project, stage):
    found = _drawing_parts(db, instance)
    if not found:
        label = _review_title(db, instance, project)
        earlier = [row for row in _stages(db, instance.policy_id) if row.position < stage.position]
        stage_name = (stage.name or "Review").strip()
        if earlier:
            return (
                "Your review is now required",
                f"{label} was approved at the earlier stage. {stage_name} is now waiting for you.",
            )
        return (
            "Your review is required",
            f"{label} was submitted. Later reviewers are notified only after you approve.",
        )
    _drawing, _revision, label = found
    stage_name = (stage.name or stage.purpose or "Review").strip()
    earlier = [row for row in _stages(db, instance.policy_id) if row.position < stage.position]
    if earlier:
        return (
            "Your review is now required",
            f"{label} was approved at the earlier stage. {stage_name} is now waiting for you.",
        )
    return (
        "Your review is required",
        f"{label} was submitted for {stage_name}. Later reviewers are notified only after you approve.",
    )


def _notify_drawing_owner(db, instance, project, title, body, source_key, skip_ids=()):
    found = _drawing_parts(db, instance)
    if not found:
        return
    drawing, _revision, _label = found
    if not drawing.responsible_user_id or drawing.responsible_user_id in skip_ids:
        return
    owner = db.get(User, drawing.responsible_user_id)
    if not owner or not owner.active:
        return
    notify(
        db,
        owner,
        title,
        body,
        source_key,
        project_id=project.id,
        link=f"/projects/{project.id}",
    )


def _open_stage(db, user, project, instance, stage):
    reviewers = _reviewers(db, stage.id)
    if not reviewers:
        raise HTTPException(422, "Mandatory reviewer configuration is missing")
    title, body = _stage_notice(db, instance, project, stage)
    for reviewer in reviewers:
        person = db.get(User, reviewer.user_id)
        if not person or not person.active or person.organization_id != project.organization_id:
            raise HTTPException(422, "Reviewer must be an active user in this organization")
        _task(
            db,
            user,
            project,
            reviewer.user_id,
            _review_title(db, instance, project),
            instance.record_type,
            instance.id,
        )
        notify(
            db,
            person,
            title,
            body,
            f"review:{instance.id}:attempt:{instance.attempt}:stage:{stage.id}:{person.id}",
            project_id=project.id,
            link=f"/projects/{project.id}",
        )


def _review_title(db, instance, project):
    if instance.record_type == "drawing.revision":
        from app.domains.engineering_documents.models import Drawing, DrawingRevision

        revision = db.get(DrawingRevision, instance.record_id)
        drawing = db.get(Drawing, revision.drawing_id) if revision else None
        if drawing and revision:
            return f"Review drawing {drawing.number} rev {revision.code}"
    if instance.record_type == "procurement.requirement":
        from app.domains.supply_chain.models import MaterialRequirement

        row = db.get(MaterialRequirement, instance.record_id)
        if row:
            return f"Review requirement {row.number}"
    if instance.record_type == "procurement.requisition":
        from app.domains.supply_chain.models import PurchaseRequisition

        row = db.get(PurchaseRequisition, instance.record_id)
        if row:
            return f"Review requisition {row.number}"
    if instance.record_type == "procurement.purchase_order":
        from app.domains.supply_chain.models import PurchaseOrder

        row = db.get(PurchaseOrder, instance.record_id)
        if row:
            return f"Review purchase order {row.number}"
    if instance.record_type == "construction.release":
        from app.domains.construction.models import WorkPackage

        row = db.get(WorkPackage, instance.record_id)
        if row:
            return f"Release work package {row.code}"
    if instance.record_type == "construction.resume":
        from app.domains.construction.models import WorkHold, WorkPackage

        hold = db.get(WorkHold, instance.record_id)
        row = db.get(WorkPackage, hold.package_id) if hold else None
        if row:
            return f"Resume work package {row.code}"
    if instance.record_type == "construction.progress":
        from app.domains.construction.models import ProgressReport

        row = db.get(ProgressReport, instance.record_id)
        if row:
            return f"Review daily progress {row.number}"
    if instance.record_type == "construction.handover":
        from app.domains.construction.models import CompletionDossier

        row = db.get(CompletionDossier, instance.record_id)
        if row:
            return f"Review handover {row.number}"
    if instance.record_type == "hse.document":
        from app.domains.hse.models import HseDocument

        row = db.get(HseDocument, instance.record_id)
        if row:
            return f"Review {row.kind} {row.number} rev {row.revision_label}"
    if instance.record_type == "hse.assessment":
        from app.domains.hse.models import HseAssessment

        row = db.get(HseAssessment, instance.record_id)
        if row:
            return f"Review risk assessment {row.number}"
    if instance.record_type == "hse.permit":
        from app.domains.hse.models import HsePermit

        row = db.get(HsePermit, instance.record_id)
        if row:
            return f"Review permit {row.number}"
    if instance.record_type == "hse.incident":
        from app.domains.hse.models import HseIncident

        row = db.get(HseIncident, instance.record_id)
        if row:
            return f"Review incident {row.number}"
    if instance.record_type == "hse.hold":
        from app.domains.hse.models import HseHold

        row = db.get(HseHold, instance.record_id)
        if row:
            return f"Review safety hold {row.number}"
    if instance.record_type == "quality.inspection":
        from app.domains.quality.models import QualityOffer

        row = db.get(QualityOffer, instance.record_id)
        if row:
            return f"Review inspection {row.number}"
    if instance.record_type == "quality.document":
        from app.domains.quality.models import QualityDocument

        row = db.get(QualityDocument, instance.record_id)
        if row:
            return f"Review {row.kind} {row.number} rev {row.revision_label}"
    if instance.record_type == "quality.template":
        from app.domains.quality.models import QualityForm

        row = db.get(QualityForm, instance.record_id)
        if row:
            return f"Review template {row.code} rev {row.revision_label}"
    if instance.record_type == "quality.material":
        from app.domains.quality.models import MaterialInspection

        row = db.get(MaterialInspection, instance.record_id)
        if row:
            return f"Review material inspection {row.number}"
    if instance.record_type == "quality.construction":
        from app.domains.quality.models import ConstructionRequest

        row = db.get(ConstructionRequest, instance.record_id)
        if row:
            return f"Review construction inspection {row.number}"
    if instance.record_type in {"quality.ncr", "quality.ncr.close"}:
        from app.domains.quality.models import Nonconformance

        row = db.get(Nonconformance, instance.record_id)
        if row:
            verb = "Verify NCR" if instance.record_type == "quality.ncr.close" else "Review NCR"
            return f"{verb} {row.number}"
    if instance.record_type == "quality.concession":
        from app.domains.quality.models import Concession

        row = db.get(Concession, instance.record_id)
        if row:
            return f"Review concession {row.number}"
    if instance.record_type == "quality.hold":
        from app.domains.quality.models import QualityHold

        row = db.get(QualityHold, instance.record_id)
        if row:
            return f"Release quality hold {row.number}"
    if instance.record_type == "quality.qualification":
        from app.domains.quality.models import Qualification

        row = db.get(Qualification, instance.record_id)
        if row:
            return f"Review qualification {row.number}"
    if instance.record_type == "quality.calibration":
        from app.domains.quality.models import Calibration

        row = db.get(Calibration, instance.record_id)
        if row:
            return f"Review calibration {row.number}"
    if instance.record_type == "quality.dossier":
        from app.domains.quality.models import QualityDossier

        row = db.get(QualityDossier, instance.record_id)
        if row:
            return f"Review quality dossier {row.number}"
    if instance.record_type == "quality.punch.close":
        from app.domains.quality.models import QualityPunch

        row = db.get(QualityPunch, instance.record_id)
        if row:
            return f"Close punch item {row.number}"
    if instance.record_type == "hr.deployment":
        from app.domains.workforce.models import Deployment, Personnel

        row = db.get(Deployment, instance.record_id)
        person = db.get(Personnel, row.personnel_id) if row else None
        if person:
            return f"Approve mobilization of {person.code}"
    if instance.record_type == "hr.request":
        from app.domains.workforce.models import WorkforceRequest

        row = db.get(WorkforceRequest, instance.record_id)
        if row:
            return f"Review workforce demand {row.number}"
    if instance.record_type == "hr.attendance":
        from app.domains.workforce.models import AttendanceSheet

        row = db.get(AttendanceSheet, instance.record_id)
        if row:
            return f"Review attendance for {row.attendance_date.isoformat()}"
    if instance.record_type == "hr.correction":
        from app.domains.workforce.models import AttendanceCorrection

        row = db.get(AttendanceCorrection, instance.record_id)
        if row:
            return f"Review attendance correction: {row.kind.lower()}"
    if instance.record_type == "hr.leave":
        from app.domains.workforce.models import Leave, Personnel

        row = db.get(Leave, instance.record_id)
        person = db.get(Personnel, row.personnel_id) if row else None
        if person:
            return f"Approve leave for {person.code}"
    if instance.record_type == "hr.offboarding":
        from app.domains.workforce.models import Offboarding, Personnel

        row = db.get(Offboarding, instance.record_id)
        person = db.get(Personnel, row.personnel_id) if row else None
        if person:
            return f"Approve demobilization of {person.code}"
    if instance.record_type == "hr.overtime":
        from app.domains.workforce.models import Overtime

        row = db.get(Overtime, instance.record_id)
        if row:
            return f"Approve overtime for {row.work_date.isoformat()}"
    return f"Review activation for {project.code}"


REVIEW_GUARDS = []


def submit_activation(db, user, project):
    from app.domains.identity_projects.router import validate_project

    data = project_input(db, project, status="Active")
    validate_project(db, user, data)
    policy = active_policy(db, project, ACTIVATION)
    if not policy or not _stages(db, policy.id):
        raise HTTPException(422, "Mandatory reviewer configuration is missing")
    open_review = (
        db.query(ReviewInstance)
        .filter_by(project_id=project.id, record_type=ACTIVATION)
        .filter(ReviewInstance.state.in_(["In Review", "Returned"]))
        .first()
    )
    if open_review:
        raise HTTPException(409, "An activation review is already open")
    instance = ReviewInstance(
        organization_id=user.organization_id,
        project_id=project.id,
        record_type=ACTIVATION,
        record_id=project.id,
        record_version=project.version,
        policy_id=policy.id,
        state="In Review",
        submitted_by=user.id,
    )
    db.add(instance)
    db.flush()
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def _lock(db, instance, version):
    result = db.execute(
        update(ReviewInstance)
        .where(ReviewInstance.id == instance.id, ReviewInstance.version == version)
        .values(version=version + 1)
    )
    if result.rowcount != 1:
        raise HTTPException(409, "This review changed. Reload it and try again")
    db.refresh(instance)


def decide(db, user, instance, action, reason, comment, version):
    from app.domains.identity_projects.router import audit

    allowed = {"approve", "reject", "return", "comment"}
    if instance.record_type == "drawing.revision":
        allowed.add("approve_with_comments")
    if action not in allowed:
        raise HTTPException(422, "Unknown review action")
    if action in {"reject", "return", "approve_with_comments"} and not reason.strip():
        raise HTTPException(422, "A reason is required")
    project = db.get(Project, instance.project_id)
    db.refresh(project)
    _project_visible(db, user, project)
    policy = db.get(ApprovalPolicy, instance.policy_id)
    stage = current_stage(db, instance)
    if instance.state != "In Review" or not stage:
        raise HTTPException(409, "This review is not awaiting a decision")
    reviewer_ids = {row.user_id for row in _reviewers(db, stage.id)}
    if user.id not in reviewer_ids:
        raise HTTPException(403, "You are not a reviewer for this stage")
    if any(
        row.reviewer_id == user.id and row.action != "comment"
        for row in _decisions(db, instance, stage.id)
    ) and action != "comment":
        raise HTTPException(409, "You already decided this attempt")
    if (
        user.id == instance.submitted_by
        and not policy.allow_self_approval
        and action in {"approve", "approve_with_comments"}
    ):
        raise HTTPException(403, "You cannot approve your own submission")
    for guard in REVIEW_GUARDS:
        guard(db, user, instance, stage, action)
    if (
        instance.record_type == ACTIVATION
        and action == "approve"
        and project.version != instance.record_version
    ):
        raise HTTPException(
            409, "The project changed after submission. Return it for correction"
        )
    _lock(db, instance, version)
    stage = current_stage(db, instance)
    if not stage or user.id not in {row.user_id for row in _reviewers(db, stage.id)}:
        raise HTTPException(409, "This review changed. Reload it and try again")
    db.add(
        ReviewDecision(
            instance_id=instance.id,
            stage_id=stage.id,
            reviewer_id=user.id,
            action=action,
            reason=reason,
            comment=comment,
            reviewed_revision=instance.record_version,
            attempt=instance.attempt,
        )
    )
    db.flush()
    if action == "comment":
        return instance
    if action in {"reject", "return"}:
        instance.state = "Rejected" if action == "reject" else "Returned"
        _close_tasks(db, project.id, instance.record_type, instance.id, "Cancelled", f"Review {action}")
        _apply_domain(db, user, instance, project, action)
        subject = _notice_subject(instance)
        if action == "return" and instance.record_type == ACTIVATION:
            _task(
                db,
                user,
                project,
                instance.submitted_by,
                f"Correct activation for {project.code}",
                ACTIVATION,
                instance.id,
            )
        submitter = db.get(User, instance.submitted_by)
        found = _drawing_parts(db, instance)
        title = f"{subject} returned" if action == "return" else f"{subject} rejected"
        body = reason
        if found:
            _drawing, _revision, label = found
            title = "Drawing returned" if action == "return" else "Drawing rejected"
            body = f"{label}: {reason}. The owner prepares the next revision."
        notify(
            db,
            submitter,
            title,
            body,
            f"review:{instance.id}:attempt:{instance.attempt}:{action}",
            project_id=project.id,
            link=f"/projects/{project.id}",
        )
        _notify_drawing_owner(
            db,
            instance,
            project,
            "Drawing returned to you" if action == "return" else "Drawing rejected",
            body,
            f"review:{instance.id}:attempt:{instance.attempt}:{action}:owner",
            skip_ids={instance.submitted_by},
        )
        audit(
            db,
            user,
            action,
            "reviews",
            instance.id,
            {"reason": reason, "revision": instance.record_version},
            project_id=project.id,
        )
        return instance
    nxt = current_stage(db, instance)
    if nxt is None:
        if instance.record_type == ACTIVATION:
            apply_activation(db, user, project, instance.record_version)
        instance.state = "Approved"
        _apply_domain(db, user, instance, project, action)
        submitter = db.get(User, instance.submitted_by)
        subject = _notice_subject(instance)
        notify(
            db,
            submitter,
            f"{subject} approved",
            project.code,
            f"review:{instance.id}:approved",
            project_id=project.id,
            link=f"/projects/{project.id}",
        )
        _close_tasks(
            db, project.id, instance.record_type, instance.id, "Completed", "Review completed"
        )
    else:
        _close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Stage finished")
        _open_stage(db, user, project, instance, nxt)
        _apply_domain(db, user, instance, project, "advance", nxt)
        found = _drawing_parts(db, instance)
        if found:
            _drawing, _revision, label = found
            names = []
            for row in _reviewers(db, nxt.id):
                person = db.get(User, row.user_id)
                if person:
                    names.append(person.name)
            _notify_drawing_owner(
                db,
                instance,
                project,
                "Review moved to the next person",
                f"{label} was approved. {', '.join(names) or nxt.name} is now notified.",
                f"review:{instance.id}:attempt:{instance.attempt}:advanced:{nxt.id}:owner",
                skip_ids={row.user_id for row in _reviewers(db, nxt.id)},
            )
    audit(
        db,
        user,
        action,
        "reviews",
        instance.id,
        {"revision": instance.record_version},
        project_id=project.id,
    )
    return instance


def _apply_domain(db, user, instance, project, action, stage=None):
    if instance.record_type == "drawing.revision":
        from app.domains.engineering_documents.workflow import on_review_event

        on_review_event(db, user, instance, project, action, stage)
        return
    if instance.record_type in {"procurement.requirement", "procurement.requisition", "procurement.purchase_order"}:
        from app.domains.supply_chain.service import on_review_event as procurement_event

        procurement_event(db, user, instance, project, action, stage)
        return
    if instance.record_type == "construction.release":
        from app.domains.construction.readiness import on_review_event as release_event

        release_event(db, user, instance, project, action, stage)
        return
    if instance.record_type == "construction.progress":
        from app.domains.construction.progress import on_review_event as progress_event

        progress_event(db, user, instance, project, action, stage)
        return
    if instance.record_type == "construction.resume":
        from app.domains.construction.monitoring import on_review_event as resume_event

        resume_event(db, user, instance, project, action, stage)
        return
    if instance.record_type == "construction.handover":
        from app.domains.construction.handover import on_review_event as handover_event

        handover_event(db, user, instance, project, action, stage)
        return
    if instance.record_type == "quality.inspection":
        from app.domains.quality.service import on_review_event as inspection_event

        inspection_event(db, user, instance, project, action, stage)
        return
    if instance.record_type in {"quality.document", "quality.template"}:
        from app.domains.quality.plans import on_review_event as plan_event

        plan_event(db, user, instance, project, action, stage)
        return
    if instance.record_type == "quality.material":
        from app.domains.quality.material import on_review_event as material_event

        material_event(db, user, instance, project, action, stage)
        return
    if instance.record_type == "quality.construction":
        from app.domains.quality.requests import on_review_event as construction_event

        construction_event(db, user, instance, project, action, stage)
        return
    if instance.record_type in {"quality.ncr", "quality.ncr.close", "quality.concession", "quality.hold"}:
        from app.domains.quality.findings import on_review_event as finding_event

        finding_event(db, user, instance, project, action, stage)
        return
    if instance.record_type in {"quality.qualification", "quality.calibration"}:
        from app.domains.quality.competence import on_review_event as competence_event

        competence_event(db, user, instance, project, action, stage)
        return
    if instance.record_type in {"quality.dossier", "quality.punch.close"}:
        from app.domains.quality.dossiers import on_review_event as dossier_event

        dossier_event(db, user, instance, project, action, stage)
        return
    if instance.record_type in {"hse.document", "hse.assessment"}:
        from app.domains.hse.service import on_review_event as hse_event

        hse_event(db, user, instance, project, action, stage)
        return
    if instance.record_type == "hse.permit":
        from app.domains.hse.permits import on_review_event as permit_event

        permit_event(db, user, instance, project, action, stage)
        return
    if instance.record_type == "hse.incident":
        from app.domains.hse.incidents import on_review_event as incident_event

        incident_event(db, user, instance, project, action, stage)
        return
    if instance.record_type == "hse.hold":
        from app.domains.hse.holds import on_review_event as hold_event

        hold_event(db, user, instance, project, action, stage)
        return
    if instance.record_type in {"hr.deployment", "hr.request"}:
        from app.domains.workforce.deployments import on_review_event as workforce_event

        workforce_event(db, user, instance, project, action, stage)
    if instance.record_type in {"hr.attendance", "hr.correction"}:
        from app.domains.workforce.attendance import on_review_event as attendance_event

        attendance_event(db, user, instance, project, action, stage)
    if instance.record_type in {"hr.leave", "hr.overtime"}:
        from app.domains.workforce.leave import on_review_event as leave_event

        leave_event(db, user, instance, project, action, stage)
    if instance.record_type == "hr.offboarding":
        from app.domains.workforce.offboarding import on_review_event as offboarding_event

        offboarding_event(db, user, instance, project, action, stage)


def resubmit(db, user, instance, version):
    if instance.record_type == "construction.release":
        from app.domains.construction.readiness import apply_resubmit

        apply_resubmit(db, user, instance, version)
        return instance
    if instance.record_type == "construction.progress":
        from app.domains.construction.progress import apply_resubmit as resubmit_progress

        resubmit_progress(db, user, instance, version)
        return instance
    if instance.record_type == "construction.resume":
        from app.domains.construction.monitoring import apply_resubmit as resubmit_hold

        resubmit_hold(db, user, instance, version)
        return instance
    if instance.record_type == "construction.handover":
        from app.domains.construction.handover import apply_resubmit as resubmit_dossier

        resubmit_dossier(db, user, instance, version)
        return instance
    if instance.record_type == "quality.inspection":
        from app.domains.quality.service import apply_resubmit as resubmit_offer

        resubmit_offer(db, user, instance, version)
        return instance
    if instance.record_type in {"quality.document", "quality.template"}:
        from app.domains.quality.plans import apply_resubmit as resubmit_plan

        resubmit_plan(db, user, instance, version)
        return instance
    if instance.record_type == "quality.material":
        from app.domains.quality.material import apply_resubmit as resubmit_material

        resubmit_material(db, user, instance, version)
        return instance
    if instance.record_type == "quality.construction":
        from app.domains.quality.requests import apply_resubmit as resubmit_construction

        resubmit_construction(db, user, instance, version)
        return instance
    if instance.record_type in {"quality.ncr", "quality.ncr.close", "quality.concession", "quality.hold"}:
        from app.domains.quality.findings import apply_resubmit as resubmit_finding

        resubmit_finding(db, user, instance, version)
        return instance
    if instance.record_type in {"quality.qualification", "quality.calibration"}:
        from app.domains.quality.competence import apply_resubmit as resubmit_competence

        resubmit_competence(db, user, instance, version)
        return instance
    if instance.record_type in {"quality.dossier", "quality.punch.close"}:
        from app.domains.quality.dossiers import apply_resubmit as resubmit_dossier

        resubmit_dossier(db, user, instance, version)
        return instance
    if instance.record_type in {"hse.document", "hse.assessment"}:
        from app.domains.hse.service import apply_resubmit as resubmit_hse

        resubmit_hse(db, user, instance, version)
        return instance
    if instance.record_type == "hse.permit":
        from app.domains.hse.permits import apply_resubmit as resubmit_permit

        resubmit_permit(db, user, instance, version)
        return instance
    if instance.record_type == "hse.incident":
        from app.domains.hse.incidents import apply_resubmit as resubmit_incident

        resubmit_incident(db, user, instance, version)
        return instance
    if instance.record_type == "hse.hold":
        from app.domains.hse.holds import apply_resubmit as resubmit_hold

        resubmit_hold(db, user, instance, version)
        return instance
    if instance.record_type in {"hr.deployment", "hr.request"}:
        from app.domains.workforce.deployments import apply_resubmit as resubmit_workforce

        resubmit_workforce(db, user, instance, version)
        return instance
    if instance.record_type in {"hr.attendance", "hr.correction"}:
        from app.domains.workforce.attendance import apply_resubmit as resubmit_attendance

        resubmit_attendance(db, user, instance, version)
        return instance
    if instance.record_type in {"hr.leave", "hr.overtime"}:
        from app.domains.workforce.leave import apply_resubmit as resubmit_leave

        resubmit_leave(db, user, instance, version)
        return instance
    if instance.record_type == "hr.offboarding":
        from app.domains.workforce.offboarding import apply_resubmit as resubmit_offboarding

        resubmit_offboarding(db, user, instance, version)
        return instance
    project = db.get(Project, instance.project_id)
    if instance.record_type != ACTIVATION:
        raise HTTPException(409, "Create a corrected revision instead of resubmitting this file")
    if instance.state != "Returned":
        raise HTTPException(409, "Only a returned review can be resubmitted")
    if user.id != instance.submitted_by and not user.organization_admin:
        raise HTTPException(403, "Only the submitter can resubmit")
    from app.domains.identity_projects.router import validate_project

    db.refresh(project)
    validate_project(db, user, project_input(db, project, status="Active"))
    _lock(db, instance, version)
    _close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    instance.record_version = project.version
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def review_chain(db, instance):
    stages = _stages(db, instance.policy_id)
    current = current_stage(db, instance)
    seen_current = False
    chain = []
    for stage in stages:
        people = []
        for row in _reviewers(db, stage.id):
            person = db.get(User, row.user_id)
            if person:
                people.append({"id": person.id, "name": person.name})
        stopped = any(row.action in {"reject", "return"} for row in _decisions(db, instance, stage.id))
        if stopped:
            status = "stopped"
            seen_current = True
        elif current and stage.id == current.id:
            status = "current"
            seen_current = True
        elif not seen_current and (current or instance.state == "Approved"):
            status = "done"
        else:
            status = "waiting"
        chain.append(
            {
                "name": stage.name,
                "purpose": stage.purpose or "",
                "status": status,
                "reviewers": people,
            }
        )
    return chain


def review_payload(db, user, instance):
    policy = db.get(ApprovalPolicy, instance.policy_id)
    stage = current_stage(db, instance)
    actions = []
    if stage and user.id in {row.user_id for row in _reviewers(db, stage.id)}:
        if not (user.id == instance.submitted_by and not policy.allow_self_approval):
            actions = ["approve", "reject", "return", "comment"]
            if instance.record_type == "drawing.revision":
                actions.insert(1, "approve_with_comments")
        else:
            actions = ["reject", "return", "comment"]
    if (
        instance.record_type in {ACTIVATION, "construction.release", "construction.progress", "construction.resume", "construction.handover", "quality.inspection", "quality.document", "quality.template", "quality.material", "quality.construction", "quality.ncr", "quality.ncr.close", "quality.concession", "quality.hold", "quality.qualification", "quality.calibration", "quality.dossier", "quality.punch.close", "hse.document", "hse.assessment", "hse.permit", "hse.incident", "hse.hold", "hr.deployment", "hr.request", "hr.attendance", "hr.correction", "hr.leave", "hr.overtime", "hr.offboarding"}
        and instance.state == "Returned"
        and (user.id == instance.submitted_by or user.organization_admin)
    ):
        actions.append("resubmit")
    decisions = (
        db.query(ReviewDecision)
        .filter_by(instance_id=instance.id)
        .order_by(ReviewDecision.id)
        .all()
    )
    reviewers = []
    if stage:
        for row in _reviewers(db, stage.id):
            person = db.get(User, row.user_id)
            if person:
                reviewers.append({"id": person.id, "name": person.name})
    project = db.get(Project, instance.project_id)
    names = {
        row.reviewer_id: db.get(User, row.reviewer_id)
        for row in decisions
    }
    return dict(
        id=instance.id,
        project_id=instance.project_id,
        record_type=instance.record_type,
        record_id=instance.record_id,
        state=instance.state,
        attempt=instance.attempt,
        record_version=instance.record_version,
        submitted_by=instance.submitted_by,
        version=instance.version,
        subject=_review_title(db, instance, project) if project else instance.record_type,
        stage_purpose=stage.purpose if stage else "",
        reviewers=reviewers,
        chain=review_chain(db, instance),
        actions=actions,
        decisions=[
            dict(
                id=row.id,
                action=row.action,
                reason=row.reason,
                comment=row.comment,
                reviewer_id=row.reviewer_id,
                reviewer_name=names[row.reviewer_id].name if names.get(row.reviewer_id) else "",
                reviewed_revision=row.reviewed_revision,
                attempt=row.attempt,
                created_at=row.created_at,
            )
            for row in decisions
        ],
    )


def change_task(db, user, task, status, evidence, owner_id, version):
    if task.organization_id != user.organization_id:
        raise HTTPException(404, "Task not found")
    project = db.get(Project, task.project_id)
    _project_visible(db, user, project)
    allowed = {task.owner_id, task.creator_id}
    if user.id not in allowed and not user.organization_admin:
        raise HTTPException(403, "You cannot change this task")
    if task.source_type in ("stores.qa_revocation.construction_review", "stores.material_return.exception_review"):
        # All changes (including evidence, reassignment and nonterminal status)
        # must use the domain workflow. Otherwise My Tasks can overwrite the
        # acknowledgment evidence later relied upon by independent QA review.
        raise HTTPException(409, "Use Construction acknowledgment and independent QA verification workflow")
    if status not in TASK_MOVES:
        raise HTTPException(422, "Unknown task status")
    if status != task.status and status not in TASK_MOVES[task.status]:
        raise HTTPException(409, "That task status change is not allowed")
    if status == "Completed" and not (evidence or "").strip():
        raise HTTPException(422, "Completion evidence is required")
    if owner_id and owner_id != task.owner_id:
        if user.id != task.creator_id and not user.organization_admin and user.id != task.owner_id:
            raise HTTPException(403, "You cannot reassign this task")
        person = db.get(User, owner_id)
        if not person or person.organization_id != user.organization_id:
            raise HTTPException(422, "Assignee must belong to this organization")
        task.owner_id = owner_id
        notify(
            db,
            person,
            "Task reassigned",
            task.title,
            f"task:{task.id}:reassigned:{person.id}:{version}",
            project_id=task.project_id,
            link=f"/projects/{task.project_id}",
        )
    result = db.execute(
        update(Task)
        .where(Task.id == task.id, Task.version == version)
        .values(
            status=status,
            evidence=evidence if evidence is not None else task.evidence,
            owner_id=task.owner_id,
            version=version + 1,
        )
    )
    if result.rowcount != 1:
        raise HTTPException(409, "Task changed. Reload it and try again")
    db.refresh(task)
    return task
