# Phase 5 / Checkpoint 6 — Controlled Return Stock Posting

## Delivered
- `POST /api/projects/{pid}/stores/material-returns/{return_id}/post-stock` creates a **Return** posting and posting line in the existing Procurement/Stores stock ledger, and adds original receipt-lot provenance to `stores_outbound_lot_allocations`.
- Only independently QA Accepted returns can post. Source issue, acknowledged handover, lot attribution, outstanding returned quantity, operator separation, project/organization permissions and aggregate stock consistency are checked.
- The Stores return stores the canonical posting ID, and a database uniqueness constraint prevents multiple postings being linked to the same return.
- Both `STORES_ATOMIC_LOT_RETURN_ENABLED=true` and `STORES_LOT_WRITER_CUTOVER=true` are required to reach this code. **Neither should be enabled yet.** Existing legacy writers and application lock order still need real PostgreSQL transaction and deadlock testing.
- Alembic revision: `stores_phase5_return_stock_posting`; no duplicate stock ledger and no posting on custody/QA decisions.

## Not completed / nonproduction
- Actual PostgreSQL concurrent Return vs Issue/QA operations, deadlock ordering, migration execution, frontend build and Docker test are deferred.
- This checkpoint does not provide configurable return-bin placement, split-lot returns, warehouse transfers or auto financial valuation.
- Deployment must keep `STORES_ATOMIC_LOT_RETURN_ENABLED=false` and legacy cutover inactive until comprehensive DB-backed writer reconciliation.
