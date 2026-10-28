import pytest
from fastapi import HTTPException
from app.domains.supply_chain.catalogue_approval import validate_decision

@pytest.mark.parametrize("action", ["Approve", "Reject"])
def test_valid_decisions(action):
    assert validate_decision({"action": action, "reason": "Reviewed for accuracy"}) == (action, "Reviewed for accuracy")

@pytest.mark.parametrize("payload", [
    {}, {"action": "Approve"}, {"reason": "approved"},
    {"action": "Invalid", "reason": "Good"},
    {"action": "Approve", "reason": ""},
    {"action": "Approve", "reason": "ab"},
    {"action": "Reject", "reason": 45},
    {"action": "Reject", "reason": "Fine", "extra": 1},
    {"action": "Approve", "reason": "x" * 2001},
])
def test_invalid_decisions(payload):
    with pytest.raises(HTTPException) as exc:
        validate_decision(payload)
    assert exc.value.status_code == 422
