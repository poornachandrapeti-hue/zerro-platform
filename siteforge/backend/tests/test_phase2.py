from datetime import date, datetime, timedelta, timezone

from app.config import settings
from app.domains.coordination.jobs import HANDLERS, enqueue, notify, process_jobs
from app.domains.coordination.models import Job, Notification
from app.domains.identity_projects.models import User
from .conftest import sign_in
from .test_foundation import new_project


def complete(c, **extra):
    me = c.get("/api/auth/me").json()["user"]
    discipline = c.get("/api/catalog").json()["disciplines"][0]["id"]
    body = dict(
        code="ACT-1",
        name="Activation",
        client_company_id=me["company_id"],
        lead_pm_id=me["id"],
        discipline_ids=[discipline],
        site_name="Site",
        state="AP",
        city="Vizag",
        planned_start="2026-01-01",
        planned_finish="2027-01-01",
        actual_start="2026-01-02",
    )
    body.update(extra)
    response = c.post("/api/projects", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_status_change_is_a_command(env):
    c, _ = env
    sign_in(c)
    pid = new_project(c).json()["id"]
    current = c.get(f"/api/projects/{pid}").json()
    body = {
        key: value
        for key, value in current.items()
        if key not in ["id", "created_by", "created_at", "modified_at", "modified_by", "client_name", "lead_pm_name"]
    }
    body["status"] = "Cancelled"
    body["cancellation_reason"] = "no"
    assert c.put(f"/api/projects/{pid}", json=body).status_code == 409


def test_activation_return_and_approve(env):
    c, maker = env
    sign_in(c)
    bare = new_project(c, code="BARE").json()
    assert c.post(f"/api/projects/{bare['id']}/activation-reviews").status_code == 422
    project = complete(c)
    pid = project["id"]
    assert c.post(f"/api/projects/{pid}/activation-reviews").status_code == 422
    with maker() as db:
        reviewer = db.query(User).filter_by(email="viewer@alpha.test").one()
        reviewer_id = reviewer.id
    assert (
        c.post(
            f"/api/projects/{pid}/approval-policies",
            json={
                "record_type": "project.activation",
                "allow_self_approval": False,
                "stages": [
                    {"name": "Check", "rule": "all", "reviewer_ids": [reviewer_id]}
                ],
            },
        ).status_code
        == 201
    )
    role_id = next(
        role["id"] for role in c.get("/api/catalog").json()["roles"] if role["name"] == "Viewer"
    )
    assert (
        c.post(
            f"/api/projects/{pid}/memberships",
            json={
                "user_id": reviewer_id,
                "role_id": role_id,
                "company_id": project["client_company_id"],
                "scope": "ALL",
                "discipline_ids": [],
            },
        ).status_code
        == 201
    )
    submitted = c.post(f"/api/projects/{pid}/activation-reviews")
    assert submitted.status_code == 201, submitted.text
    review = submitted.json()
    assert "approve" not in review["actions"]
    sign_in(c, "viewer@alpha.test")
    assert (
        c.post(
            f"/api/reviews/{review['id']}/decisions",
            json={"action": "return", "reason": "", "version": review["version"]},
        ).status_code
        == 422
    )
    returned = c.post(
        f"/api/reviews/{review['id']}/decisions",
        json={"action": "return", "reason": "Add the gate note", "version": review["version"]},
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["state"] == "Returned"
    assert c.get(f"/api/projects/{pid}").json()["status"] == "Draft"
    sign_in(c)
    assert (
        c.post(
            f"/api/reviews/{review['id']}/resubmit",
            json={"version": review["version"]},
        ).status_code
        == 409
    )
    again = c.post(
        f"/api/reviews/{review['id']}/resubmit",
        json={"version": returned.json()["version"]},
    )
    assert again.status_code == 200, again.text
    assert again.json()["attempt"] == 2
    sign_in(c, "viewer@alpha.test")
    approved = c.post(
        f"/api/reviews/{review['id']}/decisions",
        json={"action": "approve", "version": again.json()["version"]},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"] == "Approved"
    assert len(approved.json()["decisions"]) >= 2
    assert c.get(f"/api/projects/{pid}").json()["status"] == "Active"
    titles = [task["title"] for task in c.get("/api/tasks").json()]
    assert any("activation" in title.lower() for title in titles)
    notes = c.get("/api/notifications").json()
    assert notes
    assert c.post(f"/api/notifications/{notes[0]['id']}/read").status_code == 200
    sign_in(c)
    history = c.get(f"/api/projects/{pid}/history").json()
    assert history["decisions"]


def test_self_approval_and_other_project_file(env, tmp_path):
    c, maker = env
    settings.file_root = str(tmp_path)
    sign_in(c)
    project = complete(c, code="FILE-1")
    pid = project["id"]
    with maker() as db:
        reviewer_id = db.query(User).filter_by(email="admin@alpha.test").one().id
    c.post(
        f"/api/projects/{pid}/approval-policies",
        json={
            "record_type": "project.activation",
            "stages": [{"name": "Self", "rule": "all", "reviewer_ids": [reviewer_id]}],
        },
    )
    review = c.post(f"/api/projects/{pid}/activation-reviews").json()
    denied = c.post(
        f"/api/reviews/{review['id']}/decisions",
        json={"action": "approve", "version": review["version"]},
    )
    assert denied.status_code == 403
    uploaded = c.post(
        f"/api/projects/{pid}/files",
        data={"category": "Setup"},
        files={"upload": ("note.txt", b"phase2", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    fid = uploaded.json()["id"]
    assert c.get(f"/api/projects/{pid}/files/{fid}").content == b"phase2"
    other = new_project(c, code="OTHER").json()["id"]
    assert c.get(f"/api/projects/{other}/files/{fid}").status_code == 404
    assert (
        c.post(
            f"/api/projects/{pid}/files",
            data={"category": "Setup"},
            files={"upload": ("bad.exe", b"MZ", "application/octet-stream")},
        ).status_code
        == 422
    )
    sign_in(c, "viewer@alpha.test")
    assert c.get(f"/api/projects/{pid}/files/{fid}").status_code == 403
    sign_in(c)
    assert c.delete(f"/api/projects/{pid}/files/{fid}").status_code == 200
    assert c.get(f"/api/projects/{pid}/files/{fid}").status_code == 404


def test_referenced_records_stay(env):
    c, _ = env
    sign_in(c)
    company = c.get("/api/companies").json()["items"][0]
    assert (
        c.put(
            f"/api/companies/{company['id']}",
            json={
                "name": company["name"],
                "company_type": company["company_type"],
                "active": False,
                "version": company["version"],
            },
        ).status_code
        == 409
    )
    project = new_project(c, code="LOC").json()
    unit = c.post(
        f"/api/projects/{project['id']}/areas",
        json={"code": "U", "name": "Unit", "area_type": "Unit"},
    ).json()
    area = c.post(
        f"/api/projects/{project['id']}/areas",
        json={"code": "A", "name": "Area", "area_type": "Area", "parent_id": unit["id"]},
    ).json()
    listed = c.get(f"/api/projects/{project['id']}/areas").json()
    unit_row = next(row for row in listed if row["id"] == unit["id"])
    blocked = c.put(
        f"/api/projects/{project['id']}/areas/{unit['id']}",
        json={
            "code": "U",
            "name": "Unit",
            "description": "",
            "active": False,
            "version": unit_row["version"],
        },
    )
    assert blocked.status_code == 409
    area_row = next(row for row in listed if row["id"] == area["id"])
    assert (
        c.put(
            f"/api/projects/{project['id']}/areas/{area['id']}",
            json={
                "code": "A",
                "name": "Area renamed",
                "description": "kept",
                "active": False,
                "version": area_row["version"],
            },
        ).status_code
        == 200
    )
    names = [row["name"] for row in c.get(f"/api/projects/{project['id']}/areas").json()]
    assert "Area renamed" in names


def test_job_retry_and_dedupe(env):
    _, maker = env
    seen = {"n": 0}

    def flaky(db, job):
        seen["n"] += 1
        if job.attempts < 2:
            raise RuntimeError("temporary")
        user = db.get(User, job.payload["user_id"])
        notify(db, user, "Retry ok", "once", "retry-once")

    HANDLERS["test.retry"] = flaky
    with maker() as db:
        user = db.query(User).filter_by(email="admin@alpha.test").one()
        enqueue(
            db,
            "test.retry",
            {"user_id": user.id},
            "retry-key",
            datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        enqueue(
            db,
            "test.retry",
            {"user_id": user.id},
            "retry-key",
            datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        db.commit()
        assert db.query(Job).count() == 1
        process_jobs(db)
        job = db.query(Job).filter_by(dedupe_key="retry-key").one()
        assert job.status == "pending" and job.attempts == 1
        process_jobs(db)
        job = db.query(Job).filter_by(dedupe_key="retry-key").one()
        assert job.status == "succeeded"
        process_jobs(db)
        assert db.query(Notification).filter_by(source_key="retry-once").count() == 1
        process_jobs(db)
        assert db.query(Notification).filter_by(source_key="retry-once").count() == 1


def test_overdue_reminder_does_not_approve(env):
    c, maker = env
    sign_in(c)
    project = complete(c, code="DUE-1")
    pid = project["id"]
    me = c.get("/api/auth/me").json()["user"]
    assert (
        c.post(
            f"/api/projects/{pid}/reminder-policies",
            json={
                "record_type": "task",
                "reminder_hours": 1,
                "escalate_after_hours": 1,
                "recipient_ids": [me["id"]],
            },
        ).status_code
        == 201
    )
    due = (date.today() - timedelta(days=2)).isoformat()
    created = c.post(
        f"/api/projects/{pid}/tasks",
        json={"title": "Overdue gate check", "owner_id": me["id"], "due_date": due},
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    with maker() as db:
        process_jobs(db)
        process_jobs(db)
        keys = [row.source_key for row in db.query(Notification).filter_by(user_id=me["id"])]
    assert keys.count(f"task:{task_id}:overdue") == 1
    assert keys.count(f"task:{task_id}:escalated:{me['id']}") == 1
    listed = c.get("/api/tasks").json()
    task = next(row for row in listed if row["id"] == task_id)
    assert task["status"] == "Open"
    assert c.get(f"/api/projects/{pid}").json()["status"] == "Draft"


def _reviewers(c):
    company_id = c.get("/api/companies").json()["items"][0]["id"]
    created = c.post(
        "/api/users",
        json={
            "name": "Second Reviewer",
            "email": "second@alpha.test",
            "password": "test-password-123",
            "company_id": company_id,
        },
    )
    assert created.status_code == 201, created.text
    catalog = c.get("/api/catalog").json()
    return (
        next(user["id"] for user in c.get("/api/users").json()["items"] if user["email"] == "viewer@alpha.test"),
        created.json()["id"],
        next(role["id"] for role in catalog["roles"] if role["name"] == "Viewer"),
        company_id,
    )


def _policy(c, pid, stages):
    response = c.post(
        f"/api/projects/{pid}/approval-policies",
        json={"record_type": "project.activation", "allow_self_approval": False, "stages": stages},
    )
    assert response.status_code == 201, response.text


def _assign(c, pid, user_id, role_id, company_id):
    response = c.post(
        f"/api/projects/{pid}/memberships",
        json={
            "user_id": user_id,
            "role_id": role_id,
            "company_id": company_id,
            "scope": "ALL",
            "discipline_ids": [],
        },
    )
    assert response.status_code == 201, response.text


def test_two_stages_and_stale_revision(env):
    c, _ = env
    sign_in(c)
    project = complete(c, code="STAGE-1")
    pid = project["id"]
    first, second, role_id, company_id = _reviewers(c)
    _assign(c, pid, first, role_id, company_id)
    _policy(
        c,
        pid,
        [
            {"name": "First", "rule": "all", "reviewer_ids": [first]},
            {"name": "Second", "rule": "all", "reviewer_ids": [second]},
        ],
    )
    review = c.post(f"/api/projects/{pid}/activation-reviews").json()
    sign_in(c, "viewer@alpha.test")
    held = c.post(
        f"/api/reviews/{review['id']}/decisions",
        json={"action": "approve", "version": review["version"]},
    )
    assert held.status_code == 200, held.text
    assert held.json()["state"] == "In Review"
    assert c.get(f"/api/projects/{pid}").json()["status"] == "Draft"
    sign_in(c, "second@alpha.test")
    assert c.get(f"/api/projects/{pid}/tasks").status_code == 403
    sign_in(c)
    _assign(c, pid, second, role_id, company_id)
    sign_in(c, "second@alpha.test")
    stale = c.post(
        f"/api/reviews/{review['id']}/decisions",
        json={"action": "approve", "version": review["version"]},
    )
    assert stale.status_code == 409
    current = c.get("/api/reviews").json()[0]
    approved = c.post(
        f"/api/reviews/{review['id']}/decisions",
        json={"action": "approve", "version": current["version"]},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"] == "Approved"
    assert c.get(f"/api/projects/{pid}").json()["status"] == "Active"


def test_changed_project_cannot_be_approved(env):
    c, _ = env
    sign_in(c)
    project = complete(c, code="STALE-1")
    pid = project["id"]
    reviewer_id, _second, role_id, company_id = _reviewers(c)
    _assign(c, pid, reviewer_id, role_id, company_id)
    _policy(c, pid, [{"name": "Check", "rule": "all", "reviewer_ids": [reviewer_id]}])
    review = c.post(f"/api/projects/{pid}/activation-reviews").json()
    current = c.get(f"/api/projects/{pid}").json()
    body = {
        key: value
        for key, value in current.items()
        if key not in ["id", "created_by", "created_at", "modified_at", "modified_by", "client_name", "lead_pm_name"]
    }
    body["description"] = "Changed after submission"
    assert c.put(f"/api/projects/{pid}", json=body).status_code == 200
    sign_in(c, "viewer@alpha.test")
    denied = c.post(
        f"/api/reviews/{review['id']}/decisions",
        json={"action": "approve", "version": review["version"]},
    )
    assert denied.status_code == 409
    sign_in(c)
    assert c.get(f"/api/projects/{pid}").json()["status"] == "Draft"


def test_quorum_cannot_skip_reviewers(env):
    c, _ = env
    sign_in(c)
    project = complete(c, code="QUORUM-1")
    pid = project["id"]
    first, second, role_id, company_id = _reviewers(c)
    _assign(c, pid, first, role_id, company_id)
    _assign(c, pid, second, role_id, company_id)
    rejected = c.post(
        f"/api/projects/{pid}/approval-policies",
        json={
            "record_type": "project.activation",
            "stages": [
                {
                    "name": "Either",
                    "rule": "quorum",
                    "quorum_count": 0,
                    "reviewer_ids": [first, second],
                }
            ],
        },
    )
    assert rejected.status_code == 422
    _policy(
        c,
        pid,
        [
            {
                "name": "Either",
                "rule": "quorum",
                "quorum_count": 1,
                "reviewer_ids": [first, second],
            }
        ],
    )
    review = c.post(f"/api/projects/{pid}/activation-reviews").json()
    sign_in(c, "viewer@alpha.test")
    approved = c.post(
        f"/api/reviews/{review['id']}/decisions",
        json={"action": "approve", "version": review["version"]},
    )
    assert approved.status_code == 200, approved.text
    assert c.get(f"/api/projects/{pid}").json()["status"] == "Active"
    sign_in(c, "second@alpha.test")
    late = c.post(
        f"/api/reviews/{review['id']}/decisions",
        json={"action": "approve", "version": approved.json()["version"]},
    )
    assert late.status_code == 409


def test_task_scope_and_status_reason(env, tmp_path):
    c, _ = env
    settings.file_root = str(tmp_path)
    previous_limit = settings.max_upload_bytes
    settings.max_upload_bytes = 4
    try:
        _task_scope_and_status_reason(c)
    finally:
        settings.max_upload_bytes = previous_limit


def _task_scope_and_status_reason(c):
    sign_in(c)
    project = complete(c, code="TASK-1")
    pid = project["id"]
    viewer_id, _second, role_id, company_id = _reviewers(c)
    _assign(c, pid, viewer_id, role_id, company_id)
    created = c.post(
        f"/api/projects/{pid}/tasks",
        json={"title": "Collect gate photo", "owner_id": viewer_id, "priority": "High"},
    )
    assert created.status_code == 201, created.text
    task = created.json()
    sign_in(c, "viewer@alpha.test")
    assert (
        c.post(
            f"/api/tasks/{task['id']}",
            json={"status": "Completed", "evidence": "", "version": task["version"]},
        ).status_code
        == 422
    )
    done = c.post(
        f"/api/tasks/{task['id']}",
        json={"status": "Completed", "evidence": "Photo filed", "version": task["version"]},
    )
    assert done.status_code == 200, done.text
    assert (
        c.post(
            f"/api/tasks/{task['id']}",
            json={"status": "Open", "evidence": "Photo filed", "version": done.json()["version"]},
        ).status_code
        == 409
    )
    sign_in(c)
    current = c.get(f"/api/projects/{pid}").json()
    body = {
        key: value
        for key, value in current.items()
        if key not in ["id", "created_by", "created_at", "modified_at", "modified_by", "client_name", "lead_pm_name"]
    }
    body["actual_finish"] = "2026-02-01"
    edited = c.put(f"/api/projects/{pid}", json=body)
    assert edited.status_code == 200, edited.text
    planned = c.post(
        f"/api/projects/{pid}/transitions",
        json={"target": "Planned", "reason": "", "version": edited.json()["version"]},
    )
    assert planned.status_code == 200, planned.text
    assert (
        c.post(
            f"/api/projects/{pid}/transitions",
            json={"target": "On Hold", "reason": "", "version": planned.json()["version"]},
        ).status_code
        == 422
    )
    held = c.post(
        f"/api/projects/{pid}/transitions",
        json={"target": "On Hold", "reason": "Awaiting access", "version": planned.json()["version"]},
    )
    assert held.status_code == 200, held.text
    oversized = c.post(
        f"/api/projects/{pid}/files",
        data={"category": "Setup"},
        files={"upload": ("note.txt", b"too-big", "text/plain")},
    )
    assert oversized.status_code == 422
