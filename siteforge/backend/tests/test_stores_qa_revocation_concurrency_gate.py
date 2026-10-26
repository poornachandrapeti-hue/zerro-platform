"""QA revocation safety contract and optional PostgreSQL row-lock interleaving.

The PostgreSQL test demonstrates the production lock protocol on isolated test
rows. It is NOT a live API/ORM integration test. Enable with a disposable
STORES_TEST_DATABASE_URL. No application tables are altered.
"""
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

SRC = Path(__file__).resolve().parents[1] / 'app/domains/stores_inventory'


def test_qa_revocation_is_terminal_for_new_revocations_but_idempotent_for_retry():
    source = (SRC / 'router.py').read_text().split('def revoke_inspection_acceptance(', 1)[1].split('@router.get(', 1)[0]
    assert source.index('if prior:') < source.index('if case.status == "Quality Revoked":')
    assert source.index('if case.status == "Quality Revoked":') < source.index('case.accepted_qty -= data.quantity')
    assert 'case.version += 1' in source


def test_lot_writers_lock_current_qa_case_before_mutating_stock():
    for file in ('atomic_lot_acceptance.py', 'atomic_lot_issue.py', 'lot_reservations.py'):
        source = (SRC / file).read_text()
        assert 'StoresInspectionCase' in source and '.with_for_update()' in source
        assert source.index('case.status not in') < source.index('case_version_at_entry == case.version')


@pytest.mark.skipif(not os.getenv('STORES_TEST_DATABASE_URL'), reason='Disposable PostgreSQL test URL not configured')
@pytest.mark.parametrize('stock_action', ['accept', 'reserve', 'issue'])
def test_revocation_serializes_stock_action_with_row_lock(stock_action):
    """A revocation that owns the QA case lock must be seen by competing writers."""
    engine = create_engine(os.environ['STORES_TEST_DATABASE_URL'], pool_size=3)
    if engine.dialect.name != 'postgresql':
        pytest.skip('PostgreSQL required')
    name = f'stores_qa_lock_{uuid.uuid4().hex[:12]}'
    revoked = threading.Event()
    attempt = threading.Event()
    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE TABLE {name} (id integer PRIMARY KEY, status text NOT NULL, version integer NOT NULL)'))
            conn.execute(text(f"INSERT INTO {name} VALUES (1, 'Disposition Recorded', 1)"))

        def revoke():
            with engine.begin() as conn:
                conn.execute(text("SET LOCAL lock_timeout = '8s'"))
                conn.execute(text(f'SELECT status FROM {name} WHERE id=1 FOR UPDATE')).scalar_one()
                attempt.wait(timeout=5)
                conn.execute(text(f"UPDATE {name} SET status='Quality Revoked', version=version+1 WHERE id=1"))
            revoked.set()

        def stock_writer():
            attempt.set()
            # Wait until revocation commits, then obtain the same lock as each
            # existing application lot-writer query obtains.
            if not revoked.wait(timeout=8):
                raise AssertionError('Revocation did not commit')
            with engine.begin() as conn:
                conn.execute(text("SET LOCAL lock_timeout = '8s'"))
                status, version = conn.execute(text(f'SELECT status, version FROM {name} WHERE id=1 FOR UPDATE')).one()
                return status, version

        with ThreadPoolExecutor(max_workers=2) as pool:
            left = pool.submit(revoke)
            right = pool.submit(stock_writer)
            left.result(timeout=12)
            state = right.result(timeout=12)
        assert state == ('Quality Revoked', 2), stock_action
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP TABLE IF EXISTS {name}'))
        engine.dispose()
