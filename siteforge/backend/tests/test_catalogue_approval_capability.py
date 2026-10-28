"""UI capability endpoint must reflect server-side decision authorization."""
from types import SimpleNamespace
from fastapi import HTTPException
from app.domains.supply_chain import router as catalogue_router


def test_approval_capability_allows_an_authorized_user(monkeypatch):
    monkeypatch.setattr(catalogue_router, "_catalogue_approve_role", lambda db, u: None)
    assert catalogue_router.catalogue_approval_capability(SimpleNamespace(), object()) == {"can_approve": True}


def test_approval_capability_hides_unauthorized_user(monkeypatch):
    def forbidden(db, u):
        raise HTTPException(403, "Not allowed")
    monkeypatch.setattr(catalogue_router, "_catalogue_approve_role", forbidden)
    assert catalogue_router.catalogue_approval_capability(SimpleNamespace(), object()) == {"can_approve": False}


def test_approval_capability_propagates_server_failure(monkeypatch):
    def missing(db, u):
        raise HTTPException(404, "Missing")
    monkeypatch.setattr(catalogue_router, "_catalogue_approve_role", missing)
    try:
        catalogue_router.catalogue_approval_capability(SimpleNamespace(), object())
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected HTTPException")
