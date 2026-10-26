# Phase 6 — Transfer-derived lot material issue

## Implemented
- Feature-gated POST `/api/projects/{pid}/stores/material-transfers/destination-lots/{lot_id}/issue`.
- Same-project-only transfer-derived lot issues, using existing `stock_postings`, `stock_posting_lines`, and `stock_balances`; no second physical ledger.
- New audited outbound transfer-lot provenance `stores_transfer_issue_allocations` with Alembic migration.
- Validated active transfer-lot reservation, canonical approved Procurement and Stores material request, work package, current destination QA status, transfer posting-pair reconciliation, quality holds, warehouse provenance reconciliation, transfer-lot quantity ceiling, and aggregate reservation invariants.
- A single database transaction updates posting, outbound allocation, reservation balance, and on-hand/reserved aggregate.
- Concurrent posting number protection reuses existing transaction-scoped advisory locks.

## Safety limits
- All transaction gates remain default OFF. `STORES_TRANSFER_LOT_ISSUE_ENABLED=true`, `STORES_ATOMIC_LOT_ISSUE_ENABLED=true`, and `STORES_LOT_WRITER_CUTOVER=true` are all needed for invocation. **Do not enable these flags in development/production** without PostgreSQL migration, concurrency, reversals, legacy-writer and integration validation.
- Transfer-derived issues are not yet connected to the Phase 5 handover, contractor acknowledgment, returns, and material usage chain. These downstream flows need provenance-aware extensions.
- Mixed GRN/transfer lot reconciliation remains an accounting diagnostic, not a production availability certification.
- Inter-project transfer-derived issue and transfer-issued stock return are not supported.
- No PostgreSQL transaction tests were executed in this environment.

## Verification
- 9 focused pytest cases passed.
- Python compilation passed.
- Alembic revision metadata has a single head.
