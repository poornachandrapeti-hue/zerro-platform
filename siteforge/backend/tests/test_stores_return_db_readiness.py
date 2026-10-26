from app.domains.stores_inventory.return_db_readiness import REQUIRED, classify_schema, audit
import pytest

def test_ready_schema():
    assert classify_schema('postgresql', REQUIRED) == []

def test_sqlite_not_ready():
    assert any('PostgreSQL' in issue for issue in classify_schema('sqlite', REQUIRED))

def test_missing_columns_fail_closed():
    present = {table: cols.copy() for table, cols in REQUIRED.items()}
    present['stock_balances'].remove('reserved')
    assert any('reserved' in issue for issue in classify_schema('postgresql', present))

def test_missing_table_fails():
    present = {table: cols for table, cols in REQUIRED.items() if table != 'stock_postings'}
    assert any('stock_postings' in issue for issue in classify_schema('postgresql', present))

def test_explicit_project_required():
    with pytest.raises(ValueError):
        audit(0)
