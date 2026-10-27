"""Read-only QA authority diagnostics: never a stock release."""
from decimal import Decimal
from types import SimpleNamespace

from app.domains.stores_inventory.lot_reconciliation import reconcile_line


def qa_case(accepted, pending=0, rejected=0, quarantined=0, status="Disposition Recorded"):
    return SimpleNamespace(accepted_qty=Decimal(str(accepted)),
        pending_qty=Decimal(str(pending)), rejected_qty=Decimal(str(rejected)),
        quarantined_qty=Decimal(str(quarantined)), status=status)


def test_missing_case_is_flagged_despite_quality_approval():
    result = reconcile_line(10, [], None, [], quality_approved=7)
    assert "QA_CASE_MISSING" in result["flags"]
    assert "QUALITY_STORES_ACCEPTANCE_MISMATCH" in result["flags"]
    assert result["lot_issue_enabled"] is False


def test_reconciled_partial_quantity_not_released():
    result = reconcile_line(10, [], qa_case(7, rejected=3), [], quality_approved=7)
    assert "QUALITY_STORES_ACCEPTANCE_MISMATCH" not in result["flags"]
    assert "NON_ACCEPTED_MATERIAL_PRESENT" in result["flags"]
    assert result["quality_module_approved_quantity"] == "7"
    assert result["lot_issue_enabled"] is False


def test_revocation_keeps_mismatch_visible_and_fail_closed():
    result = reconcile_line(10, [], qa_case(5, quarantined=5, status="Quality Revoked"), [], quality_approved=7)
    assert "QUALITY_REVOKED" in result["flags"]
    assert "QUALITY_STORES_ACCEPTANCE_MISMATCH" in result["flags"]
    assert result["quality_stores_quantity_difference"] == "2"
    assert result["lot_issue_enabled"] is False


def test_no_quality_projection_does_not_fabricate_evidence():
    result = reconcile_line(2, [], qa_case(2), [])
    assert result["quality_module_approved_quantity"] is None
    assert "QUALITY_STORES_ACCEPTANCE_MISMATCH" not in result["flags"]
    assert result["lot_issue_enabled"] is False


def test_out_of_range_quality_projection_flagged():
    result = reconcile_line(10, [], qa_case(10), [], quality_approved=12)
    assert "QUALITY_APPROVAL_OUT_OF_RANGE" in result["flags"]
    assert result["lot_issue_enabled"] is False
