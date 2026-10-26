"""Project-wide posting number serialization for opt-in Stores lot writers.

Acquire before lot/balance row locks. This aligns with the existing
StockPosting(project_id, number_key) unique constraint, which remains the
ultimate correctness boundary. The caller owns transaction commit/rollback.
"""
from fastapi import HTTPException
from app.domains.supply_chain.service import _key
from .idempotency_lock import lock_request_key


def lock_stock_posting_number(db, *, organization_id: int, project_id: int, number: str) -> None:
    normalized = _key(number)
    if not normalized:
        raise HTTPException(422, 'Posting number is required')
    # The stock posting uniqueness constraint is scoped by project, not writer
    # type; use the SAME namespace for acceptance and issue.
    lock_request_key(db, organization_id=organization_id, project_id=project_id,
                     key=normalized, namespace='stock-posting-number')
