# Stores Phase 4 — Acceptance balance transaction gate

## Change
The actual `atomic_lot_acceptance.accept_lot` service now rejects an inconsistent aggregate `StockBalance` row while that row is locked and **before** creating any stock posting. Rejected conditions: negative on-hand, negative reserved, reserved greater than on-hand, non-finite balances.

This is complementary to the existing issue-side balance checks. It does not introduce any additional physical inventory ledger or authorize live issuing.

## Checks run in this environment
`python -m pytest -q tests/test_stores_acceptance_balance_safety.py tests/test_stores_issue_balance_invariants.py tests/test_stores_posting_number_lock.py tests/test_stores_reservation_idempotency_unit.py`: 21 passed.

## Still pending (release blockers)
- Execute PostgreSQL integration tests against an isolated, fully migrated database; the database is not available here.
- Execute live ORM service concurrency tests: acceptance vs acceptance, issue vs issue, QA revocation, reservation release, and rollbacks.
- Verify every stock-mutating legacy path and migrations on target PostgreSQL.
- Verify downstream Procurement, Planning, QA/QC, Partner Portal, and Command Center runtime integration.
- Keep `STORES_ATOMIC_LOT_ISSUE_ENABLED=false`, `STORES_LOT_WRITER_CUTOVER=false` until cutover clearance.
