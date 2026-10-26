"""PostgreSQL serialization test using the exact application posting lock.

Use only STORES_TEST_DATABASE_URL targeting a disposable PostgreSQL database.
No business tables are created or modified.
"""
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.domains.stores_inventory.posting_number_lock import lock_stock_posting_number

URL = os.getenv('STORES_TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not URL, reason='Dedicated PostgreSQL test DB not configured')


def test_accept_and_issue_share_project_posting_lock():
    engine = create_engine(URL, pool_size=3, pool_timeout=5)
    if engine.dialect.name != 'postgresql':
        pytest.skip('PostgreSQL required')
    held = threading.Event()
    release = threading.Event()
    acquired = threading.Event()

    def acceptance():
        with Session(engine) as db:
            lock_stock_posting_number(db, organization_id=7, project_id=12, number=' LOT-POST-1 ')
            held.set()
            assert release.wait(8)
            db.commit()

    def issue():
        assert held.wait(8)
        with Session(engine) as db:
            lock_stock_posting_number(db, organization_id=7, project_id=12, number='lot-post-1')
            acquired.set()
            db.rollback()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(acceptance)
            second = pool.submit(issue)
            assert held.wait(8)
            with engine.connect() as conn:
                candidate = conn.execute(text('SELECT pg_try_advisory_xact_lock(hashtextextended(:name,0))'),
                    {'name': 'stores:stock-posting-number:7:12:lot-post-1'}).scalar_one()
                assert candidate is False
                conn.rollback()
            assert not acquired.is_set()
            release.set()
            first.result(timeout=8)
            second.result(timeout=8)
            assert acquired.is_set()
    finally:
        release.set()
        engine.dispose()
