from .conftest import sign_in
from .test_foundation import new_project


def _body(project):
    hidden = {
        "id",
        "created_by",
        "created_at",
        "modified_at",
        "modified_by",
        "client_name",
        "lead_pm_name",
    }
    return {key: value for key, value in project.items() if key not in hidden}


def test_draft_duplicate_code_and_postal(env):
    c, _ = env
    sign_in(c)
    draft = new_project(c, code="gap-1")
    assert draft.status_code == 201, draft.text
    assert draft.json()["status"] == "Draft"
    again = new_project(c, code="GAP-1")
    assert again.status_code == 409
    assert "already exists" in again.json()["detail"]
    bad = new_project(c, code="PIN-1", country="India", postal_code="12")
    assert bad.status_code == 422
    assert "Postal code" in bad.json()["detail"]


def test_commercial_is_hidden_and_preserved(env):
    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    created = new_project(
        c,
        code="COM-1",
        client_company_id=me["company_id"],
        contract_number="PO-9",
        contract_value="1500.50",
        currency="INR",
        main_contractor_company_id=None,
    )
    assert created.status_code == 201, created.text
    project = created.json()
    assert project["contract_number"] == "PO-9"
    assert project["contract_value"] == "1500.50"
    pid = project["id"]
    companies = c.get(f"/api/projects/{pid}/companies").json()
    assert any(row["participation_type"] == "Owner" for row in companies)
    with maker() as db:
        from app.domains.identity_projects.models import User

        viewer = db.query(User).filter_by(email="viewer@alpha.test").one()
        uid = viewer.id
        company = viewer.company_id
    role = next(row["id"] for row in c.get("/api/catalog").json()["roles"] if row["name"] == "Project Manager")
    if not any(row["company_id"] == company for row in companies):
        assert (
            c.post(
                f"/api/projects/{pid}/companies",
                json={"company_id": company, "participation_type": "Contractor"},
            ).status_code
            == 201
        )
    assert (
        c.post(
            f"/api/projects/{pid}/memberships",
            json={
                "user_id": uid,
                "role_id": role,
                "company_id": company,
                "scope": "ALL",
                "discipline_ids": [],
            },
        ).status_code
        == 201
    )
    sign_in(c, "viewer@alpha.test")
    visible = c.get(f"/api/projects/{pid}").json()
    assert "contract_value" not in visible
    assert "contract_number" not in visible
    body = _body(visible)
    body["description"] = "PM note"
    saved = c.put(f"/api/projects/{pid}", json=body)
    assert saved.status_code == 200, saved.text
    assert "contract_value" not in saved.json()
    sign_in(c)
    assert c.get(f"/api/projects/{pid}").json()["contract_value"] == "1500.50"
    assert c.get(f"/api/projects/{pid}").json()["description"] == "PM note"


def test_discipline_scope_and_contractor(env):
    c, _ = env
    sign_in(c)
    civil = next(row["id"] for row in c.get("/api/catalog").json()["disciplines"] if row["name"] == "Civil")
    me = c.get("/api/auth/me").json()["user"]
    other = c.post("/api/companies", json={"name": "Main Build", "company_type": "Main Contractor"}).json()
    created = new_project(
        c,
        code="SCOPE-1",
        client_company_id=me["company_id"],
        main_contractor_company_id=other["id"],
        disciplines=[{"discipline_id": civil, "scope_description": "Foundations", "active": True}],
        discipline_ids=[civil],
    )
    assert created.status_code == 201, created.text
    project = c.get(f"/api/projects/{created.json()['id']}").json()
    assert project["disciplines"][0]["scope_description"] == "Foundations"
    kinds = {
        row["participation_type"]
        for row in c.get(f"/api/projects/{project['id']}/companies").json()
        if row["active"]
    }
    assert "Main Contractor" in kinds
    assert "Owner" in kinds


def test_contract_file_requires_commercial_access(env):
    c, maker = env
    sign_in(c)
    project = new_project(c, code="FILE-1").json()
    pid = project["id"]
    uploaded = c.post(
        f"/api/projects/{pid}/files",
        data={"category": "Contract/PO", "title": "Purchase order"},
        files={"upload": ("po.txt", b"order", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    fid = uploaded.json()["id"]
    with maker() as db:
        from app.domains.identity_projects.models import User

        viewer = db.query(User).filter_by(email="viewer@alpha.test").one()
        uid = viewer.id
        company = viewer.company_id
    role = next(row["id"] for row in c.get("/api/catalog").json()["roles"] if row["name"] == "Project Manager")
    c.post(
        f"/api/projects/{pid}/companies",
        json={"company_id": company, "participation_type": "Contractor"},
    )
    c.post(
        f"/api/projects/{pid}/memberships",
        json={
            "user_id": uid,
            "role_id": role,
            "company_id": company,
            "scope": "ALL",
            "discipline_ids": [],
        },
    )
    sign_in(c, "viewer@alpha.test")
    listed = c.get(f"/api/projects/{pid}/files").json()
    assert listed == []
    assert c.get(f"/api/projects/{pid}/files/{fid}").status_code == 403
    ordinary = c.post(
        f"/api/projects/{pid}/files",
        data={"category": "Site Layout", "title": "Layout"},
        files={"upload": ("layout.txt", b"site", "text/plain")},
    )
    assert ordinary.status_code == 201, ordinary.text


def test_adding_disciplines_does_not_remove_assigned_companies(env):
    c, _ = env
    sign_in(c)
    civil = next(row["id"] for row in c.get("/api/catalog").json()["disciplines"] if row["name"] == "Civil")
    me = c.get("/api/auth/me").json()["user"]
    created = new_project(c, code="DISC-KEEP")
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    assert (
        c.post(
            f"/api/projects/{pid}/companies",
            json={"company_id": me["company_id"], "participation_type": "Owner"},
        ).status_code
        == 201
    )
    role = next(row["id"] for row in c.get("/api/catalog").json()["roles"] if row["name"] == "Project Manager")
    assert (
        c.post(
            f"/api/projects/{pid}/memberships",
            json={
                "user_id": me["id"],
                "role_id": role,
                "company_id": me["company_id"],
                "scope": "ALL",
                "discipline_ids": [],
            },
        ).status_code
        == 201
    )
    body = _body(c.get(f"/api/projects/{pid}").json())
    body["discipline_ids"] = [civil]
    body["disciplines"] = [{"discipline_id": civil, "scope_description": "Structures", "active": True}]
    saved = c.put(f"/api/projects/{pid}", json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["discipline_ids"] == [civil]
    owners = [
        row["company_id"]
        for row in c.get(f"/api/projects/{pid}/companies").json()
        if row["active"] and row["participation_type"] == "Owner"
    ]
    assert me["company_id"] in owners
    body = _body(saved.json())
    body["client_company_id"] = me["company_id"]
    named = c.put(f"/api/projects/{pid}", json=body)
    assert named.status_code == 200, named.text
    body = _body(named.json())
    body["client_company_id"] = None
    blocked = c.put(f"/api/projects/{pid}", json=body)
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "Deactivate assignments before removing this company"


def test_contacts_are_not_approvers(env):
    from .test_engineering import sign_in as open_session

    c, maker = env
    open_session(c)
    me = c.get("/api/auth/me").json()["user"]
    created = new_project(c, code="CONTACT-1", client_company_id=me["company_id"])
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    with maker() as db:
        from app.domains.identity_projects.models import User

        person = db.query(User).filter_by(email="viewer@alpha.test").one()
        uid, company = person.id, person.company_id
    open_session(c, "viewer@alpha.test")
    assert c.get(f"/api/projects/{pid}/contacts").status_code == 403
    open_session(c)
    roles = {row["name"]: row["id"] for row in c.get("/api/catalog").json()["roles"]}
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
    members = c.get(f"/api/projects/{pid}/memberships").json()
    saved = c.post(
        f"/api/projects/{pid}/contacts",
        json={
            "name": "Site office",
            "function": "Site",
            "company_id": company,
            "phone": "9876543210",
            "email": "site.office@example.com",
            "note": "Gate",
        },
    )
    assert saved.status_code == 201, saved.text
    contact = saved.json()
    assert contact["approver"] is False
    assert contact["phone"] == "9876543210"
    assert contact["details_visible"] is True
    assert len(c.get(f"/api/projects/{pid}/memberships").json()) == len(members)
    assert c.get(
        f"/api/projects/{pid}/approval-policies?record_type=project.activation"
    ).json() == []
    assert c.post(
        f"/api/projects/{pid}/contacts",
        json={"name": "Bad", "function": "Site", "phone": "call-me"},
    ).status_code == 422
    other = new_project(c, code="CONTACT-2").json()["id"]
    missing = dict(saved.json())
    missing.pop("id")
    missing.pop("company_name")
    missing.pop("user_name")
    missing.pop("details_visible")
    missing.pop("approver")
    assert c.put(f"/api/projects/{other}/contacts/{contact['id']}", json=missing).status_code == 404
    open_session(c, "viewer@alpha.test")
    hidden = c.get(f"/api/projects/{pid}/contacts").json()[0]
    assert hidden["name"] == "Site office"
    assert hidden["phone"] is None
    assert hidden["email"] is None
    assert hidden["details_visible"] is False
    assert hidden["approver"] is False
    assert c.post(
        f"/api/projects/{pid}/contacts",
        json={"name": "Extra", "function": "Other"},
    ).status_code == 403
    open_session(c)
    assert (
        c.post(
            f"/api/projects/{pid}/memberships",
            json={
                "user_id": uid,
                "role_id": roles["Project Manager"],
                "company_id": company,
                "scope": "ALL",
                "discipline_ids": [],
            },
        ).status_code
        == 201
    )
    open_session(c, "viewer@alpha.test")
    visible = c.get(f"/api/projects/{pid}/contacts").json()[0]
    assert visible["phone"] == "9876543210"
    edited = dict(missing)
    edited["note"] = "Gate 2"
    edited["version"] = visible["version"]
    changed = c.put(f"/api/projects/{pid}/contacts/{contact['id']}", json=edited)
    assert changed.status_code == 200, changed.text
    assert changed.json()["note"] == "Gate 2"
    assert changed.json()["approver"] is False
    stale = dict(edited)
    assert c.put(f"/api/projects/{pid}/contacts/{contact['id']}", json=stale).status_code == 409
    open_session(c)
    assert (
        c.post(
            f"/api/projects/{pid}/approval-policies",
            json={
                "record_type": "project.activation",
                "allow_self_approval": False,
                "stages": [{"name": "Check", "rule": "all", "reviewer_ids": [uid]}],
            },
        ).status_code
        == 201
    )
    linked = dict(changed.json())
    for key in ("id", "company_name", "user_name", "details_visible", "approver"):
        linked.pop(key)
    linked["user_id"] = uid
    marked = c.put(f"/api/projects/{pid}/contacts/{contact['id']}", json=linked)
    assert marked.status_code == 200, marked.text
    assert marked.json()["approver"] is True
    listed = c.get(
        f"/api/projects/{pid}/approval-policies?record_type=project.activation"
    ).json()
    reviewers = [
        person["id"] for stage in listed[0]["stages"] for person in stage["reviewers"]
    ]
    assert reviewers == [uid]
    assert len(c.get(f"/api/projects/{pid}/memberships").json()) == len(members) + 1
    retired = dict(linked)
    retired["active"] = False
    retired["version"] = marked.json()["version"]
    closed = c.put(f"/api/projects/{pid}/contacts/{contact['id']}", json=retired)
    assert closed.status_code == 200, closed.text
    assert closed.json()["active"] is False
    assert c.get(f"/api/projects/{pid}/contacts").json()[0]["active"] is False
    assert (
        c.post(
            f"/api/projects/{pid}/contacts",
            json={"name": "Outside", "function": "Client", "company_id": 999999},
        ).status_code
        == 422
    )
