"""Fast safety checks; actual transaction tests remain deferred."""
from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.material_returns import _require_return_posting_gate, _return_posting_quantity


def test_return_posting_disabled_by_default(monkeypatch):
    monkeypatch.delenv('STORES_ATOMIC_LOT_RETURN_ENABLED', raising=False)
    monkeypatch.delenv('STORES_LOT_WRITER_CUTOVER', raising=False)
    with pytest.raises(HTTPException) as err:
        _require_return_posting_gate()
    assert err.value.status_code == 503


@pytest.mark.parametrize('return_enabled,cutover', [('true','false'),('false','true'),('false','false')])
def test_both_release_gates_required(monkeypatch, return_enabled, cutover):
    monkeypatch.setenv('STORES_ATOMIC_LOT_RETURN_ENABLED', return_enabled)
    monkeypatch.setenv('STORES_LOT_WRITER_CUTOVER', cutover)
    with pytest.raises(HTTPException) as err:
        _require_return_posting_gate()
    assert err.value.status_code == 503


def test_gate_only_allows_both_flags(monkeypatch):
    monkeypatch.setenv('STORES_ATOMIC_LOT_RETURN_ENABLED', 'true')
    monkeypatch.setenv('STORES_LOT_WRITER_CUTOVER', 'true')
    _require_return_posting_gate()


def test_return_cannot_exceed_remaining_issue_quantity():
    with pytest.raises(HTTPException) as err:
        _return_posting_quantity(SimpleNamespace(requested_quantity=Decimal('5'), received_quantity=Decimal('3')),
                                 SimpleNamespace(quantity=Decimal('5')), Decimal('3'))
    assert err.value.status_code == 409


def test_valid_return_quantity():
    result = _return_posting_quantity(SimpleNamespace(requested_quantity=Decimal('5'), received_quantity=Decimal('2.000')),
                                      SimpleNamespace(quantity=Decimal('5.000')), Decimal('3.000'))
    assert result == Decimal('2.000')


def test_nonfinite_return_blocked():
    with pytest.raises(HTTPException):
        _return_posting_quantity(SimpleNamespace(requested_quantity=Decimal('5'), received_quantity=Decimal('NaN')),
                                 SimpleNamespace(quantity=Decimal('5')), Decimal('0'))


@pytest.mark.parametrize('prior', ['NaN', 'Infinity', '-Infinity'])
def test_return_rejects_nonfinite_prior_balance(prior):
    with pytest.raises(HTTPException) as err:
        _return_posting_quantity(SimpleNamespace(requested_quantity=Decimal('2'), received_quantity=Decimal('2')),
                                 SimpleNamespace(quantity=Decimal('5')), Decimal(prior))
    assert err.value.status_code == 409


def test_return_rejects_receipt_above_requested_even_when_issue_is_sufficient():
    with pytest.raises(HTTPException) as err:
        _return_posting_quantity(SimpleNamespace(requested_quantity=Decimal('1'), received_quantity=Decimal('2')),
                                 SimpleNamespace(quantity=Decimal('10')), Decimal('0'))
    assert err.value.status_code == 409


def test_return_rejects_invalid_requested_quantity():
    with pytest.raises(HTTPException) as err:
        _return_posting_quantity(SimpleNamespace(requested_quantity=Decimal('NaN'), received_quantity=Decimal('2')),
                                 SimpleNamespace(quantity=Decimal('10')), Decimal('0'))
    assert err.value.status_code == 409
