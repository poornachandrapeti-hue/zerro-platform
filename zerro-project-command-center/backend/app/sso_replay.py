"""Database-backed single-use SSO exchange; survives worker restarts."""
import hashlib
from sqlalchemy.exc import IntegrityError
from .database import SessionLocal
from .models import ConsumedSSOTicket


def consume_ticket_once(token: str, expires_at: int) -> bool:
    digest = hashlib.sha256(token.encode('utf-8')).hexdigest()
    with SessionLocal() as db:
        try:
            db.add(ConsumedSSOTicket(ticket_hash=digest, expires_at=expires_at))
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
            return False
