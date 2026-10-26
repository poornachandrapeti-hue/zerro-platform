from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
import pytest
from .conftest import sign_in
from app.domains.identity_projects.models import (
    User,
    Company,
    Project,
    Membership,
    LoginSession,
    Role,
)
from app.domains.identity_projects.security import permitted


def new_project(c, **extra):
    return c.post(
        "/api/projects", json={"code": "ALPHA-001", "name": "Industrial Plant", **extra}
    )


def test_two_tabs_keep_separate_sessions(env):
    from fastapi.testclient import TestClient
    from app.main import app

    first, _maker = env
    first.headers["X-Tab-Id"] = "tab-one-aaaaaaaa"
    sign_in(first)
    assert first.get("/api/auth/me").json()["user"]["email"] == "admin@alpha.test"
    second = TestClient(app)
    second.headers["Origin"] = "http://localhost:5173"
    second.headers["X-Tab-Id"] = "tab-two-bbbbbbbb"
    other = second.post(
        "/api/auth/login",
        json={"email": "viewer@alpha.test", "password": "test-password-123"},
    )
    assert other.status_code == 200, other.text
    second.headers["X-CSRF-Token"] = other.json()["csrf_token"]
    assert second.get("/api/auth/me").json()["user"]["email"] == "viewer@alpha.test"
    assert first.get("/api/auth/me").json()["user"]["email"] == "admin@alpha.test"
    stolen = second.headers["X-CSRF-Token"]
    second.headers["X-CSRF-Token"] = first.headers["X-CSRF-Token"]
    assert second.post("/api/auth/logout").status_code == 403
    second.headers["X-CSRF-Token"] = stolen
    assert second.post("/api/auth/logout").status_code == 200
    assert first.get("/api/auth/me").status_code == 200


def test_login_logout_and_cookie(env):
    c, _ = env
    c.headers["Origin"] = "http://localhost:5173"
    assert (
        c.post(
            "/api/auth/login", json={"email": "admin@alpha.test", "password": "wrong"}
        ).status_code
        == 401
    )
    r = sign_in(c)
    assert (
        "HttpOnly" in r.headers["set-cookie"]
        and "SameSite=lax" in r.headers["set-cookie"]
    )
    old = c.cookies.get("siteforge_session")
    assert c.get("/api/auth/me").status_code == 200
    assert c.post("/api/auth/logout").status_code == 200
    c.cookies.set("siteforge_session", old)
    assert c.get("/api/auth/me").status_code == 401


def test_csrf_and_origin(env):
    c, _ = env
    sign_in(c)
    c.headers.pop("X-CSRF-Token")
    assert new_project(c).status_code == 403
    sign_in(c)
    c.headers["Origin"] = "https://evil.example"
    assert new_project(c).status_code == 403
    assert (
        c.post(
            "/api/auth/login",
            json={"email": "admin@alpha.test", "password": "test-password-123"},
        ).status_code
        == 403
    )


def test_inactive_and_expired_sessions(env):
    c, maker = env
    sign_in(c)
    with maker() as db:
        s = db.query(LoginSession).first()
        s.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert c.get("/api/auth/me").status_code == 401
    sign_in(c)
    with maker() as db:
        u = db.query(User).filter_by(email="admin@alpha.test").one()
        u.active = False
        db.commit()
    assert c.get("/api/auth/me").status_code == 401
    assert (
        c.post(
            "/api/auth/login",
            json={"email": "admin@alpha.test", "password": "test-password-123"},
        ).status_code
        == 401
    )


def test_admin_access_and_mass_assignment(env):
    c, _ = env
    sign_in(c, "viewer@alpha.test")
    for endpoint in ["/api/users", "/api/companies", "/api/audit"]:
        assert c.get(endpoint).status_code == 403
    assert new_project(c).status_code == 403
    assert c.get("/api/projects").json()["total"] == 0
    sign_in(c)
    assert (
        c.post(
            "/api/projects", json={"code": "P", "name": "P", "organization_id": 2}
        ).status_code
        == 422
    )


def test_project_duplicates_and_activation(env):
    c, _ = env
    sign_in(c)
    r = new_project(c)
    assert r.status_code == 201, r.text
    assert new_project(c, code=" alpha-001 ").status_code == 409
    assert new_project(c, code="B", status="Planned").status_code == 422
    assert (
        new_project(
            c, code="B", planned_start="2026-10-10", planned_finish="2026-10-01"
        ).status_code
        == 422
    )
    assert new_project(c, code="B", timezone="Invalid/Zone").status_code == 422
    assert new_project(c, code="B", actual_finish="2026-01-01").status_code == 422


def test_cross_organization_and_unassigned(env):
    c, maker = env
    sign_in(c)
    pid = new_project(c).json()["id"]
    sign_in(c, "viewer@alpha.test")
    assert c.get(f"/api/projects/{pid}").status_code == 403
    sign_in(c, "admin@beta.test")
    assert c.get(f"/api/projects/{pid}").status_code == 404
    with maker() as db:
        foreign_company = db.query(Company).filter_by(name="Alpha Co").one().id
    assert new_project(c, client_company_id=foreign_company).status_code == 422


def test_last_admin(env):
    c, _ = env
    sign_in(c)
    uid = c.get("/api/auth/me").json()["user"]["id"]
    assert (
        c.put(
            f"/api/users/{uid}",
            json={"name": "Admin", "active": False, "organization_admin": True},
        ).status_code
        == 409
    )
    assert (
        c.put(
            f"/api/users/{uid}",
            json={"name": "Admin", "active": True, "organization_admin": False},
        ).status_code
        == 409
    )


def test_project_version_conflict(env):
    c, _ = env
    sign_in(c)
    p = new_project(c).json()
    pid = p.pop("id")
    for k in ["created_by", "created_at", "modified_at", "modified_by", "client_name", "lead_pm_name"]:
        p.pop(k, None)
    p["name"] = "Updated"
    assert c.put(f"/api/projects/{pid}", json=p).status_code == 200
    assert c.put(f"/api/projects/{pid}", json=p).status_code == 409


def test_memberships_scope_and_pm_limits(env):
    c, maker = env
    sign_in(c)
    cat = c.get("/api/catalog").json()
    civil = next(d["id"] for d in cat["disciplines"] if d["name"] == "Civil")
    electrical = next(d["id"] for d in cat["disciplines"] if d["name"] == "Electrical")
    pmrole = next(r["id"] for r in cat["roles"] if r["name"] == "Project Manager")
    with maker() as db:
        v = db.query(User).filter_by(email="viewer@alpha.test").one()
        uid = v.id
        company = v.company_id
    p = new_project(c, discipline_ids=[civil, electrical]).json()
    pid = p["id"]
    assert (
        c.post(
            f"/api/projects/{pid}/companies",
            json={"company_id": company, "participation_type": "Contractor"},
        ).status_code
        == 201
    )
    payload = {
        "user_id": uid,
        "role_id": pmrole,
        "company_id": company,
        "scope": "SELECTED",
        "discipline_ids": [],
    }
    assert c.post(f"/api/projects/{pid}/memberships", json=payload).status_code == 422
    payload["discipline_ids"] = [civil]
    assert c.post(f"/api/projects/{pid}/memberships", json=payload).status_code == 201
    with maker() as db:
        u = db.get(User, uid)
        project = db.get(Project, pid)
        permitted(db, u, project, "projects.edit", civil)
        with pytest.raises(HTTPException):
            permitted(db, u, project, "projects.edit", electrical)
    sign_in(c, "viewer@alpha.test")
    assert c.get("/api/projects").json()["total"] == 1
    assert c.get(f"/api/projects/{pid}").status_code == 200
    assert c.post(f"/api/projects/{pid}/memberships", json=payload).status_code == 403
    for k in ["id", "created_by", "created_at", "modified_at", "modified_by", "client_name", "lead_pm_name"]:
        p.pop(k, None)
    p["status"] = "Cancelled"
    p["cancellation_reason"] = "test"
    assert c.put(f"/api/projects/{pid}", json=p).status_code == 403


def test_active_project_auto_pm_and_deactivation_guard(env):
    c, maker = env
    sign_in(c)
    with maker() as db:
        u = db.query(User).filter_by(email="viewer@alpha.test").one()
        uid = u.id
        cid = u.company_id
    d = c.get("/api/catalog").json()["disciplines"][0]["id"]
    r = new_project(
        c,
        status="Active",
        client_company_id=cid,
        lead_pm_id=uid,
        discipline_ids=[d],
        site_name="Site",
        state="AP",
        city="Vizag",
        planned_start="2026-01-01",
        planned_finish="2027-01-01",
        actual_start="2026-01-02",
    )
    assert r.status_code == 201, r.text
    members = c.get(f"/api/projects/{r.json()['id']}/memberships").json()
    assert any(m["user_id"] == uid and m["role"] == "Project Manager" for m in members)
    assert (
        c.put(
            f"/api/users/{uid}",
            json={"name": "PM", "active": False, "organization_admin": False},
        ).status_code
        == 409
    )


def test_area_parent_cross_project(env):
    c, _ = env
    sign_in(c)
    p1 = new_project(c).json()["id"]
    p2 = new_project(c, code="B").json()["id"]
    a = c.post(
        f"/api/projects/{p1}/areas",
        json={"code": "U1", "name": "Unit", "area_type": "Unit"},
    )
    assert a.status_code == 201
    assert (
        c.post(
            f"/api/projects/{p2}/areas",
            json={
                "code": "A1",
                "name": "Area",
                "area_type": "Area",
                "parent_id": a.json()["id"],
            },
        ).status_code
        == 422
    )
    assert (
        c.post(
            f"/api/projects/{p1}/areas",
            json={
                "code": "B1",
                "name": "Block",
                "area_type": "Block",
                "parent_id": a.json()["id"],
            },
        ).status_code
        == 422
    )


def test_rate_limit(env):
    c, _ = env
    c.headers["Origin"] = "http://localhost:5173"
    for _ in range(10):
        assert (
            c.post(
                "/api/auth/login",
                json={"email": "none@example.test", "password": "wrong"},
            ).status_code
            == 401
        )
    assert (
        c.post(
            "/api/auth/login", json={"email": "none@example.test", "password": "wrong"}
        ).status_code
        == 429
    )


def test_audit_no_secrets(env):
    c, _ = env
    sign_in(c)
    new_project(c)
    r = c.get("/api/audit")
    assert r.status_code == 200
    assert "test-password-123" not in r.text and "password_hash" not in r.text
    assert any(
        x["action"] == "create" and x["resource"] == "projects"
        for x in r.json()["items"]
    )


def test_password_whitespace_is_significant(env):
    c, maker = env
    from app.domains.identity_projects.security import hasher

    with maker() as db:
        user = db.query(User).filter_by(email="admin@alpha.test").one()
        user.password_hash = hasher.hash("  padded-password-123  ")
        db.commit()
    c.headers["Origin"] = "http://localhost:5173"
    assert (
        c.post(
            "/api/auth/login",
            json={"email": "admin@alpha.test", "password": "padded-password-123"},
        ).status_code
        == 401
    )
    assert (
        c.post(
            "/api/auth/login",
            json={"email": "admin@alpha.test", "password": "  padded-password-123  "},
        ).status_code
        == 200
    )
