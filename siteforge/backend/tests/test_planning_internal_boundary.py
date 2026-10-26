"""Focused internal/partner authorization separation regression tests."""
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.domains.planning_reporting.workspace_router import access
from app.domains.identity_projects.models import Project, Role, Membership

class Query:
    def __init__(self, memberships): self.memberships = memberships
    def filter_by(self, **kwargs): return self
    def all(self): return self.memberships

class DB:
    def __init__(self, memberships, roles):
        self.memberships = memberships
        self.roles = roles
    def get(self, model, identifier):
        if model is Project: return SimpleNamespace(id=identifier, organization_id=1)
        if model is Role: return self.roles.get(identifier)
        return None
    def query(self, model):
        assert model is Membership
        return Query(self.memberships)

def m(role_id): return SimpleNamespace(role_id=role_id)
def user(admin=False, active=True):
    return SimpleNamespace(organization_id=1, id=55, organization_admin=admin, active=active)
def role(*permissions): return SimpleNamespace(permissions=list(permissions))

def test_partner_only_cannot_read_internal():
    db = DB([m(1)], {1: role('planning.partner.view')})
    with pytest.raises(HTTPException) as exc: access(db, user(), 8)
    assert exc.value.status_code == 403

def test_misconfigured_partner_role_cannot_access_internal():
    db = DB([m(1)], {1: role('planning.partner.view','planning.view','planning.manage')})
    with pytest.raises(HTTPException): access(db, user(), 8, True)

def test_separate_internal_role_allows_read_but_not_write():
    db = DB([m(1),m(2)], {1: role('planning.partner.view'),2: role('planning.view')})
    assert access(db, user(), 8).id == 8
    with pytest.raises(HTTPException): access(db, user(), 8, True)

def test_internal_manager_can_write():
    db = DB([m(2)], {2: role('planning.manage')})
    assert access(db, user(), 8, True).id == 8

def test_inactive_admin_rejected():
    with pytest.raises(HTTPException): access(DB([], {}), user(admin=True, active=False), 8)
