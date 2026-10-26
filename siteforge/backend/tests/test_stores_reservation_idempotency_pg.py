"""Actual PostgreSQL advisory-lock concurrency tests (no application data writes).

STORES_TEST_DATABASE_URL must point to a disposable PostgreSQL database.
This tests the exact lock helper invoked by reserve_lot, not the full ORM writer.
"""
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.domains.stores_inventory.idempotency_lock import lock_request_key

URL = os.getenv('STORES_TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not URL, reason='Dedicated PostgreSQL test DB not configured')


def test_duplicate_key_waits_for_prior_transaction():
    engine = create_engine(URL, pool_size=3, pool_timeout=5)
    if engine.dialect.name != 'postgresql':
        pytest.skip('PostgreSQL required')
    first_locked = threading.Event()
    release_first = threading.Event()
    second_started = threading.Event()
    second_locked = threading.Event()

    def first():
        with Session(engine) as db:
            lock_request_key(db, organization_id=91, project_id=74, key='repeat-01', namespace='lot-reservation')
            first_locked.set()
            assert release_first.wait(timeout=8)
            db.commit()

    def second():
        assert first_locked.wait(timeout=8)
        with Session(engine) as db:
            second_started.set()
            lock_request_key(db, organization_id=91, project_id=74, key='repeat-01', namespace='lot-reservation')
            second_locked.set()
            db.rollback()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(first)
            b = pool.submit(second)
            assert second_started.wait(timeout=8)
            # A second connection cannot acquire the same advisory lock while
            # the first transaction holds it (checked via pg_try_advisory_xact_lock).
            with engine.connect() as conn:
                from sqlalchemy import text
                available = conn.execute(text('SELECT pg_try_advisory_xact_lock(hashtextextended(:key,0))'),
                    {'key':'stores:lot-reservation:91:74:repeat-01'}).scalar_one()
                assert available is False
                conn.rollback()
            assert not second_locked.is_set()
            release_first.set()
            a.result(timeout=8)
            b.result(timeout=8)
            assert second_locked.is_set()
    finally:
        release_first.set()
        engine.dispose()


def test_isolation_between_projects():
    engine = create_engine(URL)
    if engine.dialect.name != 'postgresql':
        pytest.skip('PostgreSQL required')
    try:
        with Session(engine) as first, Session(engine) as second:
            lock_request_key(first, organization_id=91, project_id=74, key='same', namespace='lot-reservation')
            lock_request_key(second, organization_id=91, project_id=75, key='same', namespace='lot-reservation')
            first.rollback()
            second.rollback()
    finally:
        engine.dispose()
