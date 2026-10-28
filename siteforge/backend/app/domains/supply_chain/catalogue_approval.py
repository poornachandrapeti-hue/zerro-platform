"""Independent validation for catalogue decisions."""
from fastapi import HTTPException


def validate_decision(data):
    if not isinstance(data, dict) or set(data) != {"action", "reason"}:
        raise HTTPException(422, "Provide action and reason")
    action, reason = data["action"], data["reason"]
    if action not in ("Approve", "Reject"):
        raise HTTPException(422, "Decision must be Approve or Reject")
    if not isinstance(reason, str) or not (3 <= len(reason.strip()) <= 2000):
        raise HTTPException(422, "Decision reason must contain 3 to 2000 characters")
    return action, reason.strip()
