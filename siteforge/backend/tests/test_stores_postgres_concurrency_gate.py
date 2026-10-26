"""Opt-in REAL PostgreSQL concurrency probes for the Stores lot-writer cutover.

These exercises validate the locking/idempotency protocol on isolated tables.
They do NOT replace end-to-end tests invoking the application ORM services.
Run: STORES_TEST_DATABASE_URL=postgresql+psycopg://... pytest -q tests/test_stores_postgres_concurrency_gate.py
The database account must have CREATE TABLE permissions. No application tables are modified.
"""
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

URL = os.environ.get("STORES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="STORES_TEST_DATABASE_URL is not configured (real PostgreSQL required)")


@pytest.fixture
def pg():
    engine = create_engine(URL, pool_size=6, max_overflow=3, pool_pre_ping=True)
    if engine.dialect.name != "postgresql":
        pytest.skip("Concurrency verification requires PostgreSQL")
    suffix = uuid.uuid4().hex[:12]
    balance = f"stores_gate_balance_{suffix}"
    posting = f"stores_gate_posting_{suffix}"
    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {balance} (lot_id integer PRIMARY KEY, on_hand numeric(14,3) NOT NULL, reserved numeric(14,3) NOT NULL, CHECK (on_hand >= 0), CHECK (reserved >= 0), CHECK (reserved <= on_hand))"))
        conn.execute(text(f"CREATE TABLE {posting} (key text PRIMARY KEY, lot_id integer NOT NULL, qty numeric(14,3) NOT NULL CHECK (qty > 0))"))
        conn.execute(text(f"INSERT INTO {balance} VALUES (1, 10, 0)"))
    try:
        yield engine, balance, posting
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {posting}"))
            conn.execute(text(f"DROP TABLE IF EXISTS {balance}"))
        engine.dispose()


def _post(engine, balance, posting, key, qty, reserve=False):
    """Protocol prototype: lock shared balance, enforce idempotency, then post."""
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL lock_timeout = '5s'"))
        row = conn.execute(text(f"SELECT on_hand, reserved FROM {balance} WHERE lot_id=1 FOR UPDATE")).one()
        prev = conn.execute(text(f"SELECT qty FROM {posting} WHERE key=:key"), {"key": key}).scalar_one_or_none()
        if prev is not None:
            return "retry" if Decimal(prev) == Decimal(qty) else "conflict"
        if qty > (row.on_hand - row.reserved):
            return "insufficient"
        conn.execute(text(f"INSERT INTO {posting} (key,lot_id,qty) VALUES (:key,1,:qty)"), {"key": key, "qty": qty})
        field = "reserved" if reserve else "on_hand"
        op = "+" if reserve else "-"
        conn.execute(text(f"UPDATE {balance} SET {field}={field}{op}:qty WHERE lot_id=1"), {"qty": qty})
        return "posted"


def test_concurrent_issues_cannot_overdraw(pg):
    engine, balance, posting = pg
    barrier = threading.Barrier(2)
    def run(key):
        barrier.wait(timeout=5)
        return _post(engine, balance, posting, key, Decimal("7"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, k) for k in ("issue-a", "issue-b")]
        result = sorted(f.result(timeout=15) for f in futures)
    assert result == ["insufficient", "posted"]
    with engine.connect() as conn:
        assert conn.execute(text(f"SELECT on_hand FROM {balance} WHERE lot_id=1")).scalar_one() == Decimal("3")
        assert conn.execute(text(f"SELECT count(*) FROM {posting}")).scalar_one() == 1


def test_simultaneous_reservations_do_not_overallocate(pg):
    engine, balance, posting = pg
    barrier = threading.Barrier(2)
    def run(key):
        barrier.wait(timeout=5)
        return _post(engine, balance, posting, key, Decimal("6"), reserve=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, k) for k in ("reserve-a", "reserve-b")]
        assert sorted(f.result(timeout=15) for f in futures) == ["insufficient", "posted"]
    with engine.connect() as conn:
        assert conn.execute(text(f"SELECT reserved FROM {balance} WHERE lot_id=1")).scalar_one() == Decimal("6")


def test_idempotency_and_payload_conflict(pg):
    engine, balance, posting = pg
    assert _post(engine, balance, posting, "same-key", Decimal("3")) == "posted"
    assert _post(engine, balance, posting, "same-key", Decimal("3")) == "retry"
    assert _post(engine, balance, posting, "same-key", Decimal("4")) == "conflict"
    with engine.connect() as conn:
        assert conn.execute(text(f"SELECT on_hand FROM {balance} WHERE lot_id=1")).scalar_one() == Decimal("7")
        assert conn.execute(text(f"SELECT count(*) FROM {posting}")).scalar_one() == 1


def test_rollback_cancels_balance_and_posting(pg):
    engine, balance, posting = pg
    with pytest.raises(RuntimeError):
        with engine.begin() as conn:
            conn.execute(text(f"SELECT * FROM {balance} WHERE lot_id=1 FOR UPDATE")).one()
            conn.execute(text(f"INSERT INTO {posting} VALUES ('rollback',1,5)"))
            conn.execute(text(f"UPDATE {balance} SET on_hand=on_hand-5 WHERE lot_id=1"))
            raise RuntimeError("Injected failure between posting and commit")
    with engine.connect() as conn:
        assert conn.execute(text(f"SELECT on_hand FROM {balance} WHERE lot_id=1")).scalar_one() == Decimal("10")
        assert conn.execute(text(f"SELECT count(*) FROM {posting}")).scalar_one() == 0
