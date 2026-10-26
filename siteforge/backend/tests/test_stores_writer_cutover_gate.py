"""Regression tests for mutually exclusive legacy and lot posting writers."""
import pytest
from fastapi import HTTPException
from app.domains.supply_chain import stock
from app.domains.stores_inventory import atomic_lot_acceptance, atomic_lot_issue, lot_reservations


@pytest.mark.parametrize('method', [stock.accept_receipt, stock.reserve_stock, stock.issue_stock])
def test_legacy_writer_disabled_during_cutover(monkeypatch, method):
    monkeypatch.setenv('STORES_LOT_WRITER_CUTOVER', 'true')
    with pytest.raises(HTTPException) as err:
        method(None, None, None, None)
    assert err.value.status_code == 503


def test_legacy_gate_allows_default_mode(monkeypatch):
    monkeypatch.delenv('STORES_LOT_WRITER_CUTOVER', raising=False)
    stock._require_legacy_writer_enabled()


def test_atomic_acceptance_rejected_without_cutover(monkeypatch):
    monkeypatch.delenv('STORES_LOT_WRITER_CUTOVER', raising=False)
    with pytest.raises(HTTPException) as err:
        atomic_lot_acceptance.accept_lot(None, None, None, lot_id=1, quantity=1, posting_number='X')
    assert err.value.status_code == 503


def test_atomic_issue_rejected_without_cutover(monkeypatch):
    monkeypatch.setenv('STORES_ATOMIC_LOT_ISSUE_ENABLED', 'true')
    monkeypatch.delenv('STORES_LOT_WRITER_CUTOVER', raising=False)
    with pytest.raises(HTTPException) as err:
        atomic_lot_issue.issue_lot(None, None, None, lot_id=1, quantity=1, posting_number='X', recipient='A', reason='B')
    assert err.value.status_code == 503


def test_lot_reservations_rejected_without_cutover(monkeypatch):
    monkeypatch.setenv('STORES_LOT_RESERVATIONS_ENABLED', 'true')
    monkeypatch.delenv('STORES_LOT_WRITER_CUTOVER', raising=False)
    with pytest.raises(HTTPException) as err:
        lot_reservations._enabled()
    assert err.value.status_code == 503


def test_all_lot_writers_default_disabled(monkeypatch):
    monkeypatch.delenv('STORES_LOT_WRITER_CUTOVER', raising=False)
    monkeypatch.delenv('STORES_ATOMIC_LOT_ISSUE_ENABLED', raising=False)
    monkeypatch.delenv('STORES_LOT_RESERVATIONS_ENABLED', raising=False)
    with pytest.raises(HTTPException):
        atomic_lot_issue.issue_lot(None, None, None, lot_id=1, quantity=1, posting_number='X', recipient='A', reason='B')
    with pytest.raises(HTTPException):
        lot_reservations._enabled()
