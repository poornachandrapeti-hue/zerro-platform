"""Single-use SSO handoff regression; no live Postgres needed."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import ConsumedSSOTicket
from app import sso_replay


def test_consumed_ticket_rejected_on_second_use(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'tickets.db'}")
    ConsumedSSOTicket.__table__.create(engine)
    monkeypatch.setattr(sso_replay, "SessionLocal", sessionmaker(bind=engine))
    assert sso_replay.consume_ticket_once("valid-first-ticket", 1000000) is True
    assert sso_replay.consume_ticket_once("valid-first-ticket", 1000000) is False
    assert sso_replay.consume_ticket_once("valid-second-ticket", 1000000) is True
    with sessionmaker(bind=engine)() as db:
        rows = db.query(ConsumedSSOTicket).all()
        assert len(rows) == 2
        assert all(row.ticket_hash != "valid-first-ticket" for row in rows)
