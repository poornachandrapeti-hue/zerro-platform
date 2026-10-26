"""Opt-in PostgreSQL tests using the REAL mapped Task/StoresInspectionCase and route functions.

Run only against a disposable, fully migrated test database:
 STORES_TEST_DATABASE_URL=postgresql+psycopg://... pytest -q tests/test_stores_construction_qa_postgres_application.py

Creates isolated schema tables cloned from the migration-created application tables.
Never connects to a production database. Authorization is stubbed here to focus on row-lock/version
behavior; real RBAC integration must be separately exercised in full HTTP tests.
"""
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

URL = os.environ.get('STORES_TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not URL, reason='STORES_TEST_DATABASE_URL required for real PostgreSQL application tests')


@pytest.fixture
def environment(monkeypatch):
    from app.domains.stores_inventory import qa_issued_impact as api
    from app.domains.identity_projects import security
    from app.domains.supply_chain import service as supply_service

    admin = create_engine(URL, pool_pre_ping=True)
    if admin.dialect.name != 'postgresql':
        pytest.skip('PostgreSQL required')
    schema = 'stores_app_gate_' + uuid.uuid4().hex[:12]
    with admin.begin() as c:
        # Requires the actual application migrations to have been applied first.
        for table in ('stores_inspection_cases', 'tasks'):
            if c.execute(text('SELECT to_regclass(:name)'), {'name': f'public.{table}'}).scalar() is None:
                pytest.skip(f'Migrated public.{table} table required')
        c.execute(text(f'CREATE SCHEMA {schema}'))
        for table in ('stores_inspection_cases', 'tasks'):
            c.execute(text(f'CREATE TABLE {schema}.{table} (LIKE public.{table} INCLUDING DEFAULTS INCLUDING CONSTRAINTS)'))
    engine = create_engine(URL, pool_size=5, max_overflow=2, pool_pre_ping=True,
                           connect_args={'options': f'-csearch_path={schema},public'})
    monkeypatch.setattr(api, 'qa_access', lambda db, user, pid, edit=False: SimpleNamespace(id=pid))
    monkeypatch.setattr(supply_service, '_project', lambda db, user, pid, action=None: SimpleNamespace(id=pid))
    monkeypatch.setattr(security, 'permitted', lambda *args, **kwargs: True)
    try:
        yield engine, api
    finally:
        engine.dispose()
        with admin.begin() as c:
            c.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()


def _seed(engine):
    # Seed via real SQLAlchemy models and mapped fields, in dedicated test-only schema.
    from app.domains.stores_inventory.models import StoresInspectionCase
    from app.domains.coordination.models import Task
    with Session(engine, expire_on_commit=False) as s:
        case = StoresInspectionCase(id=99101, organization_id=991, project_id=992,
                                    goods_receipt_line_id=993, pending_qty=0, accepted_qty=1, rejected_qty=0,
                                    quarantined_qty=0, created_by=995, status='Quality Revoked', version=1)
        task = Task(id=99102, organization_id=991, project_id=992,
                    source_type='stores.qa_revocation.construction_review', source_id=99101,
                    title='QA test impact review', owner_id=994, creator_id=995,
                    status='Open', version=1, evidence='')
        s.add_all([case, task])
        s.commit()


def _call(engine, api, operation, actor_id, version, barrier=None):
    if barrier is not None:
        barrier.wait(timeout=10)
    try:
        with Session(engine, expire_on_commit=False) as s:
            fn = api.acknowledge_construction_impact if operation == 'ack' else api.verify_construction_impact
            return fn(pid=992, case_id=99101, task_id=99102,
                      data=api.ConstructionImpactReviewIn(task_version=version,
                          evidence='Documented field review evidence for testing'),
                      u=SimpleNamespace(id=actor_id, organization_id=991), db=s)
    except HTTPException as exc:
        return exc.status_code


def test_simultaneous_acknowledgment_one_wins_and_qa_requires_next_version(environment):
    engine, api = environment
    _seed(engine)
    barrier = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_call, engine, api, 'ack', 994, 1, barrier) for _ in range(2)]
        results = [f.result(timeout=20) for f in futures]
    assert sorted(('ok' if isinstance(r, dict) else r for r in results), key=str) == [409, 'ok']
    assert _call(engine, api, 'verify', 995, 1) == 409
    done = _call(engine, api, 'verify', 995, 2)
    assert done['status'] == 'Completed' and done['qa_verified'] is True
    assert done['impact_scope_verified'] is False


def test_owner_cannot_self_verify_and_other_user_cannot_acknowledge(environment):
    engine, api = environment
    _seed(engine)
    assert _call(engine, api, 'ack', 995, 1) == 403
    assert _call(engine, api, 'verify', 995, 1) == 409
    assert isinstance(_call(engine, api, 'ack', 994, 1), dict)
    assert _call(engine, api, 'verify', 994, 2) == 403
    assert _call(engine, api, 'verify', 995, 2)['status'] == 'Completed'


def test_simultaneous_qa_verification_one_wins(environment):
    engine, api = environment
    _seed(engine)
    assert isinstance(_call(engine, api, 'ack', 994, 1), dict)
    barrier = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_call, engine, api, 'verify', 995, 2, barrier) for _ in range(2)]
        results = [f.result(timeout=20) for f in futures]
    assert sorted(('ok' if isinstance(r, dict) else r for r in results), key=str) == [409, 'ok']
    from app.domains.coordination.models import Task
    with Session(engine) as s:
        task = s.get(Task, 99102)
        assert task.status == 'Completed'
        assert task.version == 3
        assert task.evidence.count('QA verification by user ') == 1
