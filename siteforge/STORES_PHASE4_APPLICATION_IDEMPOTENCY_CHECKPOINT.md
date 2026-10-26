# Stores Phase 4: application transaction idempotency checkpoint

## Implemented
- Transaction-scoped PostgreSQL advisory lock around the actual `reserve_lot` service's request-key lookup, scoped by organization, project, and writer namespace.
- Same-key concurrent requests now serialize before checking for an existing reservation; successful retries return existing results, conflicting payloads remain rejected by existing checks.
- Unit tests for scoped bound SQL and ordering; optional real PostgreSQL tests to verify contention and cross-project isolation.

## Safety and limitations
- The caller's single database transaction owns the advisory lock; the helper does not commit.
- No live stock feature gates changed, no migration or ledger changes, and no new stock table.
- Advisory locks are a *supplement* to database uniqueness constraints; full live service-level concurrency, complete writer review, PostgreSQL migrations and QA revocation are not yet verified.
- Database integration tests skip when STORES_TEST_DATABASE_URL is not configured.

## Local verification
`cd siteforge/backend && STORES_TEST_DATABASE_URL='postgresql+psycopg://.../disposable_test_db' python -m pytest -q tests/test_stores_reservation_idempotency_pg.py tests/test_stores_postgres_concurrency_gate.py`

Do not enable STORES_LOT_WRITER_CUTOVER, STORES_ATOMIC_LOT_ISSUE_ENABLED or STORES_LOT_RESERVATIONS_ENABLED until full cutover readiness is verified.
