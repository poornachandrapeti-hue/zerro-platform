import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.db import SessionLocal
from .models import Job, Notification, Task

HANDLERS = {}


def notify(db, user, title, body, source_key, project_id=None, link=""):
    existing = (
        db.query(Notification)
        .filter_by(user_id=user.id, source_key=source_key)
        .first()
    )
    if existing:
        return existing
    row = Notification(
        organization_id=user.organization_id,
        user_id=user.id,
        project_id=project_id,
        title=title,
        body=body,
        link=link,
        source_key=source_key,
    )
    db.add(row)
    db.flush()
    return row


def enqueue(db, kind, payload, dedupe_key, run_at):
    if db.query(Job).filter_by(dedupe_key=dedupe_key).first():
        return
    db.add(
        Job(
            kind=kind,
            payload=payload,
            dedupe_key=dedupe_key,
            run_at=run_at,
            status="pending",
        )
    )


def process_jobs(db):
    try:
        from app.domains.engineering_documents.workflow import scan_overdue

        scan_overdue(db)
        db.commit()
    except Exception:
        db.rollback()
    try:
        from app.domains.workforce.monitor import scan as scan_workforce

        scan_workforce(db)
        db.commit()
    except Exception:
        db.rollback()
    try:
        from app.domains.progress_monitoring.monitor import scan as scan_progress
        scan_progress(db)
    except Exception:
        db.rollback()
    now = datetime.now(timezone.utc)
    ids = [
        job.id
        for job in db.query(Job).filter(Job.status == "pending", Job.run_at <= now)
    ]
    for job_id in ids:
        claimed = db.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == "pending")
            .values(status="running", attempts=Job.attempts + 1)
        )
        if claimed.rowcount != 1:
            db.rollback()
            continue
        db.commit()
        job = db.get(Job, job_id)
        try:
            HANDLERS[job.kind](db, job)
            job.status = "succeeded"
            job.last_error = ""
            db.commit()
        except Exception as exc:
            db.rollback()
            job = db.get(Job, job_id)
            job.last_error = str(exc)[:400]
            job.status = "failed" if (job.attempts or 0) >= 3 else "pending"
            db.commit()


def remind(db, job):
    task = db.get(Task, job.payload["task_id"])
    if not task or task.status in {"Completed", "Cancelled"}:
        return
    from app.domains.identity_projects.models import User

    owner = db.get(User, task.owner_id)
    notify(
        db,
        owner,
        "Task due",
        task.title,
        f"task:{task.id}:overdue",
        project_id=task.project_id,
        link=f"/projects/{task.project_id}/tasks",
    )


def escalate(db, job):
    task = db.get(Task, job.payload["task_id"])
    if not task or task.status in {"Completed", "Cancelled"}:
        return
    from app.domains.identity_projects.models import User

    for user_id in job.payload.get("recipient_ids", []):
        person = db.get(User, user_id)
        if not person or person.organization_id != task.organization_id:
            continue
        notify(
            db,
            person,
            "Task escalated",
            f"{task.title}. Escalation adds visibility and does not grant approval.",
            f"task:{task.id}:escalated:{person.id}",
            project_id=task.project_id,
            link=f"/projects/{task.project_id}/tasks",
        )


def credential_alert(db, job):
    from app.domains.workforce.credentials import alert

    alert(db, job)


HANDLERS["task.remind"] = remind
HANDLERS["task.escalate"] = escalate
HANDLERS["hr.credential.alert"] = credential_alert


def schedule_task(db, task, reminder_hours, escalate_after_hours, recipient_ids):
    if not task.due_date:
        return
    due = datetime.combine(task.due_date, datetime.min.time(), timezone.utc)
    enqueue(
        db,
        "task.remind",
        {"task_id": task.id},
        f"remind:{task.id}",
        due - timedelta(hours=reminder_hours),
    )
    enqueue(
        db,
        "task.escalate",
        {"task_id": task.id, "recipient_ids": recipient_ids},
        f"escalate:{task.id}",
        due + timedelta(hours=escalate_after_hours),
    )


def main():
    while True:
        with SessionLocal() as db:
            process_jobs(db)
        time.sleep(15)


if __name__ == "__main__":
    main()
