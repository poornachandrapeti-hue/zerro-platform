"""Read-model tests: transfer returns must trace to the same destination lot and issue."""
from types import SimpleNamespace as R
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.return_work_package_trace import build_work_package_trace


def sources(*, posted=True):
    request = R(id=3, work_package_id=8, planning_wbs_id=9, requirement_line_id=10)
    line = R(id=12, posting_id=20, item_id=7, unit='EA', quantity=5)
    issue = R(id=20, kind='Issue', status='Posted')
    handover = R(id=31, material_request_id=3, stock_posting_line_id=12, dispatched_quantity=5, received_quantity=5)
    ret = R(id=40, handover_id=31, stock_posting_id=25 if posted else None, received_quantity=2, requested_quantity=2, status='QA Accepted')
    return request, line, issue, handover, ret


def trace(transfer_lot=91, original_issue=12, returned_quantity=2, *, posted=True):
    req, line, issue, h, ret = sources(posted=posted)
    t_issue = R(stock_posting_line_id=12, transfer_destination_lot_id=91, quantity=5)
    rline = R(id=77, posting_id=25, quantity=2)
    t_return = R(stock_posting_line_id=77, transfer_destination_lot_id=transfer_lot,
                 original_issue_line_id=original_issue, quantity=returned_quantity)
    posts = [issue, R(id=25, kind='Return', status='Posted')] if posted else [issue]
    return build_work_package_trace([h], [req], [ret], [line], posts,
                                   [t_issue], [t_return] if posted else [], [rline] if posted else [])


def test_transfer_return_matches_original_issue():
    row = trace()[0]
    assert row['issue_lot_source'] == 'Transfer'
    assert row['transfer_destination_lot_id'] == 91
    assert row['return_provenance_verified'] is True
    assert row['ledger_outstanding_quantity'] == '3'


@pytest.mark.parametrize('kwargs', [{'transfer_lot':92}, {'original_issue':13}, {'returned_quantity':1}])
def test_transfer_return_provenance_mismatch_fails(kwargs):
    with pytest.raises(HTTPException) as exc:
        trace(**kwargs)
    assert exc.value.status_code == 409


def test_pending_return_not_mistaken_for_posted():
    row = trace(posted=False)[0]
    assert row['ledger_posted_return_quantity'] == '0'
    assert row['return_provenance_verified'] is False
