from datetime import date

from .test_engineering import sign_in
from .test_foundation import new_project


def _package(area_id, company_id, discipline_id, code="WP-1", **extra):
    body = {
        "code": code,
        "name": "Foundation block",
        "discipline_id": discipline_id,
        "area_id": area_id,
        "scope_description": "Pile caps and grade beams",
        "company_id": company_id,
        "priority": "High",
        "revision_ids": [],
        "requirement_ids": [],
    }
    body.update(extra)
    return body


def test_construction_register_keeps_baseline_and_release_closed(env):
    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    piping = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Piping")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="CONST-1",
        client_company_id=me["company_id"],
        discipline_ids=[civil, piping],
        disciplines=[
            {"discipline_id": civil, "scope_description": "Civil", "active": True},
            {"discipline_id": piping, "scope_description": "Piping", "active": True},
        ],
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    area = c.post(
        f"/api/projects/{pid}/areas",
        json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""},
    )
    assert area.status_code == 201, area.text
    area_id = area.json()["id"]
    with maker() as db:
        from app.domains.identity_projects.models import User

        person = db.query(User).filter_by(email="viewer@alpha.test").one()
        uid, company = person.id, person.company_id
    sign_in(c, "viewer@alpha.test")
    assert c.get(f"/api/projects/{pid}/construction/summary").status_code == 403
    sign_in(c)
    assert (
        c.post(
            f"/api/projects/{pid}/memberships",
            json={
                "user_id": uid,
                "role_id": roles["Viewer"],
                "company_id": company,
                "scope": "ALL",
                "discipline_ids": [],
            },
        ).status_code
        == 201
    )
    sign_in(c, "viewer@alpha.test")
    assert c.get(f"/api/projects/{pid}/construction/summary").status_code == 403
    sign_in(c)
    assert (
        c.post(
            f"/api/projects/{pid}/memberships",
            json={
                "user_id": uid,
                "role_id": roles["Site Engineer"],
                "company_id": company,
                "scope": "ALL",
                "discipline_ids": [],
            },
        ).status_code
        == 201
    )
    members = len(c.get(f"/api/projects/{pid}/memberships").json())
    sign_in(c, "viewer@alpha.test")
    summary = c.get(f"/api/projects/{pid}/construction/summary")
    assert summary.status_code == 200, summary.text
    assert "Inspections" not in summary.json()["closed"]
    assert "Daily progress" not in summary.json()["closed"]
    examples = c.post(f"/api/projects/{pid}/construction/templates/examples")
    assert examples.status_code == 201, examples.text
    assert examples.json()["added"] == 15
    by_code = {row["code"]: row for row in examples.json()["templates"]}
    assert by_code["CIV-CONC"]["checkpoints"] != by_code["PIP-WELD"]["checkpoints"]
    assert by_code["CIV-CONC"]["discipline_name"] == "Civil"
    assert by_code["PIP-WELD"]["discipline_name"] == "Piping"
    assert c.post(f"/api/projects/{pid}/construction/templates/examples").json()["added"] == 0
    saved = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(area_id, company, civil),
    )
    assert saved.status_code == 201, saved.text
    package = saved.json()
    assert package["status"] == "Draft"
    assert package["release_open"] is True
    assert package["release_state"] == "Not Submitted"
    assert (
        c.post(
            f"/api/projects/{pid}/construction/packages",
            json=_package(area_id, company, civil, code="wp-1"),
        ).status_code
        == 409
    )
    assert (
        c.post(
            f"/api/projects/{pid}/construction/packages",
            json=_package(999999, company, civil, code="WP-2"),
        ).status_code
        == 422
    )
    blocked = c.post(
        f"/api/projects/{pid}/construction/packages/{package['id']}/release",
        json={"version": package["version"]},
    )
    assert blocked.status_code == 422, blocked.text
    assert "readiness" in blocked.text.casefold()
    activity = c.post(
        f"/api/projects/{pid}/construction/activities",
        json={
            "package_id": package["id"],
            "template_id": by_code["CIV-PILE"]["id"],
            "code": "PILES",
            "name": "Pile driving",
            "quantity": "10",
            "unit": "no",
            "company_id": company,
            "measurement_method": "Item completion",
            "predecessor_ids": [],
        },
    )
    assert activity.status_code == 201, activity.text
    body = activity.json()
    assert body["baseline_quantity"] == "10.000"
    assert body["progress_note"].startswith("Scope")
    edit = {
        "package_id": package["id"],
        "template_id": by_code["CIV-PILE"]["id"],
        "code": "PILES",
        "name": "Pile driving",
        "quantity": "12",
        "unit": "no",
        "company_id": company,
        "measurement_method": "Item completion",
        "predecessor_ids": [],
        "active": True,
        "version": body["version"],
        "quantity_reason": "",
    }
    assert c.put(f"/api/projects/{pid}/construction/activities/{body['id']}", json=edit).status_code == 422
    edit["quantity_reason"] = "Two extra piles"
    changed = c.put(f"/api/projects/{pid}/construction/activities/{body['id']}", json=edit)
    assert changed.status_code == 200, changed.text
    assert changed.json()["baseline_quantity"] == "10.000"
    assert changed.json()["quantity"] == "12.000"
    assert changed.json()["scope_changes"][0]["reason"] == "Two extra piles"
    item = c.post(
        f"/api/projects/{pid}/construction/items",
        json={
            "activity_id": body["id"],
            "identifier": "P-01",
            "description": "Pile 1",
            "item_kind": "Pile",
        },
    )
    assert item.status_code == 201, item.text
    assert (
        c.post(
            f"/api/projects/{pid}/construction/items",
            json={
                "activity_id": body["id"],
                "identifier": "p-01",
                "item_kind": "Pile",
            },
        ).status_code
        == 409
    )
    sign_in(c)
    assert len(c.get(f"/api/projects/{pid}/memberships").json()) == members
    current = c.get(f"/api/projects/{pid}/construction/packages").json()[0]
    assigned = dict(current)
    for key in (
        "id",
        "discipline_name",
        "area_name",
        "company_name",
        "responsible_name",
        "supervisor_name",
        "status",
        "release_state",
        "cancellation_reason",
        "revisions",
        "requirements",
        "activity_count",
        "release_open",
        "impact_state",
        "impact_detail",
        "impact_revision_id",
    ):
        assigned.pop(key)
    assigned["supervisor_user_id"] = uid
    updated = c.put(f"/api/projects/{pid}/construction/packages/{package['id']}", json=assigned)
    assert updated.status_code == 200, updated.text
    assert updated.json()["supervisor_name"]
    assert len(c.get(f"/api/projects/{pid}/memberships").json()) == members
    with maker() as db:
        from app.domains.engineering_documents.models import Drawing, DrawingRevision, StoredFile
        from app.domains.identity_projects.models import User
        from app.domains.supply_chain.models import MaterialRequirement

        org = db.query(User).filter_by(email="admin@alpha.test").one().organization_id
        stored = StoredFile(
            organization_id=org,
            sha256="a" * 64,
            size=4,
            content_type="text/plain",
            original_name="d.txt",
            storage_name="d",
            created_by=me["id"],
        )
        db.add(stored)
        db.flush()
        drawing = Drawing(
            organization_id=stored.organization_id,
            project_id=pid,
            number="C-1",
            number_key="c-1",
            title="Foundation",
            discipline_id=civil,
            company_id=company,
            created_by=me["id"],
        )
        db.add(drawing)
        db.flush()
        held = DrawingRevision(
            drawing_id=drawing.id,
            code="A",
            code_key="a",
            sequence=1,
            file_id=stored.id,
            release_state="Not Released",
            created_by=me["id"],
        )
        released = DrawingRevision(
            drawing_id=drawing.id,
            code="B",
            code_key="b",
            sequence=2,
            file_id=stored.id,
            release_state="Released",
            created_by=me["id"],
        )
        db.add_all([held, released])
        db.flush()
        held_id, released_id = held.id, released.id
        own = MaterialRequirement(
            organization_id=stored.organization_id,
            project_id=pid,
            number="MR-1",
            number_key="mr-1",
            company_id=company,
            discipline_id=civil,
            requested_by=me["id"],
            required_date=date(2026, 10, 7),
            purpose="Piles",
            created_by=me["id"],
        )
        db.add(own)
        db.commit()
        own_id = own.id
    other_project = new_project(c, code="CONST-2", client_company_id=me["company_id"]).json()["id"]
    with maker() as db:
        from app.domains.supply_chain.models import MaterialRequirement

        foreign = MaterialRequirement(
            organization_id=org,
            project_id=other_project,
            number="MR-X",
            number_key="mr-x",
            company_id=company,
            discipline_id=civil,
            requested_by=me["id"],
            required_date=date(2026, 10, 7),
            purpose="Other",
            created_by=me["id"],
        )
        db.add(foreign)
        db.commit()
        foreign_id = foreign.id
    blocked = dict(assigned)
    blocked["version"] = updated.json()["version"]
    blocked["revision_ids"] = [held_id]
    assert c.put(f"/api/projects/{pid}/construction/packages/{package['id']}", json=blocked).status_code == 422
    blocked["revision_ids"] = [released_id]
    blocked["requirement_ids"] = [foreign_id]
    assert c.put(f"/api/projects/{pid}/construction/packages/{package['id']}", json=blocked).status_code == 422
    blocked["requirement_ids"] = [own_id]
    linked = c.put(f"/api/projects/{pid}/construction/packages/{package['id']}", json=blocked)
    assert linked.status_code == 200, linked.text
    assert linked.json()["revisions"][0]["label"] == "C-1 rev B"
    assert linked.json()["requirements"][0]["number"] == "MR-1"
    cancelled = c.post(
        f"/api/projects/{pid}/construction/packages/{package['id']}/cancel",
        json={"reason": "Scope removed", "version": linked.json()["version"]},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "Cancelled"
    assert (
        c.post(
            f"/api/projects/{pid}/construction/activities",
            json={
                "package_id": package["id"],
                "code": "MORE",
                "name": "More piles",
                "quantity": "1",
                "unit": "no",
                "company_id": company,
                "measurement_method": "Item completion",
            },
        ).status_code
        == 409
    )


def _editable(package, **extra):
    body = dict(package)
    for key in (
        "id",
        "discipline_name",
        "area_name",
        "company_name",
        "responsible_name",
        "supervisor_name",
        "status",
        "release_state",
        "cancellation_reason",
        "revisions",
        "requirements",
        "activity_count",
        "release_open",
        "impact_state",
        "impact_detail",
        "impact_revision_id",
    ):
        body.pop(key, None)
    body.update(extra)
    return body


def _release_policy(discipline_id, reviewer_id):
    return {
        "record_type": "construction.release",
        "company_id": None,
        "discipline_id": discipline_id,
        "allow_self_approval": False,
        "stages": [
            {
                "name": "Construction release",
                "rule": "all",
                "quorum_count": 1,
                "reviewer_ids": [reviewer_id],
                "reviewers": [],
                "purpose": "Release this work package",
            }
        ],
    }


def test_release_follows_saved_reviewer_and_readiness(env):
    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    piping = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Piping")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="CONST-REL",
        client_company_id=me["company_id"],
        discipline_ids=[civil, piping],
        disciplines=[
            {"discipline_id": civil, "scope_description": "Civil", "active": True},
            {"discipline_id": piping, "scope_description": "Piping", "active": True},
        ],
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    area_id = c.post(
        f"/api/projects/{pid}/areas",
        json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""},
    ).json()["id"]
    with maker() as db:
        from app.domains.identity_projects.models import Membership, User

        person = db.query(User).filter_by(email="viewer@alpha.test").one()
        uid = person.id
        before = db.query(Membership).filter_by(project_id=pid, active=True).count()
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_release_policy(civil, me["id"])).status_code == 422
    assert (
        c.post(
            f"/api/projects/{pid}/memberships",
            json={
                "user_id": uid,
                "role_id": roles["Site Engineer"],
                "company_id": me["company_id"],
                "scope": "ALL",
                "discipline_ids": [],
            },
        ).status_code
        == 201
    )
    assert (
        c.post(
            f"/api/projects/{pid}/memberships",
            json={
                "user_id": me["id"],
                "role_id": roles["Discipline Head"],
                "company_id": me["company_id"],
                "scope": "ALL",
                "discipline_ids": [],
            },
        ).status_code
        == 201
    )
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_release_policy(civil, 999999)).status_code == 422
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_release_policy(civil, me["id"])).status_code == 201
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_release_policy(piping, uid)).status_code == 201
    other = new_project(
        c,
        code="CONST-OTHER",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    sign_in(c, "viewer@alpha.test")
    examples = c.post(f"/api/projects/{pid}/construction/templates/examples")
    assert examples.status_code == 201, examples.text
    template_id = next(row["id"] for row in examples.json()["templates"] if row["code"] == "CIV-CONC")
    saved = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(area_id, me["company_id"], civil, code="WP-REL"),
    )
    assert saved.status_code == 201, saved.text
    package = saved.json()
    sign_in(c)
    assert (
        c.post(
            f"/api/projects/{other.json()['id']}/construction/packages/{package['id']}/checks",
            json={"check_type": "Drawing", "classification": "Mandatory"},
        ).status_code
        == 404
    )
    sign_in(c, "viewer@alpha.test")
    drawing = c.post(
        f"/api/projects/{pid}/construction/packages/{package['id']}/checks",
        json={"check_type": "Drawing", "classification": "Mandatory", "owner_user_id": uid},
    )
    assert drawing.status_code == 201, drawing.text
    with maker() as db:
        from app.domains.identity_projects.models import Membership

        assert db.query(Membership).filter_by(project_id=pid, active=True).count() == before + 2
    check = next(row for row in drawing.json()["checks"] if row["check_type"] == "Drawing")
    refused = c.put(
        f"/api/projects/{pid}/construction/packages/{package['id']}/checks/{check['id']}",
        json={"status": "Satisfied", "evidence": "I looked at it", "version": check["version"]},
    )
    assert refused.status_code == 422, refused.text
    with maker() as db:
        from app.domains.engineering_documents.models import Drawing, DrawingRevision, StoredFile
        from app.domains.identity_projects.models import User

        org = db.query(User).filter_by(email="admin@alpha.test").one().organization_id
        stored = StoredFile(
            organization_id=org,
            sha256="b" * 64,
            size=4,
            content_type="text/plain",
            original_name="d.txt",
            storage_name="rel",
            created_by=me["id"],
        )
        db.add(stored)
        db.flush()
        record = Drawing(
            organization_id=org,
            project_id=pid,
            number="C-REL",
            number_key="c-rel",
            title="Foundation",
            discipline_id=civil,
            company_id=me["company_id"],
            created_by=me["id"],
        )
        db.add(record)
        db.flush()
        released = DrawingRevision(
            drawing_id=record.id,
            code="A",
            code_key="a",
            sequence=1,
            file_id=stored.id,
            release_state="Released",
            created_by=me["id"],
        )
        db.add(released)
        db.commit()
        released_id = released.id
    current = next(
        row for row in c.get(f"/api/projects/{pid}/construction/packages").json() if row["id"] == package["id"]
    )
    linked = c.put(
        f"/api/projects/{pid}/construction/packages/{package['id']}",
        json=_editable(
            current,
            revision_ids=[released_id],
            responsible_user_id=uid,
            planned_start="2026-10-08",
            planned_finish="2026-10-20",
        ),
    )
    assert linked.status_code == 200, linked.text
    activity = c.post(
        f"/api/projects/{pid}/construction/activities",
        json={
            "package_id": package["id"],
            "template_id": template_id,
            "code": "POUR",
            "name": "Concrete pour",
            "quantity": "10",
            "unit": "m3",
            "company_id": me["company_id"],
            "measurement_method": "Quantity",
            "predecessor_ids": [],
        },
    )
    assert activity.status_code == 201, activity.text
    card = next(
        row for row in c.get(f"/api/projects/{pid}/construction/readiness").json() if row["package"]["id"] == package["id"]
    )
    check = next(row for row in card["checks"] if row["check_type"] == "Drawing")
    satisfied = c.put(
        f"/api/projects/{pid}/construction/packages/{package['id']}/checks/{check['id']}",
        json={"status": "Satisfied", "evidence": "", "version": check["version"]},
    )
    assert satisfied.status_code == 200, satisfied.text
    material = c.post(
        f"/api/projects/{pid}/construction/packages/{package['id']}/checks",
        json={"check_type": "Material", "classification": "Advisory"},
    )
    assert material.status_code == 201, material.text
    material_row = next(row for row in material.json()["checks"] if row["check_type"] == "Material")
    assert material_row["status"] == "Not Checked"
    assert "stays Pending until a requirement is linked" in material_row["source_label"]
    workfront = c.post(
        f"/api/projects/{pid}/construction/packages/{package['id']}/checks",
        json={"check_type": "Workfront", "classification": "Mandatory"},
    )
    assert workfront.status_code == 201, workfront.text
    held = c.post(
        f"/api/projects/{pid}/construction/packages/{package['id']}/release",
        json={"version": workfront.json()["package"]["version"]},
    )
    assert held.status_code == 422, held.text
    assert "mandatory" in held.text.casefold()
    front = next(row for row in workfront.json()["checks"] if row["check_type"] == "Workfront")
    bare = c.put(
        f"/api/projects/{pid}/construction/packages/{package['id']}/checks/{front['id']}",
        json={"status": "Satisfied", "evidence": "", "version": front["version"]},
    )
    assert bare.status_code == 422, bare.text
    marked = c.put(
        f"/api/projects/{pid}/construction/packages/{package['id']}/checks/{front['id']}",
        json={"status": "Satisfied", "evidence": "Area is clear", "version": front["version"]},
    )
    assert marked.status_code == 200, marked.text
    permit = c.post(
        f"/api/projects/{pid}/construction/packages/{package['id']}/checks",
        json={"check_type": "Permit", "classification": "Advisory"},
    )
    assert permit.status_code == 201, permit.text
    assert "No inspection, permit, or schedule record was created" in permit.text
    submitted = c.post(
        f"/api/projects/{pid}/construction/packages/{package['id']}/release",
        json={"version": permit.json()["package"]["version"]},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["package"]["status"] == "Draft"
    assert submitted.json()["package"]["release_state"] == "In Review"
    assert any("Permit" in warning for warning in submitted.json()["warnings"])
    assert submitted.json()["snapshot"]["activities"][0]["baseline_quantity"] == "10.000"
    assert submitted.json()["snapshot"]["activities"][0]["inspection_points"]
    assert "No inspection, permit, or schedule record was created" in submitted.json()["snapshot"]["manual_note"]
    review = submitted.json()["review"]
    locked = c.put(
        f"/api/projects/{pid}/construction/packages/{package['id']}",
        json=_editable(submitted.json()["package"], name="Changed during review"),
    )
    assert locked.status_code == 409, locked.text
    own = c.post(
        f"/api/reviews/{review['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": review["version"]},
    )
    assert own.status_code == 403, own.text
    sign_in(c)
    approved = c.post(
        f"/api/reviews/{review['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": review["version"]},
    )
    assert approved.status_code == 200, approved.text
    ready = next(row for row in c.get(f"/api/projects/{pid}/construction/packages").json() if row["id"] == package["id"])
    assert ready["status"] == "Ready"
    assert ready["release_state"] == "Released"
    with maker() as db:
        from app.domains.engineering_documents.models import DrawingRevision

        revision = db.get(DrawingRevision, released_id)
        revision.release_state = "Superseded"
        db.commit()
    sign_in(c, "viewer@alpha.test")
    stopped = c.post(
        f"/api/projects/{pid}/construction/packages/{package['id']}/start",
        json={"version": ready["version"]},
    )
    assert stopped.status_code == 409, stopped.text
    still = next(row for row in c.get(f"/api/projects/{pid}/construction/packages").json() if row["id"] == package["id"])
    assert still["status"] == "Ready"
    with maker() as db:
        from app.domains.engineering_documents.models import DrawingRevision

        revision = db.get(DrawingRevision, released_id)
        revision.release_state = "Released"
        db.commit()
    started = c.post(
        f"/api/projects/{pid}/construction/packages/{package['id']}/start",
        json={"version": still["version"]},
    )
    assert started.status_code == 200, started.text
    assert started.json()["package"]["status"] == "In Progress"
    poured = next(row for row in c.get(f"/api/projects/{pid}/construction/activities").json() if row["code"] == "POUR")
    assert poured["baseline_quantity"] == "10.000"
    assert poured["quantity"] == "10.000"
    returned_package = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(
            area_id,
            me["company_id"],
            civil,
            code="WP-BACK",
            responsible_user_id=uid,
            planned_start="2026-10-08",
            planned_finish="2026-10-12",
        ),
    )
    assert returned_package.status_code == 201, returned_package.text
    back = returned_package.json()
    added = c.post(
        f"/api/projects/{pid}/construction/packages/{back['id']}/checks",
        json={"check_type": "Procedure", "classification": "Mandatory"},
    )
    procedure = next(row for row in added.json()["checks"] if row["check_type"] == "Procedure")
    marked = c.put(
        f"/api/projects/{pid}/construction/packages/{back['id']}/checks/{procedure['id']}",
        json={"status": "Satisfied", "evidence": "Method statement is on site", "version": procedure["version"]},
    )
    sent = c.post(
        f"/api/projects/{pid}/construction/packages/{back['id']}/release",
        json={"version": marked.json()["package"]["version"]},
    )
    assert sent.status_code == 200, sent.text
    sign_in(c)
    sent_back = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={
            "action": "return",
            "reason": "Confirm the method statement date",
            "comment": "",
            "version": sent.json()["review"]["version"],
        },
    )
    assert sent_back.status_code == 200, sent_back.text
    sign_in(c, "viewer@alpha.test")
    draft = next(row for row in c.get(f"/api/projects/{pid}/construction/packages").json() if row["id"] == back["id"])
    assert draft["status"] == "Draft"
    assert draft["release_state"] == "Returned"
    again = c.post(
        f"/api/projects/{pid}/construction/packages/{back['id']}/resubmit",
        json={"version": draft["version"]},
    )
    assert again.status_code == 200, again.text
    assert again.json()["package"]["release_state"] == "In Review"
    assert again.json()["package"]["status"] == "Draft"
    pipe = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(
            area_id,
            me["company_id"],
            piping,
            code="WP-SELF",
            responsible_user_id=uid,
            planned_start="2026-10-08",
            planned_finish="2026-10-12",
        ),
    )
    pipe_check = c.post(
        f"/api/projects/{pid}/construction/packages/{pipe.json()['id']}/checks",
        json={"check_type": "Workfront", "classification": "Mandatory"},
    )
    workfront = next(row for row in pipe_check.json()["checks"] if row["check_type"] == "Workfront")
    pipe_ready = c.put(
        f"/api/projects/{pid}/construction/packages/{pipe.json()['id']}/checks/{workfront['id']}",
        json={"status": "Satisfied", "evidence": "Area is handed to the crew", "version": workfront["version"]},
    )
    pipe_sent = c.post(
        f"/api/projects/{pid}/construction/packages/{pipe.json()['id']}/release",
        json={"version": pipe_ready.json()["package"]["version"]},
    )
    assert pipe_sent.status_code == 200, pipe_sent.text
    self_approval = c.post(
        f"/api/reviews/{pipe_sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": pipe_sent.json()["review"]["version"]},
    )
    assert self_approval.status_code == 403, self_approval.text
    sign_in(c)
    bypass = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(
            area_id,
            me["company_id"],
            piping,
            code="WP-ADMIN",
            responsible_user_id=uid,
            planned_start="2026-10-08",
            planned_finish="2026-10-12",
        ),
    )
    admin_check = c.post(
        f"/api/projects/{pid}/construction/packages/{bypass.json()['id']}/checks",
        json={"check_type": "Quality hold", "classification": "Mandatory"},
    )
    hold = next(row for row in admin_check.json()["checks"] if row["check_type"] == "Quality hold")
    admin_marked = c.put(
        f"/api/projects/{pid}/construction/packages/{bypass.json()['id']}/checks/{hold['id']}",
        json={"status": "Satisfied", "evidence": "The site record was read", "version": hold["version"]},
    )
    admin_sent = c.post(
        f"/api/projects/{pid}/construction/packages/{bypass.json()['id']}/release",
        json={"version": admin_marked.json()["package"]["version"]},
    )
    assert admin_sent.status_code == 200, admin_sent.text
    refused_admin = c.post(
        f"/api/reviews/{admin_sent.json()['review']['id']}/decisions",
        json={
            "action": "approve",
            "reason": "",
            "comment": "",
            "version": admin_sent.json()["review"]["version"],
        },
    )
    assert refused_admin.status_code == 403, refused_admin.text
    sign_in(c, "viewer@alpha.test")
    accepted = c.post(
        f"/api/reviews/{admin_sent.json()['review']['id']}/decisions",
        json={
            "action": "approve",
            "reason": "",
            "comment": "",
            "version": admin_sent.json()["review"]["version"],
        },
    )
    assert accepted.status_code == 200, accepted.text
    released_row = next(
        row for row in c.get(f"/api/projects/{pid}/construction/packages").json() if row["id"] == bypass.json()["id"]
    )
    assert released_row["status"] == "Ready"
    assert released_row["release_state"] == "Released"


def _progress_policy(discipline_id, reviewer_id):
    return {
        "record_type": "construction.progress",
        "company_id": None,
        "discipline_id": discipline_id,
        "allow_self_approval": False,
        "stages": [
            {
                "name": "Quantity verification",
                "rule": "all",
                "quorum_count": 1,
                "reviewer_ids": [reviewer_id],
                "reviewers": [],
                "purpose": "Verify the executed quantity",
            }
        ],
    }


def _report(area_id, company_id, discipline_id, engineer_id, number="DPR-1"):
    return {
        "number": number,
        "report_date": "2026-10-07",
        "shift": "Day",
        "discipline_id": discipline_id,
        "area_id": area_id,
        "company_id": company_id,
        "site_engineer_id": engineer_id,
        "weather": "Clear",
        "remarks": "Day shift",
    }


def test_daily_progress_keeps_verified_separate_from_acceptance(env):
    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    piping = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Piping")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="CONST-DAY",
        client_company_id=me["company_id"],
        discipline_ids=[civil, piping],
        disciplines=[
            {"discipline_id": civil, "scope_description": "Civil", "active": True},
            {"discipline_id": piping, "scope_description": "Piping", "active": True},
        ],
    )
    pid = created.json()["id"]
    area_id = c.post(
        f"/api/projects/{pid}/areas",
        json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""},
    ).json()["id"]
    with maker() as db:
        from app.domains.identity_projects.models import User

        uid = db.query(User).filter_by(email="viewer@alpha.test").one().id
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_progress_policy(civil, 999999)).status_code == 422
    for user_id, role in ((uid, "Site Engineer"), (me["id"], "Discipline Head")):
        assert (
            c.post(
                f"/api/projects/{pid}/memberships",
                json={
                    "user_id": user_id,
                    "role_id": roles[role],
                    "company_id": me["company_id"],
                    "scope": "ALL",
                    "discipline_ids": [],
                },
            ).status_code
            == 201
        )
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_progress_policy(civil, me["id"])).status_code == 201
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_progress_policy(piping, uid)).status_code == 201
    other = new_project(
        c,
        code="CONST-DAY2",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    sign_in(c, "viewer@alpha.test")
    package = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(area_id, me["company_id"], civil, code="WP-DAY"),
    ).json()
    pipe = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(area_id, me["company_id"], piping, code="WP-PIPE"),
    ).json()
    held = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(area_id, me["company_id"], civil, code="WP-HOLD"),
    ).json()

    def activity(package_id, code, method, quantity):
        saved = c.post(
            f"/api/projects/{pid}/construction/activities",
            json={
                "package_id": package_id,
                "code": code,
                "name": code,
                "quantity": quantity,
                "unit": "m3",
                "company_id": me["company_id"],
                "measurement_method": method,
                "predecessor_ids": [],
            },
        )
        assert saved.status_code == 201, saved.text
        return saved.json()

    pour = activity(package["id"], "POUR", "Quantity", "10")
    items = activity(package["id"], "ITEMS", "Item completion", "2")
    marks = activity(package["id"], "MARKS", "Weighted milestones", "1")
    pipes = activity(pipe["id"], "SPOOL", "Quantity", "10")
    held_activity = activity(held["id"], "HELD", "Quantity", "5")
    item = c.post(
        f"/api/projects/{pid}/construction/items",
        json={"activity_id": items["id"], "identifier": "P-1", "description": "Pile 1", "item_kind": "Pile"},
    )
    assert item.status_code == 201, item.text
    with maker() as db:
        from app.domains.construction.models import WorkPackage

        for package_id in (package["id"], pipe["id"]):
            row = db.get(WorkPackage, package_id)
            row.status = "In Progress"
            row.release_state = "Released"
        db.commit()
    report = c.post(f"/api/projects/{pid}/construction/progress", json=_report(area_id, me["company_id"], civil, uid))
    assert report.status_code == 201, report.text
    report_id = report.json()["id"]
    sign_in(c)
    assert (
        c.post(
            f"/api/projects/{other.json()['id']}/construction/progress/{report_id}/lines",
            json={"activity_id": pour["id"], "quantity": "1"},
        ).status_code
        == 404
    )
    sign_in(c, "viewer@alpha.test")
    blocked = c.post(
        f"/api/projects/{pid}/construction/progress/{report_id}/lines",
        json={"activity_id": held_activity["id"], "quantity": "1"},
    )
    assert blocked.status_code == 422, blocked.text
    added = c.post(
        f"/api/projects/{pid}/construction/progress/{report_id}/lines",
        json={"activity_id": pour["id"], "quantity": "6", "crew_reference": "Crew A", "material_reference": "Cement"},
    )
    assert added.status_code == 201, added.text
    worked = next(row for row in added.json()["lines"] if row["quantity"] == "6.000" and not row["rework"])
    assert worked["unit"] == "m3"
    assert "not proof of installation" in worked["source_note"]
    too_much = c.post(
        f"/api/projects/{pid}/construction/progress/{report_id}/lines",
        json={"activity_id": pour["id"], "quantity": "6"},
    )
    assert too_much.status_code == 422, too_much.text
    rework = c.post(
        f"/api/projects/{pid}/construction/progress/{report_id}/lines",
        json={"activity_id": pour["id"], "quantity": "6", "rework": True, "evidence": "Broke out and redid"},
    )
    assert rework.status_code == 201, rework.text
    submitted = c.post(
        f"/api/projects/{pid}/construction/progress/{report_id}/submit",
        json={"version": rework.json()["version"]},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "Pending Review"
    own = c.post(
        f"/api/reviews/{submitted.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": submitted.json()["review"]["version"]},
    )
    assert own.status_code == 403, own.text
    sign_in(c)
    approved = c.post(
        f"/api/reviews/{submitted.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": submitted.json()["review"]["version"]},
    )
    assert approved.status_code == 200, approved.text
    sign_in(c, "viewer@alpha.test")
    board = c.get(f"/api/projects/{pid}/construction/progress").json()
    measured = next(row for row in board["activities"] if row["activity_id"] == pour["id"])
    assert measured["scope_quantity"] == "10.000"
    assert measured["reported_quantity"] == "6.000"
    assert measured["verified_quantity"] == "6.000"
    assert measured["rework_quantity"] == "6.000"
    assert measured["verified_percent"] == "60.00"
    assert measured["accepted_quantity"] is None
    assert measured["certified_quantity"] is None
    assert "does not accept" in measured["accepted_note"]
    duplicate = c.post(
        f"/api/projects/{pid}/construction/progress",
        json=_report(area_id, me["company_id"], civil, uid, number="DPR-DUP"),
    )
    dup_line = c.post(
        f"/api/projects/{pid}/construction/progress/{duplicate.json()['id']}/lines",
        json={"activity_id": pour["id"], "quantity": "1"},
    )
    dup_sent = c.post(
        f"/api/projects/{pid}/construction/progress/{duplicate.json()['id']}/submit",
        json={"version": dup_line.json()["version"]},
    )
    assert dup_sent.status_code == 200, dup_sent.text
    assert any("same date and shift" in warning for warning in dup_sent.json()["warnings"])
    sign_in(c)
    sent_back = c.post(
        f"/api/reviews/{dup_sent.json()['review']['id']}/decisions",
        json={
            "action": "return",
            "reason": "Confirm the extra quantity",
            "comment": "",
            "version": dup_sent.json()["review"]["version"],
        },
    )
    assert sent_back.status_code == 200, sent_back.text
    sign_in(c, "viewer@alpha.test")
    over = c.post(
        f"/api/projects/{pid}/construction/progress",
        json=_report(area_id, me["company_id"], civil, uid, number="DPR-OVER"),
    )
    over_line = c.post(
        f"/api/projects/{pid}/construction/progress/{over.json()['id']}/lines",
        json={"activity_id": pour["id"], "quantity": "5"},
    )
    assert over_line.status_code == 422, over_line.text
    correction = c.post(
        f"/api/projects/{pid}/construction/progress",
        json=_report(area_id, me["company_id"], civil, uid, number="DPR-REV"),
    )
    corrected = c.post(
        f"/api/projects/{pid}/construction/progress/{correction.json()['id']}/lines",
        json={"activity_id": pour["id"], "quantity": "6", "reverses_line_id": worked["id"], "evidence": "Wrong pour"},
    )
    assert corrected.status_code == 201, corrected.text
    assert any(row["reverses_line_id"] == worked["id"] and row["quantity"] == "6.000" for row in corrected.json()["lines"])
    still = next(row for row in c.get(f"/api/projects/{pid}/construction/progress").json()["activities"] if row["activity_id"] == pour["id"])
    assert still["verified_quantity"] == "6.000"
    sent_fix = c.post(
        f"/api/projects/{pid}/construction/progress/{correction.json()['id']}/submit",
        json={"version": corrected.json()["version"]},
    )
    sign_in(c)
    fixed = c.post(
        f"/api/reviews/{sent_fix.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": sent_fix.json()["review"]["version"]},
    )
    assert fixed.status_code == 200, fixed.text
    sign_in(c, "viewer@alpha.test")
    after = next(row for row in c.get(f"/api/projects/{pid}/construction/progress").json()["activities"] if row["activity_id"] == pour["id"])
    assert after["verified_quantity"] == "0.000"
    original = next(row for row in c.get(f"/api/projects/{pid}/construction/progress").json()["reports"] if row["number"] == "DPR-1")
    assert original["status"] == "Approved"
    assert any(row["id"] == worked["id"] and row["quantity"] == "6.000" for row in original["lines"])
    missing_item = c.post(
        f"/api/projects/{pid}/construction/progress",
        json=_report(area_id, me["company_id"], civil, uid, number="DPR-ITEM"),
    )
    assert (
        c.post(
            f"/api/projects/{pid}/construction/progress/{missing_item.json()['id']}/lines",
            json={"activity_id": items["id"], "quantity": "1"},
        ).status_code
        == 422
    )
    item_line = c.post(
        f"/api/projects/{pid}/construction/progress/{missing_item.json()['id']}/lines",
        json={"activity_id": items["id"], "item_id": item.json()["id"], "quantity": "1"},
    )
    item_sent = c.post(
        f"/api/projects/{pid}/construction/progress/{missing_item.json()['id']}/submit",
        json={"version": item_line.json()["version"]},
    )
    sign_in(c)
    assert (
        c.post(
            f"/api/reviews/{item_sent.json()['review']['id']}/decisions",
            json={"action": "approve", "reason": "", "comment": "", "version": item_sent.json()["review"]["version"]},
        ).status_code
        == 200
    )
    sign_in(c, "viewer@alpha.test")
    item_measure = next(
        row for row in c.get(f"/api/projects/{pid}/construction/progress").json()["activities"] if row["activity_id"] == items["id"]
    )
    assert item_measure["verified_quantity"] == "1.000"
    assert item_measure["verified_percent"] == "50.00"
    assert item_measure["accepted_quantity"] is None
    open_marks = next(
        row for row in c.get(f"/api/projects/{pid}/construction/progress").json()["activities"] if row["activity_id"] == marks["id"]
    )
    assert open_marks["verified_percent"] is None
    saved_marks = c.put(
        f"/api/projects/{pid}/construction/activities/{marks['id']}/milestones",
        json={"milestones": [{"name": "Set", "weight": "40"}, {"name": "Weld", "weight": "60"}]},
    )
    assert saved_marks.status_code == 200, saved_marks.text
    weld = next(row["id"] for row in saved_marks.json()["milestones"] if row["name"] == "Weld")
    claimed = c.post(
        f"/api/projects/{pid}/construction/progress",
        json=_report(area_id, me["company_id"], civil, uid, number="DPR-MS"),
    )
    claim = c.post(
        f"/api/projects/{pid}/construction/progress/{claimed.json()['id']}/lines",
        json={"activity_id": marks["id"], "milestone_id": weld, "evidence": "Weld is complete"},
    )
    assert claim.status_code == 201, claim.text
    claim_sent = c.post(
        f"/api/projects/{pid}/construction/progress/{claimed.json()['id']}/submit",
        json={"version": claim.json()["version"]},
    )
    sign_in(c)
    assert (
        c.post(
            f"/api/reviews/{claim_sent.json()['review']['id']}/decisions",
            json={"action": "approve", "reason": "", "comment": "", "version": claim_sent.json()["review"]["version"]},
        ).status_code
        == 200
    )
    sign_in(c, "viewer@alpha.test")
    marked = next(
        row for row in c.get(f"/api/projects/{pid}/construction/progress").json()["activities"] if row["activity_id"] == marks["id"]
    )
    assert marked["verified_percent"] == "60.00"
    assert marked["accepted_quantity"] is None
    again = c.post(
        f"/api/projects/{pid}/construction/progress",
        json=_report(area_id, me["company_id"], civil, uid, number="DPR-MS2"),
    )
    assert (
        c.post(
            f"/api/projects/{pid}/construction/progress/{again.json()['id']}/lines",
            json={"activity_id": marks["id"], "milestone_id": weld, "evidence": "Weld again"},
        ).status_code
        == 422
    )
    redone = c.post(
        f"/api/projects/{pid}/construction/progress/{again.json()['id']}/lines",
        json={"activity_id": marks["id"], "milestone_id": weld, "evidence": "Weld repaired", "rework": True},
    )
    assert redone.status_code == 201, redone.text
    self_report = c.post(
        f"/api/projects/{pid}/construction/progress",
        json=_report(area_id, me["company_id"], piping, uid, number="DPR-SELF"),
    )
    self_line = c.post(
        f"/api/projects/{pid}/construction/progress/{self_report.json()['id']}/lines",
        json={"activity_id": pipes["id"], "quantity": "1"},
    )
    self_sent = c.post(
        f"/api/projects/{pid}/construction/progress/{self_report.json()['id']}/submit",
        json={"version": self_line.json()["version"]},
    )
    assert (
        c.post(
            f"/api/reviews/{self_sent.json()['review']['id']}/decisions",
            json={"action": "approve", "reason": "", "comment": "", "version": self_sent.json()["review"]["version"]},
        ).status_code
        == 403
    )
    sign_in(c)
    admin_report = c.post(
        f"/api/projects/{pid}/construction/progress",
        json=_report(area_id, me["company_id"], piping, uid, number="DPR-ADMIN"),
    )
    admin_line = c.post(
        f"/api/projects/{pid}/construction/progress/{admin_report.json()['id']}/lines",
        json={"activity_id": pipes["id"], "quantity": "1"},
    )
    admin_sent = c.post(
        f"/api/projects/{pid}/construction/progress/{admin_report.json()['id']}/submit",
        json={"version": admin_line.json()["version"]},
    )
    assert (
        c.post(
            f"/api/reviews/{admin_sent.json()['review']['id']}/decisions",
            json={"action": "approve", "reason": "", "comment": "", "version": admin_sent.json()["review"]["version"]},
        ).status_code
        == 403
    )
    sign_in(c, "viewer@alpha.test")
    accepted = c.post(
        f"/api/reviews/{admin_sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": admin_sent.json()["review"]["version"]},
    )
    assert accepted.status_code == 200, accepted.text
    released = next(
        row for row in c.get(f"/api/projects/{pid}/construction/progress").json()["reports"] if row["number"] == "DPR-ADMIN"
    )
    assert released["status"] == "Approved"


def test_stores_link_does_not_install_or_move_stock(env):
    from decimal import Decimal

    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="CONST-LINK",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    pid = created.json()["id"]
    other = new_project(
        c,
        code="CONST-LINK2",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    other_id = other.json()["id"]
    area_id = c.post(
        f"/api/projects/{pid}/areas",
        json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""},
    ).json()["id"]
    with maker() as db:
        from app.domains.identity_projects.models import User

        uid = db.query(User).filter_by(email="viewer@alpha.test").one().id
    for user_id, role in ((uid, "Site Engineer"), (me["id"], "Discipline Head")):
        assert (
            c.post(
                f"/api/projects/{pid}/memberships",
                json={
                    "user_id": user_id,
                    "role_id": roles[role],
                    "company_id": me["company_id"],
                    "scope": "ALL",
                    "discipline_ids": [],
                },
            ).status_code
            == 201
        )
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_progress_policy(civil, me["id"])).status_code == 201
    sign_in(c, "viewer@alpha.test")
    package = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(
            area_id,
            me["company_id"],
            civil,
            code="WP-LINK",
            planning_reference="PLAN-1",
            planned_start="2026-10-07",
            planned_finish="2026-10-08",
        ),
    )
    assert package.status_code == 201, package.text
    package_id = package.json()["id"]
    activity = c.post(
        f"/api/projects/{pid}/construction/activities",
        json={
            "package_id": package_id,
            "code": "POUR",
            "name": "Pour",
            "quantity": "10",
            "unit": "m3",
            "company_id": me["company_id"],
            "measurement_method": "Quantity",
            "predecessor_ids": [],
        },
    )
    assert activity.status_code == 201, activity.text
    for check_type in ("Manpower", "Permit", "Inspection", "Quality hold"):
        saved = c.post(
            f"/api/projects/{pid}/construction/packages/{package_id}/checks",
            json={"check_type": check_type, "classification": "Advisory"},
        )
        assert saved.status_code == 201, saved.text
    held = {}
    with maker() as db:
        from app.domains.construction.models import WorkPackage
        from app.domains.identity_projects.models import Project
        from app.domains.supply_chain.models import (
            ProcurementItem,
            StockBalance,
            StockPosting,
            StockPostingLine,
            Warehouse,
        )

        row = db.get(WorkPackage, package_id)
        row.status = "In Progress"
        row.release_state = "Released"
        project = db.get(Project, pid)
        item = ProcurementItem(
            organization_id=project.organization_id,
            code="CEM-LINK",
            code_key="cem-link",
            description="Cement",
            item_type="Material",
            category="Civil",
            discipline_ids=[],
            base_unit="bag",
            created_by=me["id"],
        )
        db.add(item)
        db.flush()
        warehouse = Warehouse(
            organization_id=project.organization_id,
            project_id=pid,
            code="WH-LINK",
            code_key="wh-link",
            name="Site store",
            officer_id=me["id"],
            created_by=me["id"],
        )
        db.add(warehouse)
        db.flush()
        balance = StockBalance(
            organization_id=project.organization_id,
            project_id=pid,
            warehouse_id=warehouse.id,
            item_id=item.id,
            unit="bag",
            on_hand=Decimal("10.000"),
            reserved=Decimal("4.000"),
        )
        db.add(balance)

        def posting(project_row, kind, number, status="Posted"):
            saved = StockPosting(
                organization_id=project_row.organization_id,
                project_id=project_row.id,
                warehouse_id=warehouse.id,
                number=number,
                number_key=number.casefold(),
                kind=kind,
                status=status,
                created_by=me["id"],
            )
            db.add(saved)
            db.flush()
            if status == "Posted" and kind in {"Issue", "Reserve", "Accept"}:
                db.add(
                    StockPostingLine(
                        posting_id=saved.id,
                        item_id=item.id,
                        quantity=Decimal("20.000"),
                        unit="bag",
                    )
                )
            return saved.id

        other_project = db.get(Project, other_id)
        held["balance"] = balance.id
        held["issue"] = posting(project, "Issue", "ISS-LINK")
        held["reserve"] = posting(project, "Reserve", "RES-LINK")
        held["accept"] = posting(project, "Accept", "ACC-LINK")
        held["cancelled"] = posting(project, "Issue", "ISS-CANCEL", "Cancelled")
        held["foreign"] = posting(other_project, "Issue", "ISS-OTHER")
        held["count"] = db.query(StockPosting).filter_by(project_id=pid).count()
        db.commit()
    report = c.post(f"/api/projects/{pid}/construction/progress", json=_report(area_id, me["company_id"], civil, uid))
    assert report.status_code == 201, report.text
    report_id = report.json()["id"]
    for posting_id in (held["accept"], held["cancelled"], held["foreign"], 999999):
        refused = c.post(
            f"/api/projects/{pid}/construction/progress/{report_id}/lines",
            json={"activity_id": activity.json()["id"], "quantity": "1", "stock_posting_id": posting_id},
        )
        assert refused.status_code == 422, refused.text
        assert "posted issue or reservation" in refused.text
    linked = c.post(
        f"/api/projects/{pid}/construction/progress/{report_id}/lines",
        json={
            "activity_id": activity.json()["id"],
            "quantity": "2",
            "crew_reference": "Crew A",
            "equipment_hours": "1.5",
            "stock_posting_id": held["issue"],
        },
    )
    assert linked.status_code == 201, linked.text
    worked = next(row for row in linked.json()["lines"] if row["quantity"] == "2.000")
    assert worked["stores"]["number"] == "ISS-LINK"
    assert worked["stores"]["kind"] == "Issue"
    assert worked["stores"]["quantity_label"] == "20.000 bag"
    assert worked["stores"]["note"] == "This stores quantity is not the installed quantity."
    assert "was not changed" in worked["source_note"]
    assert "not proof of installation" in worked["source_note"]
    plain = c.post(
        f"/api/projects/{pid}/construction/progress/{report_id}/lines",
        json={"activity_id": activity.json()["id"], "quantity": "1", "material_reference": "Cement note"},
    )
    assert plain.status_code == 201, plain.text
    noted = next(row for row in plain.json()["lines"] if row["quantity"] == "1.000")
    assert noted["stores"] is None
    assert "No attendance, equipment, or stores record was created" in noted["source_note"]
    links = c.get(f"/api/projects/{pid}/construction/connections")
    assert links.status_code == 200, links.text
    body = links.json()
    numbers = {row["number"] for row in body["stores"]["postings"]}
    assert numbers == {"ISS-LINK", "RES-LINK"}
    assert "not the installed quantity" in body["stores"]["note"]
    plan = next(row for row in body["planning"]["packages"] if row["code"] == "WP-LINK")
    assert plan["planned_start"] == "2026-10-07"
    assert plan["planned_finish"] == "2026-10-08"
    assert plan["planning_reference"] == "PLAN-1"
    assert "No schedule baseline" in body["planning"]["note"]
    assert body["hr"]["crew"] == [
        {"report_number": "DPR-1", "activity_code": "POUR", "crew_reference": "Crew A"}
    ]
    assert "No attendance" in body["hr"]["note"]
    assert any(row["check_type"] == "Manpower" for row in body["hr"]["checks"])
    assert body["equipment"]["entries"][0]["equipment_hours"] == "1.50"
    assert "No equipment register" in body["equipment"]["note"]
    assert any(row["check_type"] == "Permit" for row in body["hse"]["checks"])
    assert "No work permit" in body["hse"]["note"]
    assert {row["check_type"] for row in body["qa"]["checks"]} == {"Inspection", "Quality hold"}
    assert "No inspection result" in body["qa"]["note"]
    assert body["qa"]["accepted"] == "not open"
    submitted = c.post(
        f"/api/projects/{pid}/construction/progress/{report_id}/submit",
        json={"version": plain.json()["version"]},
    )
    assert submitted.status_code == 200, submitted.text
    sign_in(c)
    approved = c.post(
        f"/api/reviews/{submitted.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": submitted.json()["review"]["version"]},
    )
    assert approved.status_code == 200, approved.text
    sign_in(c, "viewer@alpha.test")
    measured = next(
        row
        for row in c.get(f"/api/projects/{pid}/construction/progress").json()["activities"]
        if row["activity_code"] == "POUR"
    )
    assert measured["verified_quantity"] == "3.000"
    assert measured["verified_percent"] == "30.00"
    assert measured["accepted_quantity"] is None
    assert measured["certified_quantity"] is None
    with maker() as db:
        from app.domains.supply_chain.models import StockBalance, StockPosting

        balance = db.get(StockBalance, held["balance"])
        assert balance.on_hand == Decimal("10.000")
        assert balance.reserved == Decimal("4.000")
        assert db.query(StockPosting).filter_by(project_id=pid).count() == held["count"]


def _release_policy(discipline_id, reviewer_id):
    body = _progress_policy(discipline_id, reviewer_id)
    body["record_type"] = "construction.release"
    return body


def test_hold_blocks_progress_until_release_reviewer_resumes(env):
    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="CONST-HOLD",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    pid = created.json()["id"]
    area_id = c.post(
        f"/api/projects/{pid}/areas",
        json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""},
    ).json()["id"]
    with maker() as db:
        from app.domains.identity_projects.models import User

        uid = db.query(User).filter_by(email="viewer@alpha.test").one().id
    for user_id, role in ((uid, "Site Engineer"), (me["id"], "Project Manager")):
        assert (
            c.post(
                f"/api/projects/{pid}/memberships",
                json={
                    "user_id": user_id,
                    "role_id": roles[role],
                    "company_id": me["company_id"],
                    "scope": "ALL",
                    "discipline_ids": [],
                },
            ).status_code
            == 201
        )
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_release_policy(civil, me["id"])).status_code == 201
    sign_in(c, "viewer@alpha.test")
    package = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(area_id, me["company_id"], civil, code="WP-HOLD"),
    )
    assert package.status_code == 201, package.text
    draft = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(area_id, me["company_id"], civil, code="WP-DRAFT"),
    )
    assert draft.status_code == 201, draft.text
    activity = c.post(
        f"/api/projects/{pid}/construction/activities",
        json={
            "package_id": package.json()["id"],
            "code": "POUR",
            "name": "Pour",
            "quantity": "10",
            "unit": "m3",
            "company_id": me["company_id"],
            "measurement_method": "Quantity",
            "predecessor_ids": [],
        },
    )
    assert activity.status_code == 201, activity.text
    with maker() as db:
        from app.domains.construction.models import WorkPackage

        row = db.get(WorkPackage, package.json()["id"])
        row.status = "In Progress"
        row.release_state = "Released"
        db.commit()
    refused = c.post(
        f"/api/projects/{pid}/construction/packages/{draft.json()['id']}/hold",
        json={"reason": "Too early", "version": draft.json()["version"]},
    )
    assert refused.status_code == 409, refused.text
    blocked = c.post(
        f"/api/projects/{pid}/construction/blockers",
        json={
            "package_id": draft.json()["id"],
            "kind": "Delay",
            "description": "Draft work is not blocked here",
            "owner_user_id": uid,
            "recovery_note": "Leave the draft alone",
        },
    )
    assert blocked.status_code == 422, blocked.text
    held = c.post(
        f"/api/projects/{pid}/construction/packages/{package.json()['id']}/hold",
        json={"reason": "Crane is blocked", "version": package.json()["version"]},
    )
    assert held.status_code == 200, held.text
    assert held.json()["package_status"] == "On Hold"
    assert held.json()["release_state"] == "Released"
    assert held.json()["status"] == "Open"
    assert "does not create an inspection" in held.json()["note"]
    report = c.post(
        f"/api/projects/{pid}/construction/progress",
        json=_report(area_id, me["company_id"], civil, uid, number="DPR-HOLD"),
    )
    assert report.status_code == 201, report.text
    paused = c.post(
        f"/api/projects/{pid}/construction/progress/{report.json()['id']}/lines",
        json={"activity_id": activity.json()["id"], "quantity": "1"},
    )
    assert paused.status_code == 422, paused.text
    assert "on hold" in paused.text
    stranger = c.post(
        f"/api/projects/{pid}/construction/blockers",
        json={
            "package_id": package.json()["id"],
            "kind": "Weather",
            "description": "Rain stopped the pour",
            "owner_user_id": 999999,
            "recovery_note": "Wait for a dry shift",
        },
    )
    assert stranger.status_code == 422, stranger.text
    blocker = c.post(
        f"/api/projects/{pid}/construction/blockers",
        json={
            "package_id": package.json()["id"],
            "kind": "Obstruction",
            "description": "Access road is closed",
            "owner_user_id": uid,
            "recovery_note": "Open the access road",
        },
    )
    assert blocker.status_code == 201, blocker.text
    resolved = c.post(
        f"/api/projects/{pid}/construction/blockers/{blocker.json()['id']}/resolve",
        json={"resolution_note": "Road is open", "version": blocker.json()["version"]},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "Resolved"
    sent = c.post(
        f"/api/projects/{pid}/construction/holds/{held.json()['id']}/resume",
        json={"version": held.json()["version"]},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "In Review"
    assert sent.json()["package_status"] == "On Hold"
    own = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": sent.json()["review"]["version"]},
    )
    assert own.status_code == 403, own.text
    sign_in(c)
    rejected = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={
            "action": "reject",
            "reason": "The crane is still blocked",
            "comment": "",
            "version": sent.json()["review"]["version"],
        },
    )
    assert rejected.status_code == 200, rejected.text
    sign_in(c, "viewer@alpha.test")
    waiting = c.get(f"/api/projects/{pid}/construction/monitoring").json()
    pause = waiting["holds"][0]
    assert pause["status"] == "Rejected"
    assert pause["package_status"] == "On Hold"
    assert pause["release_state"] == "Released"
    still = c.post(
        f"/api/projects/{pid}/construction/progress/{report.json()['id']}/lines",
        json={"activity_id": activity.json()["id"], "quantity": "1"},
    )
    assert still.status_code == 422, still.text
    again = c.post(
        f"/api/projects/{pid}/construction/holds/{pause['id']}/resume",
        json={"version": pause["version"]},
    )
    assert again.status_code == 200, again.text
    sign_in(c)
    approved = c.post(
        f"/api/reviews/{again.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": again.json()["review"]["version"]},
    )
    assert approved.status_code == 200, approved.text
    sign_in(c, "viewer@alpha.test")
    resumed = next(
        row for row in c.get(f"/api/projects/{pid}/construction/monitoring").json()["packages"] if row["code"] == "WP-HOLD"
    )
    assert resumed["status"] == "In Progress"
    assert resumed["release_state"] == "Released"
    old = _report(area_id, me["company_id"], civil, uid, number="DPR-OLD")
    old["report_date"] = "2020-01-01"
    dated = c.post(f"/api/projects/{pid}/construction/progress", json=old)
    assert dated.status_code == 201, dated.text
    worked = c.post(
        f"/api/projects/{pid}/construction/progress/{dated.json()['id']}/lines",
        json={"activity_id": activity.json()["id"], "quantity": "1", "rework": True, "evidence": "Broke out and redid"},
    )
    assert worked.status_code == 201, worked.text
    board = c.get(f"/api/projects/{pid}/construction/progress").json()
    measured = next(row for row in board["activities"] if row["activity_code"] == "POUR")
    assert measured["verified_quantity"] == "0.000"
    assert measured["rework_quantity"] == "1.000"
    assert measured["accepted_quantity"] is None
    monitor = c.get(f"/api/projects/{pid}/construction/monitoring").json()
    assert monitor["rework"][0]["quantity"] == "1.000"
    assert "stays out of verified progress" in monitor["rework_note"]
    assert any(row["number"] == "DPR-OLD" and row["status"] == "Draft" for row in monitor["overdue_reports"])
    assert any(row["status"] == "Resolved" and row["kind"] == "Obstruction" for row in monitor["blockers"])
    sign_in(c)
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_release_policy(civil, uid)).status_code == 201
    second = c.post(
        f"/api/projects/{pid}/construction/packages/{package.json()['id']}/hold",
        json={"reason": "Night shift stopped", "version": resumed["version"]},
    )
    assert second.status_code == 200, second.text
    asked = c.post(
        f"/api/projects/{pid}/construction/holds/{second.json()['id']}/resume",
        json={"version": second.json()["version"]},
    )
    assert asked.status_code == 200, asked.text
    bypass = c.post(
        f"/api/reviews/{asked.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": asked.json()["review"]["version"]},
    )
    assert bypass.status_code == 403, bypass.text
    sign_in(c, "viewer@alpha.test")
    finished = c.post(
        f"/api/reviews/{asked.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": asked.json()["review"]["version"]},
    )
    assert finished.status_code == 200, finished.text
    final = next(
        row for row in c.get(f"/api/projects/{pid}/construction/monitoring").json()["packages"] if row["code"] == "WP-HOLD"
    )
    assert final["status"] == "In Progress"
    assert final["release_state"] == "Released"
    for email in ("viewer@alpha.test", "admin@alpha.test"):
        sign_in(c, email)
        titles = [row["title"] for row in c.get("/api/notifications").json()]
        assert "Work on hold" in titles
        assert "Construction blocker" in titles
        assert "Work resumed" in titles
    with maker() as db:
        from app.domains.construction.models import ReadinessCheck
        from app.domains.coordination.models import Job

        assert db.query(ReadinessCheck).count() == 0
        assert db.query(Job).filter(Job.kind.ilike("%mail%")).count() == 0


def _handover_policy(discipline_id, reviewer_id):
    body = _progress_policy(discipline_id, reviewer_id)
    body["record_type"] = "construction.handover"
    body["stages"][0]["name"] = "Handover"
    body["stages"][0]["purpose"] = "Confirm the construction handover dossier"
    return body


def test_handover_records_verified_quantity_without_commissioning(env):
    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="CONST-HAND",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    pid = created.json()["id"]
    area_id = c.post(
        f"/api/projects/{pid}/areas",
        json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""},
    ).json()["id"]
    with maker() as db:
        from app.domains.identity_projects.models import User

        uid = db.query(User).filter_by(email="viewer@alpha.test").one().id
    for user_id, role in ((uid, "Site Engineer"), (me["id"], "Project Manager")):
        assert (
            c.post(
                f"/api/projects/{pid}/memberships",
                json={
                    "user_id": user_id,
                    "role_id": roles[role],
                    "company_id": me["company_id"],
                    "scope": "ALL",
                    "discipline_ids": [],
                },
            ).status_code
            == 201
        )
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_progress_policy(civil, me["id"])).status_code == 201
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_release_policy(civil, me["id"])).status_code == 201
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_handover_policy(civil, me["id"])).status_code == 201
    sign_in(c, "viewer@alpha.test")
    package = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(area_id, me["company_id"], civil, code="WP-HAND"),
    )
    assert package.status_code == 201, package.text
    package_id = package.json()["id"]
    activity = c.post(
        f"/api/projects/{pid}/construction/activities",
        json={
            "package_id": package_id,
            "code": "POUR",
            "name": "Pour",
            "quantity": "10",
            "unit": "m3",
            "company_id": me["company_id"],
            "measurement_method": "Quantity",
            "predecessor_ids": [],
        },
    )
    assert activity.status_code == 201, activity.text
    check = c.post(
        f"/api/projects/{pid}/construction/packages/{package_id}/checks",
        json={"check_type": "Workfront", "classification": "Mandatory"},
    )
    assert check.status_code == 201, check.text
    workfront = next(row for row in check.json()["checks"] if row["check_type"] == "Workfront")
    satisfied = c.put(
        f"/api/projects/{pid}/construction/packages/{package_id}/checks/{workfront['id']}",
        json={"status": "Satisfied", "evidence": "Crane is clear", "version": workfront["version"]},
    )
    assert satisfied.status_code == 200, satisfied.text
    with maker() as db:
        from app.domains.construction.models import WorkPackage

        row = db.get(WorkPackage, package_id)
        row.status = "In Progress"
        row.release_state = "Released"
        db.commit()
    dossier = c.post(
        f"/api/projects/{pid}/construction/handover",
        json={"number": "HO-1", "package_id": package_id},
    )
    assert dossier.status_code == 201, dossier.text
    assert "No commissioning test" in dossier.json()["statement"]
    early = c.post(
        f"/api/projects/{pid}/construction/handover/{dossier.json()['id']}/submit",
        json={"version": dossier.json()["version"]},
    )
    assert early.status_code == 422, early.text
    assert "below the approved scope" in early.text
    report = c.post(
        f"/api/projects/{pid}/construction/progress",
        json=_report(area_id, me["company_id"], civil, uid, number="DPR-HAND"),
    )
    assert report.status_code == 201, report.text
    worked = c.post(
        f"/api/projects/{pid}/construction/progress/{report.json()['id']}/lines",
        json={"activity_id": activity.json()["id"], "quantity": "10"},
    )
    rework = c.post(
        f"/api/projects/{pid}/construction/progress/{report.json()['id']}/lines",
        json={"activity_id": activity.json()["id"], "quantity": "1", "rework": True, "evidence": "Broke out and redid"},
    )
    assert rework.status_code == 201, rework.text
    submitted = c.post(
        f"/api/projects/{pid}/construction/progress/{report.json()['id']}/submit",
        json={"version": rework.json()["version"]},
    )
    assert submitted.status_code == 200, submitted.text
    sign_in(c)
    assert (
        c.post(
            f"/api/reviews/{submitted.json()['review']['id']}/decisions",
            json={"action": "approve", "reason": "", "comment": "", "version": submitted.json()["review"]["version"]},
        ).status_code
        == 200
    )
    sign_in(c, "viewer@alpha.test")
    held = c.post(
        f"/api/projects/{pid}/construction/packages/{package_id}/hold",
        json={"reason": "Crane is blocked", "version": package.json()["version"]},
    )
    assert held.status_code == 200, held.text
    paused = c.post(
        f"/api/projects/{pid}/construction/handover/{dossier.json()['id']}/submit",
        json={"version": dossier.json()["version"]},
    )
    assert paused.status_code == 422, paused.text
    assert "Resume the work package" in paused.text
    asked = c.post(
        f"/api/projects/{pid}/construction/holds/{held.json()['id']}/resume",
        json={"version": held.json()["version"]},
    )
    sign_in(c)
    assert (
        c.post(
            f"/api/reviews/{asked.json()['review']['id']}/decisions",
            json={"action": "approve", "reason": "", "comment": "", "version": asked.json()["review"]["version"]},
        ).status_code
        == 200
    )
    sign_in(c, "viewer@alpha.test")
    extra = c.post(
        f"/api/projects/{pid}/construction/progress",
        json=_report(area_id, me["company_id"], civil, uid, number="DPR-OPEN"),
    )
    extra_line = c.post(
        f"/api/projects/{pid}/construction/progress/{extra.json()['id']}/lines",
        json={"activity_id": activity.json()["id"], "quantity": "1", "rework": True, "evidence": "Still open"},
    )
    assert extra_line.status_code == 201, extra_line.text
    open_report = c.post(
        f"/api/projects/{pid}/construction/handover/{dossier.json()['id']}/submit",
        json={"version": dossier.json()["version"]},
    )
    assert open_report.status_code == 422, open_report.text
    assert "open daily report" in open_report.text
    cancelled = c.post(
        f"/api/projects/{pid}/construction/progress/{extra.json()['id']}/cancel",
        json={"reason": "Not part of handover", "version": extra_line.json()["version"]},
    )
    assert cancelled.status_code == 200, cancelled.text
    blocker = c.post(
        f"/api/projects/{pid}/construction/blockers",
        json={
            "package_id": package_id,
            "kind": "Delay",
            "description": "Access is still tight",
            "owner_user_id": uid,
            "recovery_note": "Clear the access",
        },
    )
    assert blocker.status_code == 201, blocker.text
    blocked = c.post(
        f"/api/projects/{pid}/construction/handover/{dossier.json()['id']}/submit",
        json={"version": dossier.json()["version"]},
    )
    assert blocked.status_code == 422, blocked.text
    assert "open blockers" in blocked.text
    assert (
        c.post(
            f"/api/projects/{pid}/construction/blockers/{blocker.json()['id']}/resolve",
            json={"resolution_note": "Access is clear", "version": blocker.json()["version"]},
        ).status_code
        == 200
    )
    sent = c.post(
        f"/api/projects/{pid}/construction/handover/{dossier.json()['id']}/submit",
        json={"version": dossier.json()["version"]},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "Pending Review"
    assert sent.json()["package_status"] == "Physically Complete"
    assert sent.json()["release_state"] == "Released"
    assert sent.json()["payload"]["activities"][0]["verified_quantity"] == "10.000"
    assert sent.json()["payload"]["activities"][0]["accepted_quantity"] is None
    assert sent.json()["payload"]["activities"][0]["certified_quantity"] is None
    assert sent.json()["payload"]["checks"][0]["check_type"] == "Workfront"
    assert "permit" in sent.json()["payload"]["checks"][0]["source_label"].casefold()
    own = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": sent.json()["review"]["version"]},
    )
    assert own.status_code == 403, own.text
    during = c.post(
        f"/api/projects/{pid}/construction/progress",
        json=_report(area_id, me["company_id"], civil, uid, number="DPR-LATE"),
    )
    late = c.post(
        f"/api/projects/{pid}/construction/progress/{during.json()['id']}/lines",
        json={"activity_id": activity.json()["id"], "quantity": "1", "rework": True, "evidence": "After submit"},
    )
    assert late.status_code == 422, late.text
    assert "in handover" in late.text
    sign_in(c)
    returned = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={"action": "return", "reason": "Confirm the pour record", "comment": "", "version": sent.json()["review"]["version"]},
    )
    assert returned.status_code == 200, returned.text
    sign_in(c, "viewer@alpha.test")
    back = next(row for row in c.get(f"/api/projects/{pid}/construction/handover").json()["dossiers"] if row["number"] == "HO-1")
    assert back["status"] == "Returned for Correction"
    assert back["package_status"] == "In Progress"
    again = c.post(
        f"/api/projects/{pid}/construction/handover/{back['id']}/resubmit",
        json={"version": back["version"]},
    )
    assert again.status_code == 200, again.text
    sign_in(c)
    approved = c.post(
        f"/api/reviews/{again.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": again.json()["review"]["version"]},
    )
    assert approved.status_code == 200, approved.text
    sign_in(c, "viewer@alpha.test")
    final = next(row for row in c.get(f"/api/projects/{pid}/construction/handover").json()["dossiers"] if row["number"] == "HO-1")
    assert final["status"] == "Approved"
    assert final["package_status"] == "Handed Over"
    assert final["release_state"] == "Released"
    assert final["package_status"] != "Accepted"
    duplicate = c.post(
        f"/api/projects/{pid}/construction/handover",
        json={"number": "HO-2", "package_id": package_id},
    )
    assert duplicate.status_code == 409, duplicate.text
    measured = next(
        row for row in c.get(f"/api/projects/{pid}/construction/progress").json()["activities"] if row["activity_code"] == "POUR"
    )
    assert measured["verified_quantity"] == "10.000"
    assert measured["rework_quantity"] == "1.000"
    assert measured["accepted_quantity"] is None
    assert measured["certified_quantity"] is None
    second = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(area_id, me["company_id"], civil, code="WP-TWO"),
    )
    second_activity = c.post(
        f"/api/projects/{pid}/construction/activities",
        json={
            "package_id": second.json()["id"],
            "code": "SLAB",
            "name": "Slab",
            "quantity": "1",
            "unit": "m3",
            "company_id": me["company_id"],
            "measurement_method": "Quantity",
            "predecessor_ids": [],
        },
    )
    assert second_activity.status_code == 201, second_activity.text
    with maker() as db:
        from app.domains.construction.models import WorkPackage

        row = db.get(WorkPackage, second.json()["id"])
        row.status = "In Progress"
        row.release_state = "Released"
        db.commit()
    small = c.post(
        f"/api/projects/{pid}/construction/progress",
        json=_report(area_id, me["company_id"], civil, uid, number="DPR-TWO"),
    )
    small_line = c.post(
        f"/api/projects/{pid}/construction/progress/{small.json()['id']}/lines",
        json={"activity_id": second_activity.json()["id"], "quantity": "1"},
    )
    small_sent = c.post(
        f"/api/projects/{pid}/construction/progress/{small.json()['id']}/submit",
        json={"version": small_line.json()["version"]},
    )
    sign_in(c)
    assert (
        c.post(
            f"/api/reviews/{small_sent.json()['review']['id']}/decisions",
            json={"action": "approve", "reason": "", "comment": "", "version": small_sent.json()["review"]["version"]},
        ).status_code
        == 200
    )
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_handover_policy(civil, uid)).status_code == 201
    other = c.post(
        f"/api/projects/{pid}/construction/handover",
        json={"number": "HO-3", "package_id": second.json()["id"]},
    )
    assert other.status_code == 201, other.text
    other_sent = c.post(
        f"/api/projects/{pid}/construction/handover/{other.json()['id']}/submit",
        json={"version": other.json()["version"]},
    )
    assert other_sent.status_code == 200, other_sent.text
    bypass = c.post(
        f"/api/reviews/{other_sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": other_sent.json()["review"]["version"]},
    )
    assert bypass.status_code == 403, bypass.text
    sign_in(c, "viewer@alpha.test")
    finished = c.post(
        f"/api/reviews/{other_sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": other_sent.json()["review"]["version"]},
    )
    assert finished.status_code == 200, finished.text
    closed = next(row for row in c.get(f"/api/projects/{pid}/construction/handover").json()["dossiers"] if row["number"] == "HO-3")
    assert closed["package_status"] == "Handed Over"
    for email in ("viewer@alpha.test", "admin@alpha.test"):
        sign_in(c, email)
        titles = [row["title"] for row in c.get("/api/notifications").json()]
        assert "Work handed over" in titles
    with maker() as db:
        from app.domains.construction.models import ReadinessCheck
        from app.domains.coordination.models import Job

        assert db.query(ReadinessCheck).count() == 1
        assert db.query(Job).filter(Job.kind.ilike("%mail%")).count() == 0


def test_material_readiness_reads_accepted_reserved_stock(env):
    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="CONST-MAT",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    area = c.post(f"/api/projects/{pid}/areas", json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""})
    assert area.status_code == 201, area.text
    assert (
        c.post(
            f"/api/projects/{pid}/memberships",
            json={
                "user_id": me["id"],
                "role_id": roles["Site Engineer"],
                "company_id": me["company_id"],
                "scope": "ALL",
                "discipline_ids": [],
            },
        ).status_code
        == 201
    )
    package = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(
            area.json()["id"],
            me["company_id"],
            civil,
            code="WP-MAT",
            responsible_user_id=me["id"],
            planned_start="2026-10-08",
            planned_finish="2026-10-20",
        ),
    )
    assert package.status_code == 201, package.text
    package_id = package.json()["id"]
    added = c.post(
        f"/api/projects/{pid}/construction/packages/{package_id}/checks",
        json={"check_type": "Material", "classification": "Mandatory"},
    )
    assert added.status_code == 201, added.text
    check = next(row for row in added.json()["checks"] if row["check_type"] == "Material")
    assert check["live_material"] == "pending"
    assert check["manual"] is False
    noted = c.put(
        f"/api/projects/{pid}/construction/packages/{package_id}/checks/{check['id']}",
        json={"status": "Satisfied", "evidence": "Material is on site", "version": check["version"]},
    )
    assert noted.status_code == 422, noted.text
    assert "Pending" in noted.text
    with maker() as db:
        from decimal import Decimal

        from app.domains.identity_projects.models import Project
        from app.domains.supply_chain.models import (
            MaterialRequirement,
            ProcurementItem,
            RequirementLine,
            StockBalance,
            Warehouse,
        )

        project = db.get(Project, pid)
        item = ProcurementItem(
            organization_id=project.organization_id,
            code="CEM-MAT",
            code_key="cem-mat",
            description="Cement",
            item_type="Material",
            category="Civil",
            discipline_ids=[],
            base_unit="bag",
            created_by=me["id"],
        )
        db.add(item)
        db.flush()
        requirement = MaterialRequirement(
            organization_id=project.organization_id,
            project_id=pid,
            number="MR-MAT",
            number_key="mr-mat",
            company_id=me["company_id"],
            discipline_id=civil,
            requested_by=me["id"],
            required_date=date(2026, 10, 8),
            purpose="Pile caps",
            created_by=me["id"],
        )
        db.add(requirement)
        db.flush()
        db.add(
            RequirementLine(
                requirement_id=requirement.id,
                position=1,
                item_id=item.id,
                quantity=Decimal("5.000"),
                unit="bag",
                required_date=date(2026, 10, 8),
            )
        )
        warehouse = Warehouse(
            organization_id=project.organization_id,
            project_id=pid,
            code="WH-MAT",
            code_key="wh-mat",
            name="Site store",
            officer_id=me["id"],
            created_by=me["id"],
        )
        db.add(warehouse)
        db.flush()
        balance = StockBalance(
            organization_id=project.organization_id,
            project_id=pid,
            warehouse_id=warehouse.id,
            item_id=item.id,
            unit="bag",
            on_hand=Decimal("5.000"),
            reserved=Decimal("0.000"),
        )
        db.add(balance)
        db.commit()
        requirement_id = requirement.id
        warehouse_id = warehouse.id
        item_id = item.id
    current = next(row for row in c.get(f"/api/projects/{pid}/construction/packages").json() if row["id"] == package_id)
    linked = c.put(
        f"/api/projects/{pid}/construction/packages/{package_id}",
        json=_editable(current, requirement_ids=[requirement_id]),
    )
    assert linked.status_code == 200, linked.text
    check = next(row for row in c.get(f"/api/projects/{pid}/construction/readiness").json() if row["package"]["id"] == package_id)
    material = next(row for row in check["checks"] if row["check_type"] == "Material")
    assert material["live_material"] == "blocked"
    short = c.put(
        f"/api/projects/{pid}/construction/packages/{package_id}/checks/{material['id']}",
        json={"status": "Satisfied", "evidence": "Reserved", "version": material["version"]},
    )
    assert short.status_code == 422, short.text
    assert "reserved" in short.text.casefold()

    def reserve(number, owner):
        with maker() as db:
            from decimal import Decimal

            from app.domains.identity_projects.models import Project
            from app.domains.supply_chain.models import StockBalance, StockPosting, StockPostingLine

            posting = StockPosting(
                organization_id=db.get(Project, pid).organization_id,
                project_id=pid,
                warehouse_id=warehouse_id,
                package_id=owner,
                number=number,
                number_key=number.casefold(),
                kind="Reservation",
                created_by=me["id"],
            )
            db.add(posting)
            db.flush()
            db.add(StockPostingLine(posting_id=posting.id, item_id=item_id, quantity=Decimal("5.000"), unit="bag"))
            row = db.query(StockBalance).filter_by(warehouse_id=warehouse_id, item_id=item_id).one()
            row.reserved = Decimal("5.000")
            db.commit()
            return posting.id

    def material_now():
        card = next(
            card for card in c.get(f"/api/projects/{pid}/construction/readiness").json() if card["package"]["id"] == package_id
        )
        return next(row for row in card["checks"] if row["check_type"] == "Material")

    project_level = reserve("RES-PROJECT", None)
    material = material_now()
    assert material["live_material"] == "blocked"
    assert "without a package is not counted" in material["source_label"]
    with maker() as db:
        from app.domains.supply_chain.models import StockPosting

        db.get(StockPosting, project_level).status = "Cancelled"
        db.commit()
    reservation_id = reserve("RES-PACKAGE", package_id)
    material = material_now()
    assert material["live_material"] == "ready"
    assert material["live_state"] == "Ready"
    satisfied = c.put(
        f"/api/projects/{pid}/construction/packages/{package_id}/checks/{material['id']}",
        json={"status": "Satisfied", "evidence": "", "version": material["version"]},
    )
    assert satisfied.status_code == 200, satisfied.text
    with maker() as db:
        from app.domains.construction.models import WorkPackage
        from app.domains.supply_chain.models import StockPosting

        db.get(StockPosting, reservation_id).status = "Cancelled"
        package_row = db.get(WorkPackage, package_id)
        package_row.status = "Ready"
        package_row.release_state = "Released"
        db.commit()
        version = package_row.version
    started = c.post(
        f"/api/projects/{pid}/construction/packages/{package_id}/start",
        json={"version": version},
    )
    assert started.status_code == 409, started.text
    assert "reserved" in started.text.casefold()
    stayed = next(row for row in c.get(f"/api/projects/{pid}/construction/packages").json() if row["id"] == package_id)
    assert stayed["status"] == "Ready"


def _site(c, maker, code):
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code=code,
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    area = c.post(f"/api/projects/{pid}/areas", json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""}).json()["id"]
    with maker() as db:
        from app.domains.identity_projects.models import User

        uid = db.query(User).filter_by(email="viewer@alpha.test").one().id
    for user_id, role in ((uid, "Site Engineer"), (me["id"], "Project Manager")):
        member = c.post(
            f"/api/projects/{pid}/memberships",
            json={"user_id": user_id, "role_id": roles[role], "company_id": me["company_id"], "scope": "ALL", "discipline_ids": []},
        )
        assert member.status_code == 201, member.text
    return me, civil, pid, area, uid


def test_superseded_drawing_opens_package_impact_review(env):
    c, maker = env
    me, civil, pid, area, uid = _site(c, maker, "CONST-IMPACT")
    with maker() as db:
        from app.domains.engineering_documents.models import Drawing, DrawingRevision, StoredFile
        from app.domains.identity_projects.models import Project

        org = db.get(Project, pid).organization_id
        stored = StoredFile(
            organization_id=org,
            sha256="b" * 64,
            size=4,
            content_type="text/plain",
            original_name="d.txt",
            storage_name="d-impact",
            created_by=me["id"],
        )
        db.add(stored)
        db.flush()
        drawing = Drawing(
            organization_id=org,
            project_id=pid,
            number="C-9",
            number_key="c-9",
            title="Foundation",
            discipline_id=civil,
            company_id=me["company_id"],
            created_by=me["id"],
        )
        db.add(drawing)
        db.flush()
        old = DrawingRevision(drawing_id=drawing.id, code="B", code_key="b", sequence=1, file_id=stored.id, release_state="Released", created_by=me["id"])
        new = DrawingRevision(drawing_id=drawing.id, code="C", code_key="c", sequence=2, file_id=stored.id, release_state="Not Released", created_by=me["id"])
        db.add_all([old, new])
        db.commit()
        old_id, new_id = old.id, new.id
    sign_in(c, "viewer@alpha.test")
    package = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(area, me["company_id"], civil, code="WP-IMP", responsible_user_id=uid, revision_ids=[old_id]),
    )
    assert package.status_code == 201, package.text
    package_id = package.json()["id"]
    activity = c.post(
        f"/api/projects/{pid}/construction/activities",
        json={"package_id": package_id, "code": "POUR", "name": "Pour", "quantity": "10", "unit": "m3", "company_id": me["company_id"], "measurement_method": "Quantity", "predecessor_ids": []},
    )
    assert activity.status_code == 201, activity.text
    activity_id = activity.json()["id"]
    with maker() as db:
        from app.domains.construction.models import WorkPackage
        from app.domains.engineering_documents.models import DrawingRevision
        from app.domains.engineering_documents.workflow import _construction_impact
        from app.domains.identity_projects.models import User

        row = db.get(WorkPackage, package_id)
        row.status = "In Progress"
        row.release_state = "Released"
        db.get(DrawingRevision, new_id).release_state = "Released"
        superseded = db.get(DrawingRevision, old_id)
        superseded.release_state = "Superseded"
        admin = db.query(User).filter_by(email="admin@alpha.test").one()
        _construction_impact(db, admin, superseded, "Drawing C-9 rev B was superseded by C")
        _construction_impact(db, admin, superseded, "Drawing C-9 rev B was superseded by C")
        db.commit()
    with maker() as db:
        from app.domains.coordination.models import Notification, Task

        tasks = db.query(Task).filter_by(project_id=pid, source_type="construction.drawing_impact", source_id=package_id).all()
        assert [task.owner_id for task in tasks] == [uid]
        assert db.query(Notification).filter_by(user_id=uid, title="Drawing impact on work package").count() == 1

    flagged = next(row for row in c.get(f"/api/projects/{pid}/construction/packages").json() if row["id"] == package_id)
    assert flagged["impact_state"] == "Review required"
    card = next(row for row in c.get(f"/api/projects/{pid}/construction/readiness").json() if row["package"]["id"] == package_id)
    assert card["impact_choices"] == [{"id": new_id, "code": "C"}]
    report = c.post(
        f"/api/projects/{pid}/construction/progress",
        json={"number": "DPR-IMP", "report_date": date.today().isoformat(), "shift": "Day", "discipline_id": civil, "area_id": area, "company_id": me["company_id"], "site_engineer_id": uid, "weather": "", "remarks": ""},
    )
    assert report.status_code == 201, report.text
    lines = f"/api/projects/{pid}/construction/progress/{report.json()['id']}/lines"
    closed = c.post(lines, json={"activity_id": activity_id, "quantity": "1"})
    assert closed.status_code == 422 and "drawing impact review is open" in closed.text

    url = f"/api/projects/{pid}/construction/packages/{package_id}/drawing-impact"
    sign_in(c)
    assert c.post(url, json={"version": flagged["version"], "action": "relink", "revision_id": new_id}).status_code == 403
    sign_in(c, "viewer@alpha.test")
    assert c.post(url, json={"version": flagged["version"], "action": "accept", "reason": "ok"}).status_code == 422
    assert c.post(url, json={"version": flagged["version"], "action": "relink", "revision_id": old_id}).status_code == 422
    relinked = c.post(url, json={"version": flagged["version"], "action": "relink", "revision_id": new_id, "reason": "Pour uses rev C"})
    assert relinked.status_code == 200, relinked.text
    body = relinked.json()["package"]
    assert body["impact_state"] == "Reviewed" and body["revision_ids"] == [new_id]
    with maker() as db:
        from app.domains.coordination.models import Task

        assert {task.status for task in db.query(Task).filter_by(source_type="construction.drawing_impact", source_id=package_id)} == {"Completed"}
    opened = c.post(lines, json={"activity_id": activity_id, "quantity": "1"})
    assert opened.status_code in (200, 201), opened.text


def test_package_reservation_issue_and_material_issue_check(env):
    c, maker = env
    me, civil, pid, area, uid = _site(c, maker, "CONST-ISSUE")
    with maker() as db:
        from decimal import Decimal

        from app.domains.identity_projects.models import Project
        from app.domains.supply_chain.models import MaterialRequirement, ProcurementItem, RequirementLine, StockBalance, Warehouse

        org = db.get(Project, pid).organization_id
        item = ProcurementItem(organization_id=org, code="CEM-ISS", code_key="cem-iss", description="Cement", item_type="Material", category="Civil", discipline_ids=[], base_unit="bag", created_by=me["id"])
        db.add(item)
        db.flush()
        requirement = MaterialRequirement(organization_id=org, project_id=pid, number="MR-ISS", number_key="mr-iss", company_id=me["company_id"], discipline_id=civil, requested_by=me["id"], required_date=date(2026, 10, 8), purpose="Pile caps", created_by=me["id"])
        db.add(requirement)
        db.flush()
        db.add(RequirementLine(requirement_id=requirement.id, position=1, item_id=item.id, quantity=Decimal("5.000"), unit="bag", required_date=date(2026, 10, 8)))
        warehouse = Warehouse(organization_id=org, project_id=pid, code="WH-ISS", code_key="wh-iss", name="Site store", officer_id=me["id"], created_by=me["id"])
        db.add(warehouse)
        db.flush()
        db.add(StockBalance(organization_id=org, project_id=pid, warehouse_id=warehouse.id, item_id=item.id, unit="bag", on_hand=Decimal("8.000"), reserved=Decimal("0.000")))
        db.commit()
        requirement_id, warehouse_id, item_id = requirement.id, warehouse.id, item.id
    package = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(area, me["company_id"], civil, code="WP-ISS", responsible_user_id=uid, requirement_ids=[requirement_id]),
    )
    assert package.status_code == 201, package.text
    package_id = package.json()["id"]
    added = c.post(
        f"/api/projects/{pid}/construction/packages/{package_id}/checks",
        json={"check_type": "Material issue", "classification": "Mandatory"},
    )
    assert added.status_code == 201, added.text

    def issue_check():
        card = next(row for row in c.get(f"/api/projects/{pid}/construction/readiness").json() if row["package"]["id"] == package_id)
        return next(row for row in card["checks"] if row["check_type"] == "Material issue")

    def balance():
        return next(row for row in c.get(f"/api/projects/{pid}/procurement/stock").json() if row["item_id"] == item_id)

    stock = f"/api/projects/{pid}/procurement/stock"
    reserved = c.post(
        f"{stock}/reservations",
        json={"number": "RSV-ISS", "warehouse_id": warehouse_id, "reason": "For WP-ISS", "package_id": package_id, "lines": [{"item_id": item_id, "quantity": "5"}]},
    )
    assert reserved.status_code == 201, reserved.text
    assert reserved.json()["package_code"] == "WP-ISS"
    check = issue_check()
    assert check["live_state"] == "Blocked" and "issued before start" in check["live_reason"]

    def issue(number, quantity, **extra):
        return c.post(
            f"{stock}/issues",
            json={"number": number, "warehouse_id": warehouse_id, "reason": "Install", "recipient": "Crew", "lines": [{"item_id": item_id, "quantity": quantity}], **extra},
        )

    assert issue("ISS-OVER", "6", reservation_id=reserved.json()["id"]).status_code == 422
    assert issue("ISS-PKG", "1", package_id=package_id).status_code == 422
    first = issue("ISS-1", "3", reservation_id=reserved.json()["id"])
    assert first.status_code == 201, first.text
    assert first.json()["package_code"] == "WP-ISS"
    assert (balance()["on_hand"], balance()["reserved"]) == ("5.000", "2.000")
    refused = c.post(f"{stock}/postings/{reserved.json()['id']}/cancel", json={"reason": "No longer needed", "version": reserved.json()["version"]})
    assert refused.status_code == 409, refused.text
    second = issue("ISS-2", "2", reservation_id=reserved.json()["id"])
    assert second.status_code == 201, second.text
    assert issue_check()["live_state"] == "Ready"
    assert (balance()["on_hand"], balance()["reserved"]) == ("3.000", "0.000")
    undone = c.post(f"{stock}/postings/{second.json()['id']}/cancel", json={"reason": "Wrong crew", "version": second.json()["version"]})
    assert undone.status_code == 200, undone.text
    assert (balance()["on_hand"], balance()["reserved"]) == ("5.000", "2.000")
    assert issue_check()["live_state"] == "Blocked"

