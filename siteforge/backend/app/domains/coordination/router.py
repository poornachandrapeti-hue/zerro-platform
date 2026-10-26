from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.identity_projects.models import Project, User
from app.domains.identity_projects.router import audit, commit
from app.domains.identity_projects.security import admin, authenticated, permitted
from .models import (
    ApprovalPolicy,
    Job,
    Notification,
    PolicyReviewer,
    PolicyStage,
    ReminderPolicy,
    ReviewInstance,
    Task,
)
from .schemas import DecisionIn, PolicyIn, ReminderIn, ResubmitIn, TaskIn, TaskUpdate
from .service import (
    ACTIVATION,
    change_task,
    decide,
    resubmit,
    review_payload,
    save_policy,
    submit_activation,
    _task,
)

router = APIRouter(prefix="/api")


def _project(db, user, pid):
    project = db.get(Project, pid)
    if not project or project.organization_id != user.organization_id:
        raise HTTPException(404, "Project not found")
    if not user.organization_admin:
        permitted(db, user, project, "projects.view")
    return project


@router.get("/projects/{pid}/approval-policies")
def list_policies(
    pid: int,
    record_type: str = "drawing.revision",
    u: User = Depends(admin),
    db: Session = Depends(get_db),
):
    project = _project(db, u, pid)
    rows = (
        db.query(ApprovalPolicy)
        .filter_by(project_id=project.id, record_type=record_type, active=True)
        .order_by(ApprovalPolicy.id.desc())
        .all()
    )
    result = []
    for policy in rows:
        stages = (
            db.query(PolicyStage)
            .filter_by(policy_id=policy.id)
            .order_by(PolicyStage.position)
            .all()
        )
        result.append(
            {
                "id": policy.id,
                "discipline_id": policy.discipline_id,
                "policy_version": policy.policy_version,
                "stages": [
                    {
                        "name": stage.name,
                        "purpose": stage.purpose,
                        "rule": stage.rule,
                        "quorum_count": stage.quorum_count,
                        "reviewers": [
                            {
                                "id": person.id,
                                "name": person.name,
                                "approval_limit": reviewer.approval_limit,
                            }
                            for reviewer in db.query(PolicyReviewer).filter_by(
                                stage_id=stage.id
                            )
                            if (person := db.get(User, reviewer.user_id))
                        ],
                    }
                    for stage in stages
                ],
            }
        )
    return result


@router.post("/projects/{pid}/approval-policies", status_code=201)
def create_policy(
    pid: int,
    data: PolicyIn,
    u: User = Depends(admin),
    db: Session = Depends(get_db),
):
    project = _project(db, u, pid)
    if data.record_type not in {
        ACTIVATION,
        "drawing.revision",
        "procurement.requirement",
        "procurement.requisition",
        "procurement.purchase_order",
        "construction.release",
        "construction.progress",
        "construction.handover",
        "quality.inspection",
        "quality.document",
        "quality.template",
        "quality.material",
        "quality.construction",
        "quality.ncr",
        "quality.ncr.close",
        "quality.concession",
        "quality.hold",
        "quality.qualification",
        "quality.calibration",
        "quality.dossier",
        "quality.punch.close",
        "hse.document",
        "hse.assessment",
        "hse.permit",
        "hse.incident",
        "hse.hold",
        "hr.deployment",
        "hr.request",
        "hr.attendance",
        "hr.correction",
        "hr.leave",
        "hr.overtime",
        "hr.offboarding",
    }:
        raise HTTPException(422, "That record type does not have a review policy")
    if data.record_type.startswith("procurement."):
        from app.domains.supply_chain.service import validate_procurement_policy

        validate_procurement_policy(db, project, data)
    if data.record_type in {
        "construction.release",
        "construction.progress",
        "construction.handover",
        "quality.inspection",
        "quality.document",
        "quality.template",
        "quality.material",
        "quality.construction",
        "quality.ncr",
        "quality.ncr.close",
        "quality.concession",
        "quality.hold",
        "quality.qualification",
        "quality.calibration",
        "quality.dossier",
        "quality.punch.close",
        "hse.document",
        "hse.assessment",
        "hse.permit",
        "hse.incident",
        "hse.hold",
        "hr.deployment",
        "hr.request",
        "hr.attendance",
        "hr.correction",
        "hr.leave",
        "hr.overtime",
        "hr.offboarding",
    }:
        from app.domains.construction.readiness import validate_construction_policy

        validate_construction_policy(db, project, data)
    for stage in data.stages:
        if stage.rule not in {"all", "quorum"}:
            raise HTTPException(422, "Stage rule must be all or quorum")
    if data.record_type == "drawing.revision":
        from app.domains.engineering_documents.workflow import validate_drawing_policy

        validate_drawing_policy(db, project, data)
    policy = save_policy(db, u, project, data)
    audit(db, u, "create", "approval_policies", policy.id, project_id=pid)
    commit(db)
    return {"id": policy.id, "policy_version": policy.policy_version}


@router.post("/projects/{pid}/activation-reviews", status_code=201)
def submit(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    if not u.organization_admin:
        permitted(db, u, project, "projects.edit")
    instance = submit_activation(db, u, project)
    audit(db, u, "submit", "reviews", instance.id, project_id=pid)
    commit(db)
    return review_payload(db, u, instance)


@router.get("/reviews")
def inbox(u: User = Depends(authenticated), db: Session = Depends(get_db)):
    rows = (
        db.query(ReviewInstance)
        .filter_by(organization_id=u.organization_id)
        .order_by(ReviewInstance.id.desc())
        .all()
    )
    visible = []
    for row in rows:
        try:
            _project(db, u, row.project_id)
        except HTTPException:
            continue
        payload = review_payload(db, u, row)
        if payload["actions"] or row.submitted_by == u.id or u.organization_admin:
            payload["project_id"] = row.project_id
            visible.append(payload)
    return visible


@router.get("/projects/{pid}/reviews")
def reviews(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _project(db, u, pid)
    rows = (
        db.query(ReviewInstance)
        .filter_by(project_id=pid, record_type=ACTIVATION)
        .order_by(ReviewInstance.id.desc())
        .all()
    )
    return [review_payload(db, u, row) for row in rows]


@router.post("/reviews/{rid}/decisions")
def decision(
    rid: int,
    data: DecisionIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    instance = db.get(ReviewInstance, rid)
    if not instance or instance.organization_id != u.organization_id:
        raise HTTPException(404, "Review not found")
    decide(db, u, instance, data.action, data.reason, data.comment, data.version)
    commit(db)
    return review_payload(db, u, instance)


@router.post("/reviews/{rid}/resubmit")
def resubmit_review(
    rid: int,
    data: ResubmitIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    instance = db.get(ReviewInstance, rid)
    if not instance or instance.organization_id != u.organization_id:
        raise HTTPException(404, "Review not found")
    resubmit(db, u, instance, data.version)
    audit(db, u, "resubmit", "reviews", instance.id, project_id=instance.project_id)
    commit(db)
    return review_payload(db, u, instance)


@router.post("/projects/{pid}/reminder-policies", status_code=201)
def reminders(
    pid: int, data: ReminderIn, u: User = Depends(admin), db: Session = Depends(get_db)
):
    project = _project(db, u, pid)
    for recipient_id in data.recipient_ids:
        person = db.get(User, recipient_id)
        if (
            not person
            or person.organization_id != u.organization_id
            or not person.active
        ):
            raise HTTPException(
                422, "Escalation recipient must be an active user in this organization"
            )
    row = (
        db.query(ReminderPolicy)
        .filter_by(project_id=pid, record_type=data.record_type)
        .first()
    )
    if not row:
        row = ReminderPolicy(project_id=pid, record_type=data.record_type)
        db.add(row)
    row.reminder_hours = data.reminder_hours
    row.escalate_after_hours = data.escalate_after_hours
    row.recipient_ids = data.recipient_ids
    audit(db, u, "update", "reminder_policies", pid, project_id=project.id)
    commit(db)
    return {"ok": True}


@router.get("/projects/{pid}/tasks")
def project_tasks(
    pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    _project(db, u, pid)
    rows = db.query(Task).filter_by(project_id=pid).order_by(Task.id.desc()).all()
    return [_task_dict(row) for row in rows]


@router.get("/tasks")
def my_tasks(u: User = Depends(authenticated), db: Session = Depends(get_db)):
    rows = (
        db.query(Task)
        .filter_by(organization_id=u.organization_id, owner_id=u.id)
        .order_by(Task.id.desc())
        .all()
    )
    return [_task_dict(row) for row in rows]


@router.post("/projects/{pid}/tasks", status_code=201)
def create_task(
    pid: int,
    data: TaskIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    project = _project(db, u, pid)
    if not u.organization_admin:
        permitted(db, u, project, "projects.edit")
    owner = db.get(User, data.owner_id)
    if not owner or owner.organization_id != u.organization_id:
        raise HTTPException(422, "Assignee must belong to this organization")
    due = date.fromisoformat(data.due_date) if data.due_date else None
    task = _task(
        db, u, project, data.owner_id, data.title, "task", 0, data.priority, due
    )
    audit(db, u, "create", "tasks", task.id, project_id=pid)
    commit(db)
    return _task_dict(task)


@router.post("/tasks/{tid}")
def update_task(
    tid: int,
    data: TaskUpdate,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    task = db.get(Task, tid)
    if not task or task.organization_id != u.organization_id:
        raise HTTPException(404, "Task not found")
    change_task(db, u, task, data.status, data.evidence, data.owner_id, data.version)
    commit(db)
    return _task_dict(task)


@router.get("/jobs")
def jobs(u: User = Depends(admin), db: Session = Depends(get_db)):
    rows = db.query(Job).order_by(Job.id.desc()).limit(50).all()
    return [
        dict(
            id=row.id,
            kind=row.kind,
            status=row.status,
            attempts=row.attempts,
            last_error=row.last_error,
            run_at=row.run_at,
        )
        for row in rows
    ]


@router.get("/notifications")
def notifications(u: User = Depends(authenticated), db: Session = Depends(get_db)):
    rows = (
        db.query(Notification)
        .filter_by(user_id=u.id)
        .order_by(Notification.id.desc())
        .limit(50)
        .all()
    )
    return [_note(row) for row in rows]


@router.get("/notifications/unread-count")
def unread(u: User = Depends(authenticated), db: Session = Depends(get_db)):
    total = (
        db.query(Notification)
        .filter_by(user_id=u.id)
        .filter(Notification.read_at.is_(None))
        .count()
    )
    return {"unread": total}


@router.post("/notifications/{nid}/read")
def mark_read(
    nid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    row = db.get(Notification, nid)
    if not row or row.user_id != u.id:
        raise HTTPException(404, "Notification not found")
    row.read_at = datetime.now(timezone.utc)
    commit(db)
    return _note(row)


def _task_dict(row: Task):
    return dict(
        id=row.id,
        project_id=row.project_id,
        title=row.title,
        owner_id=row.owner_id,
        creator_id=row.creator_id,
        priority=row.priority,
        due_date=row.due_date,
        status=row.status,
        evidence=row.evidence,
        source_type=row.source_type,
        source_id=row.source_id,
        version=row.version,
    )


def _note(row: Notification):
    return dict(
        id=row.id,
        title=row.title,
        body=row.body,
        link=row.link,
        project_id=row.project_id,
        read=row.read_at is not None,
        created_at=row.created_at,
    )
