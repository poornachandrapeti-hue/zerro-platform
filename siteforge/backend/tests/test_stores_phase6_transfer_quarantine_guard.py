"""Fail-closed check for unallocated transfer-derived stock in shared balance."""
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.atomic_lot_issue import _require_full_coverage


class Result:
    def __init__(self, value): self.value = value
    def scalar_one_or_none(self): return self.value
    def all(self): return []


class FakeDB:
    def __init__(self, transfer_line):
        self.transfer_line = transfer_line
        self.calls = 0
    def execute(self, statement):
        self.calls += 1
        return Result(self.transfer_line) if self.calls == 1 else Result(None)


def test_destination_transfer_credit_blocks_grn_lot_allocation():
    db = FakeDB(984)
    with pytest.raises(HTTPException) as error:
        _require_full_coverage(db, SimpleNamespace(id=123), 52, 65)
    assert error.value.status_code == 409
    assert 'quarantined' in error.value.detail
    assert db.calls == 1


def test_no_destination_transfer_allows_existing_coverage_verification():
    db = FakeDB(None)
    _require_full_coverage(db, SimpleNamespace(id=123), 52, 65)
    assert db.calls == 2
