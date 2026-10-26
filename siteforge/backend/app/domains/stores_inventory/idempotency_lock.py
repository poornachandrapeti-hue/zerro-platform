"""PostgreSQL transaction-scoped serialization for Stores request keys.

Uses the same transaction as the ORM caller, so locks release automatically on
commit or rollback. Does not alter the authoritative stock ledger.
"""
from sqlalchemy import text


def lock_request_key(db, *, organization_id: int, project_id: int, key: str, namespace: str) -> None:
    if not key or not key.strip():
        raise ValueError('Idempotency key is required')
    # hashtextextended provides a stable bigint within PostgreSQL. Hash collisions
    # would only serialize unrelated requests; they cannot bypass row validation.
    lock_name = f'stores:{namespace}:{organization_id}:{project_id}:{key}'
    db.execute(
        text('SELECT pg_advisory_xact_lock(hashtextextended(:lock_name, 0))'),
        {'lock_name': lock_name},
    )
