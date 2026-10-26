from types import SimpleNamespace as R
from app.domains.stores_inventory.phase5_operations import build_operations_view

def test_operations_custody_counts_without_stock_claim():
    req = R(id=2, requirement_line_id=9, work_package_id=3, planning_wbs_id=5)
    handovers = [R(id=1, material_request_id=2, handover_reference='H-1', status='Acknowledged', dispatched_quantity=8, received_quantity=8),
                 R(id=2, material_request_id=2, handover_reference='H-2', status='Discrepancy', dispatched_quantity=4, received_quantity=3)]
    ret = R(id=7, handover_id=1, status='QA Accepted', stock_posting_id=None, return_location_id=12,
            requested_quantity=2, received_quantity=2, qa_decision='Accepted')
    result = build_operations_view(handovers,[req],[ret])
    assert result['counts']['pending_posting'] == 1
    assert result['counts']['discrepancies'] == 1
    assert result['counts']['ledger_posted_returns'] == 0
    assert result['inventory_verified'] is False
    assert result['construction_consumption_verified'] is False
    assert result['records'][0]['requirement_line_id'] == 9

def test_operations_skips_unlinked_handover():
    handover = R(id=1, material_request_id=99, handover_reference='H-1', status='Discrepancy', dispatched_quantity=4, received_quantity=3)
    result = build_operations_view([handover], [], [])
    assert result['record_count'] == 0
    assert result['counts']['discrepancies'] == 0

def test_operations_posted_return_is_explicit_not_assumed():
    req=R(id=3, requirement_line_id=6, work_package_id=5, planning_wbs_id=None)
    h=R(id=8,material_request_id=3,handover_reference='H-8',status='Acknowledged',dispatched_quantity=5,received_quantity=5)
    r=R(id=9,handover_id=8,status='Posted',stock_posting_id=17,return_location_id=11,requested_quantity=1,received_quantity=1,qa_decision='Accepted')
    result=build_operations_view([h],[req],[r])
    assert result['counts']['ledger_posted_returns']==1
    assert result['records'][0]['return_stock_posting_id']==17
    assert result['inventory_verified'] is False

from datetime import datetime, timedelta, timezone

def test_operations_aging_overdue_acknowledgment_and_unknown_timestamp():
    now = datetime(2026, 10, 23, 12, tzinfo=timezone.utc)
    req = R(id=21, requirement_line_id=11, work_package_id=9, planning_wbs_id=None)
    old = R(id=1, material_request_id=21, handover_reference='D-1', status='Awaiting Acknowledgment',
            dispatched_quantity=2, received_quantity=None, created_at=now-timedelta(hours=50))
    new = R(id=2, material_request_id=21, handover_reference='D-2', status='Awaiting Acknowledgment',
            dispatched_quantity=2, received_quantity=None, created_at=now-timedelta(hours=2))
    unknown = R(id=3, material_request_id=21, handover_reference='D-3', status='Awaiting Acknowledgment',
            dispatched_quantity=2, received_quantity=None)
    closed = R(id=4, material_request_id=21, handover_reference='D-4', status='Acknowledged',
            dispatched_quantity=2, received_quantity=2, created_at=now-timedelta(hours=80))
    data = build_operations_view([old,new,unknown,closed], [req], [], now=now)
    assert data['counts']['awaiting_acknowledgment'] == 3
    assert data['counts']['overdue_acknowledgments'] == 1
    assert [r['acknowledgment_overdue'] for r in data['records']] == [True, False, False, False]
    assert data['inventory_verified'] is False

def test_operations_aging_supports_naive_db_timestamps_and_custom_threshold():
    now = datetime(2026, 10, 23, 12, tzinfo=timezone.utc)
    req = R(id=21, requirement_line_id=11, work_package_id=9, planning_wbs_id=None)
    old = R(id=1, material_request_id=21, handover_reference='D-1', status='Awaiting Acknowledgment',
            dispatched_quantity=2, received_quantity=None, created_at=datetime(2026, 10, 23, 6))
    data = build_operations_view([old], [req], [], now=now, acknowledgment_overdue_hours=4)
    assert data['counts']['overdue_acknowledgments'] == 1
    assert data['acknowledgment_overdue_hours'] == 4
