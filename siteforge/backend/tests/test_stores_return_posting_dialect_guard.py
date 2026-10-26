"""Fail-closed dialect guard for feature-gated return postings.

These tests do not replace live PostgreSQL concurrency and rollback tests.
"""
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.material_returns import _require_postgres_row_locking

class FakeDB:
    def __init__(self, name):
        self.name = name
    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name=self.name))


def test_postgresql_allowed():
    _require_postgres_row_locking(FakeDB('postgresql'))

@pytest.mark.parametrize('dialect', ['sqlite', 'mysql', None, ''])
def test_other_or_unknown_dialect_blocked(dialect):
    with pytest.raises(HTTPException) as exc:
        _require_postgres_row_locking(FakeDB(dialect))
    assert exc.value.status_code == 503
