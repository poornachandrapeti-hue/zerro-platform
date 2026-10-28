import pytest
from fastapi import HTTPException
from app.domains.supply_chain.catalogue_amendments import (
    validate_amendment, require_separation, require_current_version, ALLOWED_CHANGES,
)


def test_allowed_changes_exclude_stable_identity():
    assert "code" not in ALLOWED_CHANGES
    assert "base_unit" not in ALLOWED_CHANGES
    assert "category" not in ALLOWED_CHANGES


def test_amendment_reason_and_specs():
    changes, reason = validate_amendment({"changes": {"specification": "60 m3/hr"}, "reason": "Revised capacity"})
    assert changes["specification"] == "60 m3/hr"
    assert reason == "Revised capacity"


@pytest.mark.parametrize("payload", [
    {}, {"changes": {}, "reason": "x"},
    {"changes": {"code": "NEW"}, "reason": "x"},
    {"changes": {"specification": "new"}, "reason": " "},
    {"changes": {"inspection_required": "yes"}, "reason": "x"},
    {"changes": {"specification_attributes": []}, "reason": "x"},
])
def test_invalid_amendments(payload):
    with pytest.raises(HTTPException) as e:
        validate_amendment(payload)
    assert e.value.status_code == 422


def test_no_self_approval():
    for reviewer in (10, 20):
        with pytest.raises(HTTPException) as e:
            require_separation(10, 20, reviewer)
        assert e.value.status_code == 403
    require_separation(10, 20, 30)


def test_version_conflict():
    with pytest.raises(HTTPException) as e:
        require_current_version(2, 3)
    assert e.value.status_code == 409
    require_current_version(3, 3)
