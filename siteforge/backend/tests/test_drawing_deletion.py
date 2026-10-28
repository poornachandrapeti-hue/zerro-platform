"""Secure soft deletion of draft drawings."""
from datetime import date

from app.domains.engineering_documents.models import Drawing, DrawingRevision
from app.domains.identity_projects.models import Audit, Project
from app.domains.identity_projects.seed import DRAWING_DELETION_ROLE
from app.domains.supply_chain.models import MaterialRequirement
from .test_engineering import _file, _ids, _member, _user, sign_in
from .test_phase2 import complete


def _setup(c, code="DEL-1"):
    sign_in(c)
    roles, disciplines, me = _ids(c)
    electrical = disciplines["Electrical"]
    pid = complete(c, code=code, discipline_ids=[electrical, disciplines["Mechanical"]])["id"]
    company = me["company_id"]
    return roles, disciplines, me, pid, company


def _drawing(c, pid, number, discipline_id, company_id):
    response = c.post(
        f"/api/projects/{pid}/drawings",
        json={"number": number, "title": f"Drawing {number}", "discipline_id": discipline_id, "company_id": company_id},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _delete(c, pid, drawing, reason="Created in error", version=None):
    return c.post(
        f"/api/projects/{pid}/drawings/{drawing['id']}/delete",
        json={"reason": reason, "version": version or drawing["version"]},
    )


def _import(c, pid, csv, mode="create"):
    return c.post(
        f"/api/projects/{pid}/drawing-imports",
        data={"mode": mode},
        files={"upload": ("drawings.csv", csv.encode(), "text/csv")},
    )


def test_authorized_soft_deletion_is_audited_and_hidden(env):
    c, maker = env
    roles, disciplines, me, pid, company = _setup(c)
    electrical = disciplines["Electrical"]
    engineer = _user(c, "engineer@alpha.test", "Engineer", company)
    deleter = _user(c, "deleter@alpha.test", "Deleter", company)
    _member(c, pid, engineer, roles["Engineering Engineer"], company, [electrical])
    _member(c, pid, deleter, roles[DRAWING_DELETION_ROLE], company, [electrical])
    sign_in(c, "engineer@alpha.test")
    drawing = _drawing(c, pid, "E-100", electrical, company)
    assert "delete" not in drawing["actions"]
    assert _delete(c, pid, drawing).status_code == 403
    sign_in(c)
    assert "delete" not in c.get(f"/api/projects/{pid}/drawings/{drawing['id']}").json()["actions"]
    assert _delete(c, pid, drawing).status_code == 403
    sign_in(c, "viewer@alpha.test")
    assert _delete(c, pid, drawing).status_code == 403

    sign_in(c, "deleter@alpha.test")
    assert "delete" in c.get(f"/api/projects/{pid}/drawings/{drawing['id']}").json()["actions"]
    assert _delete(c, pid, drawing, reason="   ").status_code == 422
    assert _delete(c, pid, drawing, version=drawing["version"] + 5).status_code == 409
    deleted = _delete(c, pid, drawing, reason="Duplicate of E-101")
    assert deleted.status_code == 200, deleted.text

    for status in ("Active", "All", "Deleted"):
        items = c.get(f"/api/projects/{pid}/drawings", params={"record_status": status}).json()["items"]
        assert all(row["id"] != drawing["id"] for row in items)
    assert c.get(f"/api/projects/{pid}/drawings/{drawing['id']}").status_code == 404
    again = _delete(c, pid, {**drawing, "version": drawing["version"] + 1})
    assert again.status_code == 409
    assert "already deleted" in again.json()["detail"]

    with maker() as db:
        row = db.get(Drawing, drawing["id"])
        assert row.record_status == "Deleted"
        assert row.number == "E-100" and row.number_key == "e-100"
        assert row.deleted_by == deleter
        assert row.deleted_at is not None
        assert row.deletion_reason == "Duplicate of E-101"
        event = db.query(Audit).filter_by(resource="drawings", resource_id=drawing["id"], action="delete").one()
        assert event.actor_id == deleter
        assert event.project_id == pid
        assert event.details["reason"] == "Duplicate of E-101"
        assert event.details["number"] == "E-100"


def test_grant_is_per_project_and_per_discipline(env):
    c, _ = env
    roles, disciplines, me, pid, company = _setup(c, "DEL-A")
    electrical, mechanical = disciplines["Electrical"], disciplines["Mechanical"]
    other_pid = complete(c, code="DEL-B", discipline_ids=[electrical])["id"]
    deleter = _user(c, "deleter@alpha.test", "Deleter", company)
    _member(c, pid, deleter, roles[DRAWING_DELETION_ROLE], company, [electrical])
    _member(c, other_pid, deleter, roles["Engineering Engineer"], company, [electrical])
    sign_in(c)
    here_mech = _drawing(c, pid, "M-1", mechanical, company)
    elsewhere = _drawing(c, other_pid, "E-1", electrical, company)

    sign_in(c, "deleter@alpha.test")
    assert _delete(c, other_pid, elsewhere).status_code == 403
    assert _delete(c, pid, elsewhere).status_code == 404
    assert _delete(c, pid, here_mech).status_code == 403
    sign_in(c, "admin@beta.test")
    assert _delete(c, other_pid, elsewhere).status_code == 404


def test_approved_issued_and_revision_linked_drawings_are_blocked(env, tmp_path):
    from app.config import settings

    settings.file_root = str(tmp_path)
    c, maker = env
    roles, disciplines, me, pid, company = _setup(c)
    electrical = disciplines["Electrical"]
    engineer = _user(c, "engineer@alpha.test", "Engineer", company)
    deleter = _user(c, "deleter@alpha.test", "Deleter", company)
    _member(c, pid, engineer, roles["Engineering Engineer"], company, [electrical])
    _member(c, pid, deleter, roles[DRAWING_DELETION_ROLE], company, [])
    sign_in(c, "engineer@alpha.test")
    drawing = _drawing(c, pid, "E-200", electrical, company)
    revised = _file(c, pid, drawing["id"], "A")
    cancelled = _drawing(c, pid, "E-201", electrical, company)
    assert c.post(
        f"/api/projects/{pid}/drawings/{cancelled['id']}/cancel",
        json={"reason": "Scope removed", "version": cancelled["version"]},
    ).status_code == 200

    sign_in(c, "deleter@alpha.test")
    current = c.get(f"/api/projects/{pid}/drawings/{drawing['id']}").json()
    assert "delete" not in current["actions"]
    blocked = _delete(c, pid, current)
    assert blocked.status_code == 409 and "revision" in blocked.json()["detail"]
    assert _delete(c, pid, cancelled, version=cancelled["version"] + 1).status_code == 409

    revision_id = revised["revisions"][0]["id"]
    for values, message in (
        ({"review_state": "Internal Review"}, "Submitted"),
        ({"review_state": "Accepted", "client_outcome": "Approved"}, "Approved"),
        ({"review_state": "Accepted", "release_state": "Released"}, "Issued"),
        ({"release_state": "Superseded"}, "superseded"),
    ):
        with maker() as db:
            row = db.get(DrawingRevision, revision_id)
            for key, value in values.items():
                setattr(row, key, value)
            db.commit()
        response = _delete(c, pid, current)
        assert response.status_code == 409, response.text
        assert message in response.json()["detail"]
    with maker() as db:
        assert db.get(Drawing, drawing["id"]).record_status == "Active"
        assert db.query(DrawingRevision).filter_by(drawing_id=drawing["id"]).count() == 1


def test_linked_and_cross_module_references_block_deletion(env):
    c, maker = env
    roles, disciplines, me, pid, company = _setup(c)
    electrical = disciplines["Electrical"]
    deleter = _user(c, "deleter@alpha.test", "Deleter", company)
    _member(c, pid, deleter, roles[DRAWING_DELETION_ROLE], company, [])
    sign_in(c)
    first = _drawing(c, pid, "E-300", electrical, company)
    second = _drawing(c, pid, "E-301", electrical, company)
    referenced = _drawing(c, pid, "E-302", electrical, company)
    link = c.post(f"/api/projects/{pid}/drawings/{first['id']}/links", json={"related_id": second["id"]})
    assert link.status_code == 201, link.text
    with maker() as db:
        db.add(
            MaterialRequirement(
                organization_id=db.get(Project, pid).organization_id,
                project_id=pid,
                number="MR-1",
                number_key="mr-1",
                company_id=company,
                discipline_id=electrical,
                requested_by=me["id"],
                required_date=date(2026, 12, 1),
                purpose="Cable for E-302",
                drawing_id=referenced["id"],
                created_by=me["id"],
            )
        )
        db.commit()

    sign_in(c, "deleter@alpha.test")
    for row in (first, second):
        response = _delete(c, pid, row)
        assert response.status_code == 409 and "linked" in response.json()["detail"]
    response = _delete(c, pid, referenced)
    assert response.status_code == 409 and "material requirement" in response.json()["detail"]
    assert "delete" not in c.get(f"/api/projects/{pid}/drawings/{referenced['id']}").json()["actions"]


def test_deleted_number_cannot_be_reimported_or_recreated(env):
    c, maker = env
    roles, disciplines, me, pid, company = _setup(c)
    electrical = disciplines["Electrical"]
    deleter = _user(c, "deleter@alpha.test", "Deleter", company)
    _member(c, pid, deleter, roles[DRAWING_DELETION_ROLE], company, [])
    sign_in(c)
    csv = "number,title,discipline\nE-900,Imported drawing,Electrical\n"
    created = _import(c, pid, csv)
    assert created.status_code == 201 and created.json()["created"] == ["E-900"], created.text
    drawing = next(row for row in c.get(f"/api/projects/{pid}/drawings").json()["items"] if row["number"] == "E-900")

    sign_in(c, "deleter@alpha.test")
    assert _delete(c, pid, drawing).status_code == 200

    sign_in(c)
    for mode in ("create", "update"):
        report = _import(c, pid, csv, mode)
        assert report.status_code == 201, report.text
        body = report.json()
        assert body["created"] == [] and body["updated"] == [] and body["skipped"] == []
        assert "deleted drawing" in body["conflicts"][0]["reason"]
        assert body["duplicates"] == 1
    recreated = c.post(
        f"/api/projects/{pid}/drawings",
        json={"number": "e-900", "title": "Again", "discipline_id": electrical, "company_id": company},
    )
    assert recreated.status_code == 409 and "deleted drawing" in recreated.json()["detail"]
    other = _drawing(c, pid, "E-901", electrical, company)
    renamed = c.put(
        f"/api/projects/{pid}/drawings/{other['id']}",
        json={"number": "E-900", "title": other["title"], "discipline_id": electrical, "company_id": company, "version": other["version"]},
    )
    assert renamed.status_code == 409
    with maker() as db:
        rows = db.query(Drawing).filter_by(project_id=pid, number_key="e-900").all()
        assert len(rows) == 1 and rows[0].record_status == "Deleted" and rows[0].title == "Imported drawing"
