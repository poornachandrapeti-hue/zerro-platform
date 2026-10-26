import pytest
from app.baseline_validation import validate_document

BASE = {"project_code":"P-1","revision":"R1","approval_status":"approved", "approved_by":"user-2", "approved_on":"2026-10-18", "approval_reference":"APR-1", "activities":[{"package_code":"W1","activity_code":"A1","unit":"m3","scope_quantity":100,"cumulative_plan":[{"date":"2026-10-01","quantity":20},{"date":"2026-10-31","quantity":100}]}]}

def test_valid_approved():
    assert validate_document(BASE)["revision"] == "R1"

def test_draft_cannot_be_approved_data():
    with pytest.raises(ValueError):
        validate_document({**BASE,"approval_status":"draft"})

def test_invalid_milestones_rejected():
    with pytest.raises(ValueError):
        validate_document({**BASE,"activities":[{**BASE["activities"][0],"cumulative_plan":[{"date":"2026-10-01","quantity":80},{"date":"2026-10-31","quantity":70}]}]})
