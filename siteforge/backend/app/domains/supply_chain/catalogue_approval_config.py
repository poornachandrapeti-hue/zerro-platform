"""Organization catalogue approval workflow configuration."""
from __future__ import annotations

from fastapi import HTTPException

from .models import CatalogueApprovalConfig

DEFAULT_STAGES = ["Draft", "Submitted", "Under Review", "Approved", "Rejected"]
ALLOWED_SUBMITTED = {"Pending Approval", "Under Review"}


def default_config_payload():
    return {
        "id": None,
        "stages": list(DEFAULT_STAGES),
        "submitted_status": "Under Review",
        "approve_permission": "procurement.catalogue.approve",
        "require_decision_reason": True,
        "decision_reason_min_length": 3,
        "enforce_separation_of_duties": True,
        "reviewer_stages": [
            {"name": "Under Review", "permission": "procurement.catalogue.approve"},
        ],
        "active": True,
        "is_default": True,
    }


def config_payload(row: CatalogueApprovalConfig | None):
    if row is None:
        return default_config_payload()
    return {
        "id": row.id,
        "stages": list(row.stages or DEFAULT_STAGES),
        "submitted_status": row.submitted_status,
        "approve_permission": row.approve_permission,
        "require_decision_reason": row.require_decision_reason,
        "decision_reason_min_length": row.decision_reason_min_length,
        "enforce_separation_of_duties": row.enforce_separation_of_duties,
        "reviewer_stages": list(getattr(row, "reviewer_stages", None) or []),
        "active": row.active,
        "is_default": False,
    }


def get_config(db, organization_id: int) -> CatalogueApprovalConfig | None:
    return (
        db.query(CatalogueApprovalConfig)
        .filter_by(organization_id=organization_id, active=True)
        .first()
    )


def get_config_or_defaults(db, organization_id: int) -> dict:
    return config_payload(get_config(db, organization_id))


def validate_and_normalize(data: dict) -> dict:
    if not isinstance(data, dict):
        raise HTTPException(422, "Invalid approval configuration")
    stages = data.get("stages", DEFAULT_STAGES)
    if not isinstance(stages, list) or not (3 <= len(stages) <= 12):
        raise HTTPException(422, "Provide 3 to 12 stage labels")
    cleaned_stages = []
    for stage in stages:
        if not isinstance(stage, str) or not (1 <= len(stage.strip()) <= 40):
            raise HTTPException(422, "Invalid stage label")
        cleaned_stages.append(stage.strip())
    submitted_status = str(data.get("submitted_status", "Under Review")).strip()
    if submitted_status not in ALLOWED_SUBMITTED:
        raise HTTPException(422, "submitted_status must be Under Review or Pending Approval")
    permission = str(data.get("approve_permission", "procurement.catalogue.approve")).strip()
    if not (1 <= len(permission) <= 120) or " " in permission:
        raise HTTPException(422, "Invalid approve permission key")
    min_length = data.get("decision_reason_min_length", 3)
    if not isinstance(min_length, int) or not 3 <= min_length <= 200:
        raise HTTPException(422, "decision_reason_min_length must be 3..200")
    reviewer_stages = data.get("reviewer_stages", [])
    if reviewer_stages in (None, ""):
        reviewer_stages = []
    if not isinstance(reviewer_stages, list) or len(reviewer_stages) > 8:
        raise HTTPException(422, "reviewer_stages must be a list of up to 8 stages")
    cleaned_reviewers = []
    for stage in reviewer_stages:
        if not isinstance(stage, dict):
            raise HTTPException(422, "Invalid reviewer stage")
        name = str(stage.get("name") or "").strip()
        stage_permission = str(stage.get("permission") or permission).strip()
        if not (1 <= len(name) <= 40) or not (1 <= len(stage_permission) <= 120) or " " in stage_permission:
            raise HTTPException(422, "Invalid reviewer stage name or permission")
        cleaned_reviewers.append({"name": name, "permission": stage_permission})
    return {
        "stages": cleaned_stages,
        "submitted_status": submitted_status,
        "approve_permission": permission,
        "require_decision_reason": bool(data.get("require_decision_reason", True)),
        "decision_reason_min_length": min_length,
        "enforce_separation_of_duties": bool(data.get("enforce_separation_of_duties", True)),
        "reviewer_stages": cleaned_reviewers,
        "active": bool(data.get("active", True)),
    }


def save_config(db, user, data: dict) -> CatalogueApprovalConfig:
    payload = validate_and_normalize(data)
    row = db.query(CatalogueApprovalConfig).filter_by(organization_id=user.organization_id).first()
    if row is None:
        row = CatalogueApprovalConfig(organization_id=user.organization_id, modified_by=user.id)
        db.add(row)
    for key, value in payload.items():
        setattr(row, key, value)
    row.modified_by = user.id
    db.flush()
    return row


def pending_statuses(config: dict) -> set[str]:
    return {config.get("submitted_status") or "Under Review", "Pending Approval", "Under Review"}


def can_approve_with_config(organization_admin: bool, role_permissions, config: dict) -> bool:
    if organization_admin:
        return True
    permission = config.get("approve_permission") or "procurement.catalogue.approve"
    return permission in (role_permissions or ())
