from types import SimpleNamespace as Row
from fastapi import HTTPException
import pytest
from app.domains.stores_inventory.return_work_package_trace import build_work_package_trace


def example(return_status='QA Accepted', posted=False):
    req = Row(id=10, work_package_id=42, planning_wbs_id=4, requirement_line_id=11)
    h = Row(id=20, material_request_id=10, stock_posting_line_id=30,
            dispatched_quantity=10, received_quantity=10)
    line = Row(id=30, posting_id=40, quantity=10, item_id=90, unit='EA')
    issue = Row(id=40, kind='Issue', status='Posted')
    ret = Row(id=50, handover_id=20, requested_quantity=3, received_quantity=2,
              status=return_status, stock_posting_id=60 if posted else None)
    postings = [issue] + ([Row(id=60, kind='Return', status='Posted')] if posted else [])
    return [h], [req], [ret], [line], postings


def test_unposted_qa_return_does_not_reduce_ledger_outstanding():
    out = build_work_package_trace(*example())[0]
    assert out['ledger_outstanding_quantity'] == '10'
    assert out['ledger_posted_return_quantity'] == '0'
    assert out['pending_custody_return_quantity'] == '2'
    assert out['work_package_id'] == 42
    assert out['construction_consumption_verified'] is False


def test_only_posted_return_reduces_outstanding():
    out = build_work_package_trace(*example(posted=True))[0]
    assert out['ledger_outstanding_quantity'] == '8'
    assert out['ledger_posted_return_quantity'] == '2'
    assert out['pending_custody_return_quantity'] == '0'


def test_missing_ledger_posting_fails_closed():
    args = example(posted=True)
    args[-1].pop()
    with pytest.raises(HTTPException) as err:
        build_work_package_trace(*args)
    assert err.value.status_code == 409


def test_unmapped_handover_is_not_counted_as_verified():
    args = example()
    args[1].clear()
    assert build_work_package_trace(*args) == []


def test_invalid_quantity_fails_closed():
    args = example()
    args[3][0].quantity = -1
    with pytest.raises(HTTPException):
        build_work_package_trace(*args)
