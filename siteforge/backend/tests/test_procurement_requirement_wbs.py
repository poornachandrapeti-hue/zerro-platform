from .test_construction import _package
from .test_engineering import sign_in
from .test_foundation import new_project


def _setup(c, maker):
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="REQ-WBS",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    membership = c.post(
        f"/api/projects/{pid}/memberships",
        json={"user_id": me["id"], "role_id": roles["Site Engineer"], "company_id": me["company_id"], "scope": "ALL", "discipline_ids": []},
    )
    assert membership.status_code == 201, membership.text
    area = c.post(f"/api/projects/{pid}/areas", json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""})
    assert area.status_code == 201, area.text
    item = c.post(
        "/api/procurement/items",
        json={"code": "CEM-WBS", "description": "Cement", "item_type": "Material", "category": "Civil", "discipline_ids": [civil], "base_unit": "kg"},
    )
    assert item.status_code == 201, item.text
    draft = c.post(f"/api/projects/{pid}/construction/packages", json=_package(area.json()["id"], me["company_id"], civil, code="WP-D"))
    released = c.post(f"/api/projects/{pid}/construction/packages", json=_package(area.json()["id"], me["company_id"], civil, code="WP-R"))
    assert draft.status_code == 201 and released.status_code == 201
    with maker() as db:
        from app.domains.construction.models import WorkPackage
        from app.domains.planning_reporting.workspace_models import PlanningWBS
        from app.domains.identity_projects.models import Project

        org = db.get(Project, pid).organization_id
        wbs = PlanningWBS(organization_id=org, project_id=pid, code="1.1", name="Foundation")
        retired = PlanningWBS(organization_id=org, project_id=pid, code="9.9", name="Retired", active=False)
        db.add_all([wbs, retired])
        row = db.get(WorkPackage, released.json()["id"])
        row.status = "Ready"
        row.release_state = "Released"
        db.commit()
        ids = wbs.id, retired.id
    return pid, me, civil, item.json()["id"], ids, draft.json()["id"], released.json()["id"]


def _body(me, civil, item_id, wbs_id=None, **extra):
    line = {"item_id": item_id, "quantity": "1000", "unit": "kg", "required_date": "2026-12-01", "tag": ""}
    if wbs_id is not None:
        line["planning_wbs_id"] = wbs_id
    body = {
        "number": "MR-WBS",
        "company_id": me["company_id"],
        "discipline_id": civil,
        "requested_by": me["id"],
        "required_date": "2026-12-01",
        "purpose": "Foundation concrete",
        "lines": [line],
    }
    body.update(extra)
    return body


def test_requirement_line_carries_wbs_and_links_draft_work_package(env):
    c, maker = env
    pid, me, civil, item_id, (wbs_id, retired_id), draft_id, released_id = _setup(c, maker)
    base = f"/api/projects/{pid}/procurement/requirements"

    context = c.get(f"/api/projects/{pid}/procurement/context").json()
    assert [row["code"] for row in context["wbs"]] == ["1.1"]
    assert {row["id"]: row["editable"] for row in context["work_packages"]} == {draft_id: True, released_id: False}

    assert c.post(base, json=_body(me, civil, item_id, retired_id)).status_code == 422
    assert c.post(base, json=_body(me, civil, item_id, wbs_id, work_package_ids=[released_id])).status_code == 409

    saved = c.post(base, json=_body(me, civil, item_id, wbs_id, work_package_ids=[draft_id]))
    assert saved.status_code == 201, saved.text
    row = saved.json()
    assert row["lines"][0]["planning_wbs_id"] == wbs_id
    assert row["lines"][0]["wbs_code"] == "1.1"
    assert [wp["code"] for wp in row["work_packages"]] == ["WP-D"]
    package = next(p for p in c.get(f"/api/projects/{pid}/construction/packages").json() if p["id"] == draft_id)
    assert package["requirement_ids"] == [row["id"]]

    line = {k: row["lines"][0][k] for k in ("id", "item_id", "quantity", "unit", "required_date", "tag")}
    kept = c.put(f"{base}/{row['id']}", json={**_body(me, civil, item_id), "lines": [line], "version": row["version"]})
    assert kept.status_code == 200, kept.text
    assert kept.json()["lines"][0]["planning_wbs_id"] == wbs_id
    assert [wp["code"] for wp in kept.json()["work_packages"]] == ["WP-D"]

    cleared = c.put(
        f"{base}/{row['id']}",
        json={**_body(me, civil, item_id), "lines": [{**line, "planning_wbs_id": None}], "work_package_ids": [], "version": kept.json()["version"]},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["lines"][0]["planning_wbs_id"] is None
    assert cleared.json()["work_packages"] == []
