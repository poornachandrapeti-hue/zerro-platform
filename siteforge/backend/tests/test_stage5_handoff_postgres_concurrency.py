"""Opt-in PostgreSQL test of the actual Quality-to-Stores handoff function.

Runs against a disposable PostgreSQL database via STORES_TEST_DATABASE_URL.
Creates a uniquely named schema, clones only required structures, and removes
that schema after the test. It NEVER changes public application tables.

The actual handoff function, SQLAlchemy models, SQL statements, commit logic,
and PostgreSQL locks run. Authorization and Quality disposition totals are
stubbed to isolate the handoff's concurrent transaction behavior; they are
covered by separate HTTP tests.
"""
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

URL = os.getenv("STORES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Requires disposable PostgreSQL STORES_TEST_DATABASE_URL")


@pytest.fixture
def handoff_pg(monkeypatch):
    from app.domains.stores_inventory import router as stores
    from app.domains.quality import material as quality_material
    from app.domains.quality.models import MaterialInspection
    from app.domains.supply_chain.models import GoodsReceipt, GoodsReceiptLine
    from app.domains.stores_inventory.models import StoresInspectionCase, StoresInspectionDecision

    admin = create_engine(URL, pool_pre_ping=True)
    if admin.dialect.name != "postgresql":
        admin.dispose()
        pytest.skip("Real PostgreSQL required")

    database = None
    schema = "stage5_qa_handoff_" + uuid.uuid4().hex[:12]
    engine = None
    try:
        with admin.connect() as conn:
            database = conn.execute(text("SELECT current_database()" )).scalar_one()
        if database != "siteforge_test":
            pytest.fail(f"Refusing to run outside siteforge_test (got {database!r})")

        tables = [GoodsReceipt.__table__.name, GoodsReceiptLine.__table__.name,
                  StoresInspectionCase.__table__.name, StoresInspectionDecision.__table__.name,
                  MaterialInspection.__table__.name]
        if len(set(tables)) != len(tables):
            pytest.fail("Unexpected table-name collision")
        with admin.begin() as conn:
            for table in tables:
                exists = conn.execute(text("SELECT to_regclass(:tablename)"),
                                      {"tablename": f"public.{table}"}).scalar_one()
                if exists is None:
                    pytest.skip(f"Missing migrated table public.{table}")
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            for table in tables:
                # No public fallback for this isolated test's mapped tables.
                # LIKE copies the columns and check/not-null constraints, not
                # foreign keys, public records, triggers or application data.
                conn.execute(text(f'CREATE TABLE "{schema}"."{table}" '
                                  f'(LIKE public."{table}" INCLUDING CONSTRAINTS)'))
                conn.execute(text(f'CREATE SEQUENCE "{schema}"."{table}_local_id_seq"'))
                conn.execute(text(f'ALTER TABLE "{schema}"."{table}" '
                                  f'ALTER COLUMN id SET DEFAULT '
                                  f'nextval(\'"{schema}"."{table}_local_id_seq"\')'))
                # LIKE does not copy unique indexes; make concurrent duplicate
                # writes observable and rejectable like production.
                if table == StoresInspectionCase.__table__.name:
                    conn.execute(text(f'CREATE UNIQUE INDEX "stage5_unique_grn_line" '
                                      f'ON "{schema}"."{table}" (goods_receipt_line_id)'))
                elif table == StoresInspectionDecision.__table__.name:
                    conn.execute(text(f'CREATE UNIQUE INDEX "stage5_unique_decision_key" '
                                      f'ON "{schema}"."{table}" (case_id,idempotency_key)'))

        engine = create_engine(URL, pool_size=4, max_overflow=0, pool_pre_ping=True,
                               connect_args={"options": f"-csearch_path={schema}"})
        # Fail closed if a connection unexpectedly reads the public schema.
        with engine.connect() as conn:
            path = conn.execute(text("SHOW search_path")).scalar_one()
            assert path == schema, path

        # Seed only the two records used by the actual handoff ORM query.
        # The clone deliberately lacks FK constraints, so fixed test-only IDs
        # are safe and cannot reference live/public records.
        with engine.begin() as conn:
            conn.execute(text(f'''INSERT INTO "{schema}"."{GoodsReceipt.__table__.name}"
                (id,organization_id,project_id,purchase_order_id,number,number_key,
                 receipt_date,delivery_note,status,cancellation_reason,version,
                 created_by,created_at,modified_at)
                VALUES (90001,901,902,903,'STAGE5-TEST','stage5-test',CURRENT_DATE,
                        '','Posted','',1,904,now(),now())'''))
            conn.execute(text(f'''INSERT INTO "{schema}"."{GoodsReceiptLine.__table__.name}"
                (id,goods_receipt_id,purchase_order_line_id,quantity)
                VALUES (90002,90001,905,10)'''))

        monkeypatch.setattr(stores, "qa_access", lambda db, user, pid, edit=False: SimpleNamespace(id=pid))
        monkeypatch.setattr(stores, "permitted", lambda *args, **kwargs: None)
        monkeypatch.setattr(stores, "audit", lambda *args, **kwargs: None)
        monkeypatch.setattr(quality_material, "_totals", lambda db, line_id: {
            "accepted": Decimal("7"), "rejected": Decimal("3"), "quarantined": Decimal("0")})
        yield engine, stores, StoresInspectionCase, StoresInspectionDecision
    finally:
        if engine is not None:
            engine.dispose()
        try:
            with admin.begin() as conn:
                # Only drop our generated test schema, never 'public'.
                if database == "siteforge_test":
                    conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        finally:
            admin.dispose()


def test_two_simultaneous_real_handoffs_only_authorize_once(handoff_pg):
    engine, stores, Case, Decision = handoff_pg
    start = threading.Barrier(2)
    actor = SimpleNamespace(id=904, organization_id=901, organization_admin=True)

    def call():
        start.wait(timeout=10)
        try:
            with Session(engine, expire_on_commit=False) as db:
                db.execute(text("SET LOCAL lock_timeout = '12s'"))
                return stores.reconcile_approved_quality_case(
                    pid=902, receipt_line_id=90002, expected_version=1, u=actor, db=db)
        except HTTPException as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = [pool.submit(call) for _ in range(2)]
        results = [f.result(timeout=25) for f in tasks]

    assert len([x for x in results if isinstance(x, dict)]) == 1, results
    assert [x for x in results if isinstance(x, int)] == [409], results

    with Session(engine) as db:
        cases = db.query(Case).filter_by(goods_receipt_line_id=90002).all()
        assert len(cases) == 1
        case = cases[0]
        assert case.version == 2
        assert case.status == "Disposition Recorded"
        assert (case.pending_qty, case.accepted_qty, case.rejected_qty,
                case.quarantined_qty) == (Decimal("0"), Decimal("7"), Decimal("3"), Decimal("0"))
        decisions = db.query(Decision).filter_by(case_id=case.id).all()
        assert len(decisions) == 2
        assert {(x.disposition, x.quantity) for x in decisions} == {
            ("Accepted", Decimal("7")), ("Rejected", Decimal("3"))}
    winner = next(x for x in results if isinstance(x, dict))
    assert winner["stock_posted"] is False
    assert winner["lot_release_enabled"] is False
