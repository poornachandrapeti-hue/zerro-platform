import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
schema = os.environ.get("COMMAND_CENTER_DB_SCHEMA", "").strip()
if schema:
    if schema != "command_center":
        raise ValueError("Unsupported Command Center schema")
    if not settings.database_url.startswith("postgresql"):
        raise ValueError("Schema isolation requires PostgreSQL")
    connect_args = {**connect_args, "options": "-csearch_path=command_center"}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

