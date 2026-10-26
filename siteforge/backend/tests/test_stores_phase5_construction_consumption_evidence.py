from types import SimpleNamespace as R
from app.domains.stores_inventory.construction_consumption_evidence import match_approved_progress_evidence


def trace():
    return [{'issue_posting_id': 4, 'work_package_id': 8, 'ledger_outstanding_quantity': '6'}]


def test_explicit_approved_progress_is_evidence_not_consumption():
    lines = [R(id=1, stock_posting_id=4, activity_id=2, report_id=3, quantity=20, unit='m3')]
    reports = [R(id=3, status='Approved')]
    activities = [R(id=2, package_id=8)]
    result = match_approved_progress_evidence(trace(), lines, reports, activities)[0]
    assert result['approved_construction_evidence_count'] == 1
    assert result['approved_construction_evidence'][0]['activity_quantity'] == '20'
    assert result['construction_consumption_verified'] is False
    assert result['installation_verified'] is False
    assert result['ledger_outstanding_quantity'] == '6'


def test_draft_and_cross_package_lines_are_not_matched():
    lines = [R(id=1, stock_posting_id=4, activity_id=2, report_id=3, quantity=2, unit='EA'),
             R(id=2, stock_posting_id=4, activity_id=9, report_id=5, quantity=1, unit='EA')]
    reports = [R(id=3, status='Draft'), R(id=5, status='Approved')]
    activities = [R(id=2, package_id=8), R(id=9, package_id=99)]
    assert match_approved_progress_evidence(trace(), lines, reports, activities)[0]['approved_construction_evidence_count'] == 0


def test_missing_report_or_activity_not_inferred():
    lines = [R(id=1, stock_posting_id=4, activity_id=2, report_id=7, quantity=1, unit='EA')]
    assert match_approved_progress_evidence(trace(), lines, [], [R(id=2, package_id=8)])[0]['approved_construction_evidence'] == []
