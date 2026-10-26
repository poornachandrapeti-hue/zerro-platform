# Phase 7 — Checkpoint 4: Variance reconciliation and independent verification

## Delivered
- `GET /api/projects/{pid}/stores/cycle-counts/{count_id}/variance-reconciliation`: read-only, project-and-organization-scoped comparison context.
- Surfaces counted receipt-lot observations separately from current warehouse/item `stock_balances`, with an observation timestamp and explicit variance blockers.
- Exposes whether a count was independently verified, without equating that review to reconciliation or stock-adjustment authorization.
- No new physical inventory ledger, posting, mutation or migration.

## Important constraints
The current cycle-count count-sheet records historical receipt-lot quantity, not a contemporaneous per-lot book stock snapshot. The stock ledger aggregates by warehouse and item; transfer-derived lots may also exist. Therefore a valid accounting variance cannot be derived from these fields. The API intentionally reports `reconciliation_status=Blocked`, `variance_verified=false`, and `authorized_stock_adjustment=false`, including on verified counts. The historical observed-minus-receipt figure is **not** a book variance. These blockers must be solved before inventory adjustments.

## Deferred
- Point-in-time per-lot ledger reconciliation and all-lot count completeness.
- Transfer-derived lot cycle counts; live PostgreSQL concurrency and Docker tests.
- Adjustment approval and ledger posting (future Phase 7 checkpoint).
