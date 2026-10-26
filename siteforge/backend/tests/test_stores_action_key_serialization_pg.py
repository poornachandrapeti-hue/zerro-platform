"""PostgreSQL integration gate for actual application action-key locking helper.

Set STORES_TEST_DATABASE_URL to a disposable PostgreSQL test database.
No business tables are changed; advisory locks are transaction-local.
"""
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.domains.stores_inventory.idempotency_lock import lock_request_key

URL = os.getenv('STORES_TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not URL, reason='Dedicated PostgreSQL test database not configured')


@pytest.mark.parametrize('namespace', ['lot-reservation-release', 'lot-reservation-reassignment'])
def test_competing_action_key_waits_for_commit_or_rollback(namespace):
    engine = create_engine(URL, pool_size=3, pool_timeout=5)
    if engine.dialect.name != 'postgresql':
        pytest.skip('PostgreSQL required')
    held, release, acquired = threading.Event(), threading.Event(), threading.Event()
    lock_kwargs = dict(organization_id=51, project_id=52, key='action-duplicate-001', namespace=namespace)

    def first():
        with Session(engine) as db:
            lock_request_key(db, **lock_kwargs)
            held.set()
            assert release.wait(10)
            db.rollback()

    def second():
        assert held.wait(10)
        with Session(engine) as db:
            lock_request_key(db, **lock_kwargs)
            acquired.set()
            db.rollback()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            one, two = pool.submit(first), pool.submit(second)
            assert held.wait(10)
            with engine.connect() as connection:
                # A separate transaction cannot obtain the same project-scoped lock.
                available = connection.execute(text(
                    'SELECT pg_try_advisory_xact_lock(hashtextextended(:name,0))'),
                    {'name': f'stores:{namespace}:51:52:action-duplicate-001'}).scalar_one()
                assert available is False
                connection.rollback()
            assert not acquired.is_set()
            release.set()
            one.result(timeout=10)
            two.result(timeout=10)
            assert acquired.is_set()
    finally:
        release.set()
        engine.dispose()
