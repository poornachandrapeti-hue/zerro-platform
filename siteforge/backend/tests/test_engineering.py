from datetime import date, timedelta
from io import BytesIO

from openpyxl import Workbook

from app.domains.coordination.models import Notification
from app.domains.engineering_documents.models import StoredFile
from app.domains.engineering_documents.workflow import scan_overdue
from app.domains.identity_projects.router import attempts
from .conftest import sign_in as _sign_in
from .test_phase2 import complete


def sign_in(client, email="admin@alpha.test"):
    attempts.clear()
    return _sign_in(client, email)


def _ids(c):
    catalog = c.get("/api/catalog").json()
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    disciplines = {row["name"]: row["id"] for row in catalog["disciplines"]}
    me = c.get("/api/auth/me").json()["user"]
    return roles, disciplines, me


def _user(c, email, name, company_id):
    response = c.post(
        "/api/users",
        json={
            "name": name,
            "email": email,
            "password": "test-password-123",
            "company_id": company_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _member(c, pid, user_id, role_id, company_id, discipline_ids):
    response = c.post(
        f"/api/projects/{pid}/memberships",
        json={
            "user_id": user_id,
            "role_id": role_id,
            "company_id": company_id,
            "scope": "SELECTED" if discipline_ids else "ALL",
            "discipline_ids": discipline_ids,
        },
    )
    assert response.status_code == 201, response.text


def _file(c, pid, drawing_id, code, body=b"drawing-bytes"):
    response = c.post(
        f"/api/projects/{pid}/drawings/{drawing_id}/revisions",
        data={"code": code},
        files={"upload": (f"{code}.pdf", body, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _revision(payload, code):
    return next(row for row in payload["revisions"] if row["code"] == code)


def _decide(c, review, action, reason=""):
    response = c.post(
        f"/api/reviews/{review['id']}/decisions",
        json={"action": action, "reason": reason, "version": review["version"]},
    )
    return response


def test_drawing_review_release_and_supersession(env, tmp_path):
    from app.config import settings

    settings.file_root = str(tmp_path)
    c, maker = env
    sign_in(c)
    roles, disciplines, me = _ids(c)
    electrical = disciplines["Electrical"]
    mechanical = disciplines["Mechanical"]
    project = complete(c, code="ENG-1", discipline_ids=[electrical, mechanical])
    pid = project["id"]
    company_id = me["company_id"]
    engineer = _user(c, "engineer@alpha.test", "Engineer", company_id)
    head = _user(c, "head@alpha.test", "Head", company_id)
    client = _user(c, "client@alpha.test", "Client", company_id)
    other = _user(c, "mech@alpha.test", "Mechanic", company_id)
    site = _user(c, "site@alpha.test", "Site", company_id)
    controller = _user(c, "docs@alpha.test", "Docs", company_id)
    _member(c, pid, engineer, roles["Engineering Engineer"], company_id, [electrical])
    _member(c, pid, head, roles["Discipline Head"], company_id, [electrical])
    _member(c, pid, client, roles["Client/PMC Reviewer"], company_id, [electrical])
    _member(c, pid, other, roles["Engineering Engineer"], company_id, [mechanical])
    _member(c, pid, site, roles["Site Engineer"], company_id, [])
    _member(c, pid, controller, roles["Document Controller"], company_id, [])
    policy = c.post(
        f"/api/projects/{pid}/approval-policies",
        json={
            "record_type": "drawing.revision",
            "discipline_id": electrical,
            "allow_self_approval": False,
            "stages": [
                {"name": "Internal", "rule": "all", "purpose": "internal", "reviewer_ids": [head]},
                {"name": "Client", "rule": "all", "purpose": "client", "reviewer_ids": [client]},
            ],
        },
    )
    assert policy.status_code == 201, policy.text
    sign_in(c, "engineer@alpha.test")
    created = c.post(
        f"/api/projects/{pid}/drawings",
        json={
            "number": "E-1",
            "title": "Single line",
            "drawing_type": "Schematic",
            "discipline_id": electrical,
            "company_id": company_id,
            "responsible_user_id": engineer,
            "priority": "High",
            "planned_date": "2026-04-01",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["bucket"] == "to_prepare"
    drawing_id = created.json()["id"]
    sign_in(c, "mech@alpha.test")
    assert c.get(f"/api/projects/{pid}/drawings/{drawing_id}").status_code == 403
    sign_in(c, "site@alpha.test")
    assert c.get(f"/api/projects/{pid}/drawings/{drawing_id}").status_code == 403
    sign_in(c, "engineer@alpha.test")
    prepared = _file(c, pid, drawing_id, "A")
    revision_a = _revision(prepared, "A")
    assert prepared["preparation"] == "Prepared"
    assert prepared["bucket"] == "in_preparation"
    submitted = c.post(
        f"/api/projects/{pid}/drawings/{drawing_id}/revisions/{revision_a['id']}/submit"
    )
    assert submitted.status_code == 201, submitted.text
    review = _revision(submitted.json(), "A")["review"]
    assert _revision(submitted.json(), "A")["review_state"] == "Internal Review"
    assert [step["status"] for step in review["chain"]] == ["current", "waiting"]
    sign_in(c, "head@alpha.test")
    head_notes = c.get("/api/notifications").json()
    assert any(row["title"] == "Your review is required" for row in head_notes)
    assert any(row["number"] == "E-1" for row in c.get(f"/api/projects/{pid}/engineering-tasks").json()["reviews"])
    sign_in(c, "client@alpha.test")
    assert not any(row["title"] == "Your review is now required" for row in c.get("/api/notifications").json())
    assert c.get(f"/api/projects/{pid}/engineering-tasks").json()["reviews"] == []
    sign_in(c, "engineer@alpha.test")
    assert c.get(f"/api/projects/{pid}/engineering-tasks").json()["reviews"] == []
    denied = _decide(c, review, "approve")
    assert denied.status_code == 403
    sign_in(c, "head@alpha.test")
    stale_client_version = review["version"]
    internal = _decide(c, review, "approve")
    assert internal.status_code == 200, internal.text
    sign_in(c, "client@alpha.test")
    assert any(row["title"] == "Your review is now required" for row in c.get("/api/notifications").json())
    assert any(row["number"] == "E-1" for row in c.get(f"/api/projects/{pid}/engineering-tasks").json()["reviews"])
    sign_in(c, "head@alpha.test")
    assert c.get(f"/api/projects/{pid}/engineering-tasks").json()["reviews"] == []
    sign_in(c, "engineer@alpha.test")
    assert any(row["title"] == "Review moved to the next person" for row in c.get("/api/notifications").json())
    sign_in(c, "client@alpha.test")
    stale = _decide(c, {"id": review["id"], "version": stale_client_version}, "return", "Wrong border")
    assert stale.status_code == 409
    current = _revision(c.get(f"/api/projects/{pid}/drawings/{drawing_id}").json(), "A")
    assert current["review_state"] == "Client Review"
    assert current["release_state"] == "Not Released"
    comment = c.post(
        f"/api/projects/{pid}/drawings/{drawing_id}/revisions/{revision_a['id']}/comments",
        json={
            "page_ref": "1",
            "body": "Move the feeder",
            "severity": "Blocking",
            "owner_id": engineer,
            "due_date": "2020-01-01",
        },
    )
    assert comment.status_code == 201, comment.text
    comment_id = comment.json()["id"]
    sign_in(c, "site@alpha.test")
    denied = c.post(
        f"/api/projects/{pid}/comments/{comment_id}/respond",
        json={"response": "Not my comment", "version": 1},
    )
    assert denied.status_code == 403, denied.text
    sign_in(c, "engineer@alpha.test")
    responded = c.post(
        f"/api/projects/{pid}/comments/{comment_id}/respond",
        json={"response": "Feeder moved", "version": 1},
    )
    assert responded.status_code == 200, responded.text
    sign_in(c, "head@alpha.test")
    closed = c.post(
        f"/api/projects/{pid}/comments/{comment_id}/close",
        json={"evidence": "Checked on the returned sheet", "version": 2},
    )
    assert closed.status_code == 200, closed.text
    sign_in(c, "client@alpha.test")
    returned = _decide(c, current["review"], "return", "Wrong border")
    assert returned.status_code == 200, returned.text
    sign_in(c, "engineer@alpha.test")
    assert any(row["title"] == "Drawing returned" for row in c.get("/api/notifications").json())
    again = c.post(f"/api/projects/{pid}/drawings/{drawing_id}/revisions/{revision_a['id']}/submit")
    assert again.status_code == 409
    corrected = _file(c, pid, drawing_id, "B", b"corrected-bytes")
    assert any(row["body"] == "Move the feeder" for row in _revision(corrected, "A")["comments"])
    revision_b = _revision(corrected, "B")
    submitted_b = c.post(
        f"/api/projects/{pid}/drawings/{drawing_id}/revisions/{revision_b['id']}/submit"
    )
    assert submitted_b.status_code == 201, submitted_b.text
    review_b = _revision(submitted_b.json(), "B")["review"]
    sign_in(c, "head@alpha.test")
    assert _decide(c, review_b, "approve").status_code == 200
    sign_in(c, "client@alpha.test")
    current_b = _revision(c.get(f"/api/projects/{pid}/drawings/{drawing_id}").json(), "B")
    accepted = _decide(c, current_b["review"], "approve_with_comments", "Issue with the noted cloud")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["state"] == "Approved"
    sign_in(c, "engineer@alpha.test")
    blocked = c.post(
        f"/api/projects/{pid}/drawings/{drawing_id}/revisions/{revision_b['id']}/release",
        json={"version": revision_b["version"]},
    )
    assert blocked.status_code == 403
    sign_in(c)
    enabled = c.put(
        f"/api/projects/{pid}/engineering-settings",
        json={"allow_release_with_comments": True},
    )
    assert enabled.status_code == 200, enabled.text
    sign_in(c, "head@alpha.test")
    early = c.post(
        f"/api/projects/{pid}/drawings/{drawing_id}/revisions/{revision_a['id']}/release",
        json={"version": revision_a["version"]},
    )
    assert early.status_code == 409
    released = c.post(
        f"/api/projects/{pid}/drawings/{drawing_id}/revisions/{revision_b['id']}/release",
        json={"version": revision_b["version"]},
    )
    assert released.status_code == 200, released.text
    body = released.json()
    assert _revision(body, "B")["release_state"] == "Released"
    assert _revision(body, "B")["review_state"] == "Accepted with Comments"
    assert body["latest_released"]["code"] == "B"
    conflict = c.post(
        f"/api/projects/{pid}/drawings/{drawing_id}/revisions/{revision_b['id']}/release",
        json={"version": revision_b["version"]},
    )
    assert conflict.status_code == 409
    sign_in(c, "engineer@alpha.test")
    newer = _file(c, pid, drawing_id, "C", b"newer-bytes")
    revision_c = _revision(newer, "C")
    submitted_c = c.post(
        f"/api/projects/{pid}/drawings/{drawing_id}/revisions/{revision_c['id']}/submit"
    )
    review_c = _revision(submitted_c.json(), "C")["review"]
    sign_in(c, "head@alpha.test")
    assert _decide(c, review_c, "approve").status_code == 200
    sign_in(c, "client@alpha.test")
    current_c = _revision(c.get(f"/api/projects/{pid}/drawings/{drawing_id}").json(), "C")
    assert _decide(c, current_c["review"], "approve").status_code == 200
    sign_in(c, "head@alpha.test")
    superseded = c.post(
        f"/api/projects/{pid}/drawings/{drawing_id}/revisions/{revision_c['id']}/release",
        json={"version": revision_c["version"]},
    )
    assert superseded.status_code == 200, superseded.text
    final = superseded.json()
    assert _revision(final, "C")["release_state"] == "Released"
    assert _revision(final, "B")["release_state"] == "Superseded"
    assert "superseded" in {row["kind"] for row in _revision(final, "B")["events"]}
    assert final["latest_released"]["code"] == "C"
    sign_in(c, "docs@alpha.test")
    transmittal = c.post(
        f"/api/projects/{pid}/transmittals",
        json={
            "number": "TR-1",
            "purpose": "For construction",
            "issue_date": "2026-04-02",
            "revision_ids": [revision_b["id"]],
            "recipient_ids": [site],
        },
    )
    assert transmittal.status_code == 201, transmittal.text
    sent = c.post(
        f"/api/projects/{pid}/transmittals/{transmittal.json()['id']}/dispatch",
        json={"version": transmittal.json()["version"]},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "Issued"
    assert sent.json()["revision_ids"] == [revision_b["id"]]
    sign_in(c, "site@alpha.test")
    acked = c.post(f"/api/projects/{pid}/transmittals/{transmittal.json()['id']}/acknowledge")
    assert acked.status_code == 200, acked.text
    assert acked.json()["status"] == "Acknowledged"
    assert acked.json()["revision_ids"] == [revision_b["id"]]
    visible = c.get(f"/api/projects/{pid}/drawings/{drawing_id}")
    assert visible.status_code == 200, visible.text
    assert visible.json()["latest_released"]["code"] == "C"
    assert "C" in {row["code"] for row in visible.json()["revisions"]}
    assert c.get(
        f"/api/projects/{pid}/drawings/{drawing_id}/revisions/{revision_c['id']}/file"
    ).content == b"newer-bytes"
    register = c.get(f"/api/projects/{pid}/drawings?bucket=released")
    assert register.status_code == 200
    assert register.json()["summary"]["counts"]["released"] == len(register.json()["items"])
    sign_in(c, "viewer@alpha.test")
    assert c.get(f"/api/projects/{pid}/drawings").status_code == 403
    with maker() as db:
        assert db.query(Notification).filter_by(source_key=f"drawing-review:{review_b['id']}:accepted").count() == 1


def test_import_duplicates_and_wrench_stay_manual(env):
    c, _ = env
    sign_in(c)
    _, disciplines, _me = _ids(c)
    project = complete(c, code="IMP-1", discipline_ids=[disciplines["Electrical"]])
    pid = project["id"]
    csv_body = (
        "number,title,type,discipline,company,responsible,location,planned_date,priority\n"
        "E-9,Cable schedule,Schedule,Electrical,Alpha Co,,,2026-05-01,Normal\n"
    )
    first = c.post(
        f"/api/projects/{pid}/drawing-imports",
        files={"upload": ("drawings.csv", csv_body.encode(), "text/csv")},
    )
    assert first.status_code == 201, first.text
    assert first.json()["created"] == ["E-9"]
    second = c.post(
        f"/api/projects/{pid}/drawing-imports",
        files={"upload": ("drawings.csv", csv_body.encode(), "text/csv")},
    )
    assert second.json()["skipped"] == ["E-9"]
    assert second.json()["created"] == []
    changed = csv_body.replace("Cable schedule", "Different schedule")
    conflict = c.post(
        f"/api/projects/{pid}/drawing-imports",
        files={"upload": ("drawings.csv", changed.encode(), "text/csv")},
    )
    assert conflict.json()["conflicts"]
    book = Workbook()
    sheet = book.active
    sheet.append(["number", "title", "type", "discipline", "company", "priority"])
    sheet.append(["E-10", "Layout", "GA", "Electrical", "Alpha Co", "High"])
    buffer = BytesIO()
    book.save(buffer)
    imported = c.post(
        f"/api/projects/{pid}/drawing-imports",
        files={
            "upload": (
                "drawings.xlsx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert imported.status_code == 201, imported.text
    assert imported.json()["created"] == ["E-10"]
    drawing_id = next(
        row["id"] for row in c.get(f"/api/projects/{pid}/drawings").json()["items"] if row["number"] == "E-9"
    )
    linked = c.post(
        f"/api/projects/{pid}/drawings/{drawing_id}/wrench-link",
        json={"external_document_id": "WR-9", "external_revision_id": "1"},
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["conflict_status"] == "none"
    clash = c.post(
        f"/api/projects/{pid}/drawings/{drawing_id}/wrench-link",
        json={"external_document_id": "WR-OTHER", "external_revision_id": "2"},
    )
    assert clash.json()["conflict_status"] == "conflict"
    assert clash.json()["external_document_id"] == "WR-9"
    assert c.get(f"/api/projects/{pid}/drawings/{drawing_id}").json()["title"] == "Cable schedule"
    enabled = c.put(
        f"/api/projects/{pid}/wrench",
        json={"enabled": True, "specification": "none", "credential_label": "missing"},
    )
    assert enabled.status_code == 409
    assert c.post(f"/api/projects/{pid}/wrench/sync").status_code == 409
    added = c.post("/api/disciplines", json={"name": "Telecom"})
    assert added.status_code == 201, added.text
    assert any(row["name"] == "Telecom" for row in c.get("/api/catalog").json()["disciplines"])


def test_quarantine_and_overdue_do_not_approve(env, tmp_path):
    from app.config import settings

    settings.file_root = str(tmp_path)
    c, maker = env
    sign_in(c)
    roles, disciplines, me = _ids(c)
    electrical = disciplines["Electrical"]
    project = complete(c, code="Q-1", discipline_ids=[electrical])
    pid = project["id"]
    head = _user(c, "headq@alpha.test", "Head Q", me["company_id"])
    _member(c, pid, head, roles["Discipline Head"], me["company_id"], [electrical])
    c.post(
        f"/api/projects/{pid}/approval-policies",
        json={
            "record_type": "drawing.revision",
            "stages": [
                {"name": "Internal", "rule": "all", "purpose": "internal", "reviewer_ids": [head]}
            ],
        },
    )
    created = c.post(
        f"/api/projects/{pid}/drawings",
        json={
            "number": "E-Q",
            "title": "Query",
            "discipline_id": electrical,
            "company_id": me["company_id"],
            "responsible_user_id": me["id"],
            "planned_date": (date.today() - timedelta(days=3)).isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    drawing_id = created.json()["id"]
    uploaded = _file(c, pid, drawing_id, "A")
    revision_id = _revision(uploaded, "A")["id"]
    with maker() as db:
        stored = db.query(StoredFile).order_by(StoredFile.id.desc()).first()
        stored.scan_status = "quarantined"
        db.commit()
    assert (
        c.post(f"/api/projects/{pid}/drawings/{drawing_id}/revisions/{revision_id}/submit").status_code
        == 409
    )
    with maker() as db:
        stored = db.get(StoredFile, stored.id)
        stored.scan_status = "available"
        db.commit()
        scan_overdue(db, date.today())
        scan_overdue(db, date.today())
        db.commit()
        assert (
            db.query(Notification)
            .filter(Notification.source_key.like(f"drawing:{drawing_id}:prep:owner:%"))
            .count()
            == 1
        )
    submitted = c.post(f"/api/projects/{pid}/drawings/{drawing_id}/revisions/{revision_id}/submit")
    assert submitted.status_code == 201, submitted.text
    assert _revision(submitted.json(), "A")["review_state"] == "Internal Review"


def test_saved_drawing_reviewers_replace_the_frozen_policy(env, tmp_path):
    from app.config import settings

    settings.file_root = str(tmp_path)
    c, _maker = env
    sign_in(c)
    roles, disciplines, me = _ids(c)
    electrical = disciplines["Electrical"]
    project = complete(c, code="POL-1", discipline_ids=[electrical])
    pid = project["id"]
    company_id = me["company_id"]
    site = _user(c, "site.pol@alpha.test", "Site Pol", company_id)
    client = _user(c, "client.pol@alpha.test", "Client Pol", company_id)
    outsider = _user(c, "out.pol@alpha.test", "Out Pol", company_id)
    _member(c, pid, site, roles["Site Engineer"], company_id, [electrical])
    _member(c, pid, client, roles["Engineering Engineer"], company_id, [electrical])
    denied = c.post(
        f"/api/projects/{pid}/approval-policies",
        json={
            "record_type": "drawing.revision",
            "stages": [
                {"name": "Internal", "rule": "all", "purpose": "internal", "reviewer_ids": [outsider]}
            ],
        },
    )
    assert denied.status_code == 422
    first = c.post(
        f"/api/projects/{pid}/approval-policies",
        json={
            "record_type": "drawing.revision",
            "stages": [
                {"name": "Internal", "rule": "all", "purpose": "internal", "reviewer_ids": [site]}
            ],
        },
    )
    assert first.status_code == 201, first.text
    replaced = c.post(
        f"/api/projects/{pid}/approval-policies",
        json={
            "record_type": "drawing.revision",
            "discipline_id": electrical,
            "stages": [
                {"name": "Internal", "rule": "all", "purpose": "internal", "reviewer_ids": [site]},
                {"name": "Client", "rule": "all", "purpose": "client", "reviewer_ids": [client]},
            ],
        },
    )
    assert replaced.status_code == 201, replaced.text
    listed = c.get(f"/api/projects/{pid}/approval-policies?record_type=drawing.revision")
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert rows[0]["discipline_id"] == electrical
    assert rows[0]["stages"][0]["reviewers"][0]["name"] == "Site Pol"
    assert rows[0]["stages"][1]["reviewers"][0]["name"] == "Client Pol"
    created = c.post(
        f"/api/projects/{pid}/drawings",
        json={
            "number": "E-POL",
            "title": "Policy check",
            "discipline_id": electrical,
            "company_id": company_id,
            "responsible_user_id": me["id"],
        },
    )
    assert created.status_code == 201, created.text
    drawing_id = created.json()["id"]
    uploaded = _file(c, pid, drawing_id, "A")
    revision = _revision(uploaded, "A")
    submitted = c.post(f"/api/projects/{pid}/drawings/{drawing_id}/revisions/{revision['id']}/submit")
    assert submitted.status_code == 201, submitted.text
    sign_in(c, "site.pol@alpha.test")
    approved = _decide(c, _revision(submitted.json(), "A")["review"], "approve")
    assert approved.status_code == 200, approved.text
