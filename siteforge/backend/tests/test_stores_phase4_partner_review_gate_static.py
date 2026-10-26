"""Source-level guards; live database authorization must also be tested."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = (ROOT / 'app/domains/stores_inventory/material_requests.py').read_text()
UI = (ROOT.parent / 'frontend/src/stores.tsx').read_text()


def test_internal_queue_needs_reviewer_permission():
    block = CODE.split('def review_queue(', 1)[1].split('def validate_partner_review_scope', 1)[0]
    assert "stores.requests.review" in block and "_project(db, u, pid, action=" in block
    assert "'Pending Approval'" in block


def test_partner_approval_revalidates_work_scope():
    assert "if data.decision == 'Approved':" in CODE
    assert 'validate_partner_review_scope(db, row, parent)' in CODE
    assert "wp.release_state != 'Released'" in CODE
    assert 'WorkPackageRequirement.package_id == wp.id' in CODE


def test_legacy_unlinked_requests_cannot_be_approved():
    assert 'Unlinked legacy requests cannot be approved' in CODE


def test_internal_ui_displays_partner_origin_and_filter():
    assert 'Pending approval only' in UI
    assert 'Partner · company' in UI
