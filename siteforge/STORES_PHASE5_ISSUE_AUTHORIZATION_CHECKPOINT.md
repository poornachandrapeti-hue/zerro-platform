# Phase 5 / Checkpoint 1 — Canonical-demand-bound Material Issue

## Delivered
- Extended existing feature-gated `POST /api/projects/{pid}/stores/receipt-lots/issue-atomically` instead of creating another inventory ledger.
- `reservation_id` is now mandatory in the request model and at service level. Ad hoc direct lot issues without an approved reservation are rejected.
- Before posting or reducing inventory, verify reservation belongs to an **Approved** Stores material issue request and remains tied to its canonical **Approved** Procurement requirement line.
- Verify requested item, base unit, WBS/work-package scope, reserved quantity, and, for partner requests, active contractor work-package ownership, release and requirement linkage.
- Reuse existing QA, expiration, quantity, posted-lot coverage, stock-balance, idempotent posting-number and transaction checks.
- Outbound provenance reason includes the issue request ID and reservation ID; response returns the linked request, canonical requirement line and work package IDs.
- No new physical ledger, material demand record or DB migration.

## Security / rollout status
- `STORES_ATOMIC_LOT_ISSUE_ENABLED=false`, `STORES_LOT_RESERVATIONS_ENABLED=false` and `STORES_LOT_WRITER_CUTOVER=false` by default. **Do not enable them** before completing PostgreSQL concurrency, worker, migrations and legacy-writer cutover tests.
- Existing `receipt_access(edit=True)` still governs internal issue privilege; partner personnel do not obtain direct physical stock-issue authorization from this change.
- Existing reservation lookup uses row locking. Approved request/requirement check is a read; database-backed concurrency with concurrent requirement withdrawal is **not verified**. Do not call this production-ready.
- Contractor receipt/acknowledgment, partial delivery evidence, acceptance by storekeeper, site returns, auto-issue from allocation, Command Center verified KPIs: **future Phase 5 checkpoints**.

## Verification completed
- `python -m pytest -q tests/test_stores*`: **195 passed, 15 skipped** (PostgreSQL-dependent cases skipped, not waived).
- Python source compilation and ZIP integrity checks were also performed.

## Next checkpoint
Implement Stores-issued material dispatch/hand-over register with stock posting reference, contractor acknowledgment lifecycle, maker/checker RBAC, immutable evidence and discrepancy recording using the existing ledger. Do not create a duplicate stock ledger or a separate procurement demand.
