from unittest.mock import Mock, patch
from fastapi import HTTPException
from app.domains.commercial_financials import movement_receipt_api as api


def test_endpoint_rejects_out_of_scope_issue():
    db = Mock()
    db.query.return_value.join.return_value.filter.return_value.one_or_none.return_value = None
    user = Mock(organization_id=7)
    with patch.object(api, 'guard') as access:
        try:
            api.movement_receipt_reconciliation(2, 10, user, db)
        except HTTPException as exc:
            assert exc.status_code == 404
        else:
            assert False, 'Expected 404'
        access.assert_called_once_with(db, user, 2, 'financials.view')


def test_endpoint_is_read_only_route():
    assert all(getattr(route, 'methods', set()) == {'GET'} for route in api.router.routes)
    assert '{stock_posting_line_id}' in api.router.routes[0].path


def test_receipt_cost_trace_scopes_receipt_headers_and_warehouses():
    import inspect
    src = inspect.getsource(api.movement_receipt_reconciliation)
    assert 'GoodsReceipt.organization_id == org' in src
    assert 'GoodsReceipt.project_id == pid' in src
    assert "GoodsReceipt.status == 'Posted'" in src
    assert 'lot.warehouse_id != posting.warehouse_id' in src
    assert 'receipt_warehouse != lot.warehouse_id' in src

