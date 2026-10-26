"""Offline guards for disabled-by-default same-project paired transfer posting.
Live SQL locking and ledger behavior still require PostgreSQL integration tests.
"""
from pathlib import Path
import pytest
from fastapi import HTTPException
from types import SimpleNamespace
from app.domains.stores_inventory.transfer_posting_readiness import (
    assert_transfer_posting_gate, _assert_transfer_ready,
)


def test_posting_disabled_without_explicit_opt_in(monkeypatch):
    monkeypatch.delenv('STORES_ATOMIC_TRANSFER_POSTING_ENABLED', raising=False)
    monkeypatch.delenv('STORES_LOT_WRITER_CUTOVER', raising=False)
    with pytest.raises(HTTPException) as exc:
        assert_transfer_posting_gate()
    assert exc.value.status_code == 503


def test_two_flags_required(monkeypatch):
    monkeypatch.setenv('STORES_ATOMIC_TRANSFER_POSTING_ENABLED', 'true')
    monkeypatch.delenv('STORES_LOT_WRITER_CUTOVER', raising=False)
    with pytest.raises(HTTPException):
        assert_transfer_posting_gate()


def _rows(**overrides):
    transfer = dict(id=7, project_id=1, destination_project_id=1, status='Received',
                    discrepancy_status='Not Required', destination_custodian_company_id=None,
                    custody_confirmed_by=None, quantity=5, dispatched_quantity=5,
                    received_quantity=5, damaged_quantity=0, destination_warehouse_id=4, item_id=11)
    transfer.update(overrides)
    lineage = SimpleNamespace(id=99, status='Planned', source_posting_id=None,
                              destination_posting_id=None, quantity=5, source_receipt_lot_id=20)
    destination = SimpleNamespace(status='PendingPostingAndQA', lineage_id=99,
                                  source_receipt_lot_id=20, destination_warehouse_id=4,
                                  item_id=11, quantity=5)
    return SimpleNamespace(**transfer), lineage, destination


def test_matching_transfer_eligible_for_internal_posting():
    assert _assert_transfer_ready(*_rows()) == 5


def test_interproject_rejected():
    with pytest.raises(HTTPException) as exc:
        _assert_transfer_ready(*_rows(destination_project_id=2))
    assert exc.value.status_code == 409


def test_partial_receipt_rejected():
    with pytest.raises(HTTPException):
        _assert_transfer_ready(*_rows(received_quantity=4))


def test_posted_lineage_rejected():
    t, l, d = _rows()
    l.status = 'Posted'
    with pytest.raises(HTTPException):
        _assert_transfer_ready(t, l, d)


def test_both_ledger_posts_and_quarantine_in_single_commit_source_contract():
    code = Path(__file__).resolve().parents[1].joinpath('app/domains/stores_inventory/transfer_posting_readiness.py').read_text()
    assert "'TransferOut'" in code and "'TransferIn'" in code
    assert "destination.status = 'PostedPendingQA'" in code
    assert code.index("lineage.source_posting_id = out_post.id") < code.index('commit(db)', code.index('def post_transfer_stock'))
