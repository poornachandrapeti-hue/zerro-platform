from types import SimpleNamespace as R
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.phase8_progress_evidence import material_progress_evidence_rows


def sample(status='Verified', package=12):
    usage = R(id=1, handover_id=2, work_package_id=package, item_id=7, unit='EA', quantity=3,
              status=status, usage_type='Installed', verified_by=9)
    handover = R(id=2, material_request_id=4, stock_posting_line_id=6)
    request = R(id=4, item_id=7, base_unit='EA', work_package_id=12, requirement_line_id=22, planning_wbs_id=33)
    line = R(id=6, posting_id=8, item_id=7, unit='EA')
    posting = R(id=8, kind='Issue', status='Posted')
    report = R(id=10, status='Approved')
    progress_line = R(id=11, report_id=10, activity_id=13, stock_posting_id=8, quantity=20, unit='M')
    activity = R(id=13, package_id=12)
    return ([usage], [handover], [request], [line], [posting], [progress_line], [report], [activity])


def test_qa_verified_usage_linked_but_never_earned():
    row = material_progress_evidence_rows(*sample())[0]
    assert row['qa_verified_material_quantity'] == '3'
    assert row['approved_progress_evidence'][0]['progress_report_id'] == 10
    assert row['progress_earned'] is False and row['billing_certified'] is False


def test_pending_qa_not_counted_verified():
    row = material_progress_evidence_rows(*sample('Pending QA'))[0]
    assert row['qa_verified_material_quantity'] is None
    assert row['pending_qa_material_quantity'] == '3'


def test_mismatched_work_package_rejected():
    with pytest.raises(HTTPException) as exc:
        material_progress_evidence_rows(*sample(package=14))
    assert exc.value.status_code == 409


def test_unapproved_progress_not_linked():
    args = list(sample())
    args[6] = [R(id=10, status='Pending Review')]
    assert material_progress_evidence_rows(*args)[0]['approved_progress_evidence'] == []
