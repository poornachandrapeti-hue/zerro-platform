# Phase 4 — Cross-Writer Posting Number Concurrency

## Implemented

- Added `posting_number_lock.py`: PostgreSQL transaction-scoped advisory lock on the *same normalized posting number key* used by the existing `StockPosting(project_id, number_key)` unique constraint.
- Applied the lock before lot/balance locking in the actual `accept_lot` and `issue_lot` application functions, so concurrent acceptance and issue requests cannot pass duplicate-number prechecks simultaneously.
- The lock is per organization/project/normalized number and shared by **both** lot writer types. A duplicate number still returns the existing stock service's HTTP 409 after the earlier transaction commits. The existing unique constraint remains the final database safeguard.
- Added unit and optional live PostgreSQL concurrency tests. No ledger tables, migrations, posting structure, cutover defaults, or live stock gates changed.

## Verification and limitations

Run from `siteforge/backend`:

```bash
python -m pytest -q tests/test_stores_posting_number_lock.py tests/test_stores_posting_number_lock_pg.py tests/test_stores_reservation_idempotency_unit.py tests/test_stores_writer_cutover_gate.py
```

A dedicated disposable PostgreSQL test database is required for the `_pg.py` test via `STORES_TEST_DATABASE_URL`. Without it, that test is **skipped**, not passed. These tests do not replace application-level PostgreSQL ORM fixtures, quality-revocation race tests, actual authenticated API tests, or full migration/Docker validation. **Do not enable** `STORES_LOT_WRITER_CUTOVER`, `STORES_ATOMIC_LOT_ISSUE_ENABLED`, or `STORES_LOT_RESERVATIONS_ENABLED` as a consequence of this checkpoint.

Only the two opt-in lot writers participate in this new posting-number advisory lock. Other writers depend on existing stock uniqueness and cutover protections and must be audited before a broader switch.
