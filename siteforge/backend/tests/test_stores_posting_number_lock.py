"""Application lot writer posting-number serialization regression checks."""
from unittest.mock import Mock
import inspect
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.posting_number_lock import lock_stock_posting_number
from app.domains.stores_inventory.atomic_lot_acceptance import accept_lot
from app.domains.stores_inventory.atomic_lot_issue import issue_lot


def test_number_normalizes_like_authoritative_stock_posting_key():
    db = Mock()
    lock_stock_posting_number(db, organization_id=3, project_id=9, number='  ISSUE-001  ')
    _, params = db.execute.call_args.args
    assert params['lock_name'] == 'stores:stock-posting-number:3:9:issue-001'


def test_empty_number_rejected():
    with pytest.raises(HTTPException) as exc:
        lock_stock_posting_number(Mock(), organization_id=3, project_id=9, number='  ')
    assert exc.value.status_code == 422


def test_both_lot_writers_lock_before_row_locks():
    for fn in (accept_lot, issue_lot):
        source = inspect.getsource(fn)
        assert source.index('lock_stock_posting_number(db,') < source.index('lot = db.execute(')


def test_namespace_project_scoped_and_writer_agnostic():
    db = Mock()
    lock_stock_posting_number(db, organization_id=3, project_id=9, number='ISSUE-1')
    first = db.execute.call_args.args[1]['lock_name']
    lock_stock_posting_number(db, organization_id=3, project_id=10, number='ISSUE-1')
    second = db.execute.call_args.args[1]['lock_name']
    assert first != second
