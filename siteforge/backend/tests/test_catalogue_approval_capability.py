"""UI capability endpoint must reflect server-side decision authorization."""
from types import SimpleNamespace
from fastapi import HTTPException
from app.domains.supply_chain import router as catalogue_router


def _defaults():
    return {
        "submitted_status": "Under Review",
        "stages": ["Draft", "Submitted", "Under Review", "Approved", "Rejected"],
        "approve_permission": "procurement.catalogue.approve",
        "decision_reason_min_length": 3,
        "enforce_separation_of_duties": True,
    }


def test_approval_capability_allows_an_authorized_user(monkeypatch):
    monkeypatch.setattr(catalogue_router, "_catalogue_approve_role", lambda db, u: None)
    monkeypatch.setattr(catalogue_router, "_catalogue_config", lambda db, u: _defaults())
    assert catalogue_router.catalogue_approval_capability(SimpleNamespace(organization_id=1), object()) == {
        "can_approve": True,
        **_defaults(),
    }


def test_approval_capability_hides_unauthorized_user(monkeypatch):
    def forbidden(db, u):
        raise HTTPException(403, "Not allowed")
    monkeypatch.setattr(catalogue_router, "_catalogue_approve_role", forbidden)
    monkeypatch.setattr(catalogue_router, "_catalogue_config", lambda db, u: _defaults())
    assert catalogue_router.catalogue_approval_capability(SimpleNamespace(organization_id=1), object()) == {
        "can_approve": False,
        **_defaults(),
    }


def test_approval_capability_propagates_server_failure(monkeypatch):
    def missing(db, u):
        raise HTTPException(404, "Missing")
    monkeypatch.setattr(catalogue_router, "_catalogue_approve_role", missing)
    monkeypatch.setattr(catalogue_router, "_catalogue_config", lambda db, u: _defaults())
    try:
        catalogue_router.catalogue_approval_capability(SimpleNamespace(organization_id=1), object())
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected HTTPException")
