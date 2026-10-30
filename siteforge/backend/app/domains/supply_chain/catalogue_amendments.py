"""Pure guards for immutable approved-item amendment requests."""
from fastapi import HTTPException

ALLOWED_CHANGES = frozenset({
    "specification",
    "specification_attributes",
    "size_rating",
    "approved_make",
    "material_grade",
    "applicable_standard",
    "model_number",
    "manufacturer_part_number",
    "hsn_code",
    "inspection_required",
    "tracking_required",
    "mtc_required",
    "calibration_certificate_required",
    "shelf_life_applicable",
    "shelf_life_days",
})
_BOOL_FIELDS = frozenset({
    "inspection_required",
    "tracking_required",
    "mtc_required",
    "calibration_certificate_required",
    "shelf_life_applicable",
})


def validate_amendment(data):
    if not isinstance(data, dict) or set(data) != {"changes", "reason"}:
        raise HTTPException(422, "Expected changes and reason")
    changes, reason = data["changes"], data["reason"]
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise HTTPException(422, "Amendment reason required (maximum 2000 characters)")
    if not isinstance(changes, dict) or not changes or set(changes) - ALLOWED_CHANGES:
        raise HTTPException(422, "Unsupported amendment fields")
    for key, value in changes.items():
        if key in _BOOL_FIELDS:
            if not isinstance(value, bool):
                raise HTTPException(422, f"{key} must be boolean")
        elif key == "shelf_life_days":
            if value is not None and (not isinstance(value, int) or not 1 <= value <= 36500):
                raise HTTPException(422, "shelf_life_days must be null or 1..36500")
        elif key == "specification_attributes":
            if not isinstance(value, dict) or len(value) > 100:
                raise HTTPException(422, "Invalid specification attributes")
        elif not isinstance(value, str) or len(value) > 2000:
            raise HTTPException(422, f"Invalid {key}")
    return changes, reason.strip()


def require_separation(submitter, creator, reviewer):
    if reviewer in (submitter, creator):
        raise HTTPException(403, "Creator/submitter cannot approve own amendment")


def require_current_version(base_version, current_version):
    if base_version != current_version:
        raise HTTPException(409, "Item version changed; amendment must be resubmitted")
