from fastapi import HTTPException
import pytest
from app.domains.supply_chain.catalogue_approval_config import (
    can_approve_with_config,
    pending_statuses,
    validate_and_normalize,
    default_config_payload,
)


def test_default_config_has_under_review_flow():
    config = default_config_payload()
    assert config["submitted_status"] == "Under Review"
    assert "Under Review" in config["stages"]
    assert config["enforce_separation_of_duties"] is True


def test_validate_rejects_bad_submitted_status():
    with pytest.raises(HTTPException) as exc:
        validate_and_normalize({"submitted_status": "Approved", "stages": ["Draft", "Under Review", "Approved"]})
    assert exc.value.status_code == 422


def test_validate_accepts_pending_approval_alias():
    result = validate_and_normalize({
        "stages": ["Draft", "Submitted", "Pending Approval", "Approved", "Rejected"],
        "submitted_status": "Pending Approval",
        "approve_permission": "procurement.catalogue.approve",
        "decision_reason_min_length": 5,
    })
    assert result["submitted_status"] == "Pending Approval"
    assert result["decision_reason_min_length"] == 5


def test_pending_statuses_include_aliases():
    statuses = pending_statuses({"submitted_status": "Under Review"})
    assert "Under Review" in statuses
    assert "Pending Approval" in statuses


def test_can_approve_uses_configured_permission():
    assert can_approve_with_config(True, [], {"approve_permission": "x"}) is True
    assert can_approve_with_config(False, ["procurement.catalogue.approve"], {"approve_permission": "procurement.catalogue.approve"})
    assert can_approve_with_config(False, ["procurement.master.edit"], {"approve_permission": "procurement.catalogue.approve"}) is False


def test_default_config_includes_reviewer_stages():
    config = default_config_payload()
    assert config["reviewer_stages"]
    assert config["reviewer_stages"][0]["permission"] == "procurement.catalogue.approve"


def test_validate_accepts_ordered_reviewer_stages():
    result = validate_and_normalize({
        "stages": ["Draft", "Under Review", "Technical Review", "Approved", "Rejected"],
        "submitted_status": "Under Review",
        "approve_permission": "procurement.catalogue.approve",
        "decision_reason_min_length": 3,
        "reviewer_stages": [
            {"name": "Under Review", "permission": "procurement.catalogue.approve"},
            {"name": "Technical Review", "permission": "procurement.catalogue.technical"},
        ],
    })
    assert len(result["reviewer_stages"]) == 2
    assert result["reviewer_stages"][1]["permission"] == "procurement.catalogue.technical"


def test_validate_rejects_invalid_reviewer_stage_permission():
    with pytest.raises(HTTPException) as exc:
        validate_and_normalize({
            "stages": ["Draft", "Under Review", "Approved", "Rejected"],
            "submitted_status": "Under Review",
            "approve_permission": "procurement.catalogue.approve",
            "reviewer_stages": [{"name": "Under Review", "permission": "bad permission"}],
        })
    assert exc.value.status_code == 422
