# Phase 4 — Reservation Action Idempotency Concurrency Gate

## Changes
- `release_reservation` serializes `(organization, project, action_key)` using transaction-scoped PostgreSQL advisory lock **before** selecting/locking the reservation or balance rows. This avoids conflicting release action inserts racing the project-unique `(project_id, action_key)` constraint.
- `reassign_reservation` uses a separate action namespace with the same early-lock approach, preventing concurrently duplicated work-scope reassignment actions.
- Both existing audit tables and the shared stock ledger remain unchanged. The existing database unique constraints remain final correctness boundaries.

## Tests
- Static integration-contract tests confirm the key lock precedes row locks and uniqueness lookups.
- PostgreSQL integration tests exercise the actual locking helper with two sessions against the configured `STORES_TEST_DATABASE_URL` (disposable DB only). They skip when no DB configured; they **do not** prove complete ORM writes or receipt/issue concurrency.

## Remaining blockers
- Run PostgreSQL tests on an isolated Docker Desktop instance and test full ORM acceptance, QA revocation, lot reservation, issue, release, and reassignment transactions under contention.
- Run Alembic migrations, end-to-end authorization, frontend build, and Docker tests.
- External Command Center backend wiring is not part of this archive.
- Do not enable `STORES_LOT_WRITER_CUTOVER`, `STORES_LOT_RESERVATIONS_ENABLED`, or `STORES_ATOMIC_LOT_ISSUE_ENABLED` on production based solely on this checkpoint.
