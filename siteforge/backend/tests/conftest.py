import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:5173"
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db import Base, get_db
from app.main import app
from app.domains.identity_projects.models import (
    Organization,
    Company,
    User,
    Project,
    Membership,
    Role,
)
from app.domains.identity_projects.seed import seed
from app.domains.identity_projects.security import hasher
from app.domains.identity_projects.router import attempts


@pytest.fixture
def env():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def fk_on(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(engine, expire_on_commit=False)
    with maker() as db:
        seed(db)
        a = Organization(name="Alpha")
        b = Organization(name="Beta")
        db.add_all([a, b])
        db.flush()
        ca = Company(organization_id=a.id, name="Alpha Co", name_key="alpha co")
        cb = Company(organization_id=b.id, name="Beta Co", name_key="beta co")
        db.add_all([ca, cb])
        db.flush()
        for email, org, company, admin in [
            ("admin@alpha.test", a.id, ca.id, True),
            ("viewer@alpha.test", a.id, ca.id, False),
            ("admin@beta.test", b.id, cb.id, True),
        ]:
            db.add(
                User(
                    organization_id=org,
                    company_id=company,
                    email=email,
                    name=email.split("@")[0],
                    password_hash=hasher.hash("test-password-123"),
                    organization_admin=admin,
                )
            )
        db.commit()

    def override():
        with maker() as db:
            yield db

    app.dependency_overrides[get_db] = override
    attempts.clear()
    with TestClient(app) as client:
        yield client, maker
    app.dependency_overrides.clear()
    engine.dispose()


def sign_in(client, email="admin@alpha.test"):
    client.headers["Origin"] = "http://localhost:5173"
    response = client.post(
        "/api/auth/login", json={"email": email, "password": "test-password-123"}
    )
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response
