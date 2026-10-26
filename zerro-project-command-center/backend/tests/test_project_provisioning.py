from datetime import date
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.database import Base
from app.models import Project, Discipline
from app.project_provisioning import provision_authorized_projects


def test_provision_only_allowed_and_idempotent(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path}/cc.db')
    Base.metadata.create_all(engine)
    authority = {
        'P-1': {'name':'Steel Plant', 'planned_start':'2026-01-01', 'planned_finish':'2026-12-31', 'status':'Active', 'currency':'INR'},
        'P-2': {'name':'Private Project', 'planned_start':'2026-01-01', 'planned_finish':'2026-12-31'},
    }
    with Session(engine) as db:
        first = provision_authorized_projects(db, authority, {'P-1'}, {}, {'P-1': {'CIVIL', 'MECHANICAL'}})
        second = provision_authorized_projects(db, authority, {'P-1'}, {}, {'P-1': {'CIVIL'}})
        rows = db.scalars(select(Project)).all()
        assert first['created'] == 1 and second['created'] == 0
        assert len(rows) == 1 and rows[0].code == 'P-1'
        assert rows[0].approved_budget == 0
        assert {d.code for d in rows[0].disciplines} == {'CIVIL', 'MECHANICAL'}
        assert all(d.actual_progress == 0 and d.weight == 0 for d in rows[0].disciplines)
    engine.dispose()


def test_existing_project_header_resyncs_from_source(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path}/cc.db')
    Base.metadata.create_all(engine)
    source = {'name':'Steel Plant', 'planned_start':'2026-01-01', 'planned_finish':'2026-12-31', 'status':'Draft', 'currency':'INR'}
    with Session(engine) as db:
        provision_authorized_projects(db, {'P-1': source}, {'P-1'}, {}, {'P-1': {'CIVIL'}})
        updated = {**source, 'name':'Steel Plant II', 'status':'Active', 'client':'Owner Co',
                   'contract_value':'500000000.00', 'planned_finish':'2027-03-31'}
        result = provision_authorized_projects(db, {'P-1': updated}, {'P-1'}, {}, {'P-1': {'CIVIL'}})
        project = db.scalars(select(Project)).one()
        assert result['synced'] == 1
        assert (project.name, project.status, project.client) == ('Steel Plant II', 'Active', 'Owner Co')
        assert project.approved_budget == 500000000
        assert project.planned_finish == project.forecast_finish == date(2027, 3, 31)
        provision_authorized_projects(db, {'P-1': {**updated, 'planned_start':None}}, {'P-1'}, {})
        assert db.scalars(select(Project)).one().start_date == date(2026, 1, 1)
    engine.dispose()


def test_missing_dates_skip_without_fabrication(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path}/cc.db')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        result = provision_authorized_projects(db, {'P-3': {'name':'Undated','planned_start':None,'planned_finish':None}}, {'P-3'}, {})
        assert result['skipped_missing_dates'] == 1
        assert not db.scalars(select(Project)).all()
    engine.dispose()
