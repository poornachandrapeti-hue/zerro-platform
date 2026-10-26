from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.material_returns import summarize_return_exception_tasks, internal_command_center_return_exceptions


def test_return_workload_counts_active_overdue_and_missing():
    rows = [SimpleNamespace(id=1, handover_id=10, status='Awaiting QA', stock_posting_id=None),
            SimpleNamespace(id=2, handover_id=11, status='Submitted', stock_posting_id=None),
            SimpleNamespace(id=3, handover_id=12, status='Stock Posted', stock_posting_id=100)]
    tasks = [SimpleNamespace(source_id=1, owner_id=7, status='Open', due_date=date.today()-timedelta(days=1)),
             SimpleNamespace(source_id=3, owner_id=7, status='Completed', due_date=None)]
    result = summarize_return_exception_tasks(rows, tasks)
    assert result['active_tasks'] == 1
    assert result['overdue_tasks'] == 1
    assert result['unassigned_exceptions'] == 1
    assert result['by_owner_id'] == {'7': 1}
    assert result['physical_stock_readiness'] == 'Unverified'


def test_return_workload_ignores_cross_scope_tasks():
    rows = [SimpleNamespace(id=1, handover_id=10, status='QA Accepted', stock_posting_id=None, return_location_id=9)]
    tasks = [SimpleNamespace(source_id=99, owner_id=7, status='Blocked', due_date=date.today()-timedelta(days=1))]
    summary = summarize_return_exception_tasks(rows, tasks)
    assert summary['active_tasks'] == 0
    assert summary['unassigned_exceptions'] == 1


def test_service_feed_denies_no_key(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, 'command_center_identity_service_key', 'expected-key')
    req = SimpleNamespace(headers={'X-ZerroR-Service-Key':'bad-key'})
    with pytest.raises(HTTPException) as exc:
        internal_command_center_return_exceptions(1, req, Mock())
    assert exc.value.status_code == 403
