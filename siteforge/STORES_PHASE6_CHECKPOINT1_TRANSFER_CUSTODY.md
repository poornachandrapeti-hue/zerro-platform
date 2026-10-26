# Stores Phase 6 — Checkpoint 1: Internal Warehouse Transfer Custody

## Delivered
- `stores_transfers` evidence table with project-unique reference; source/destination existing warehouse IDs; material item and quantity; approval, dispatch, receipt, discrepancy records, version and audit fields.
- Internal API at `/api/projects/{pid}/stores/material-transfers`:
  - POST request; GET latest 300 (internal stock editor only).
  - POST `/{id}/decision` (independent approval or rejection).
  - POST `/{id}/dispatch` (separate operator, sets In Transit).
  - POST `/{id}/receive` (independent receiver, records shortage/damage discrepancy).
- Existing stock ledger remains unchanged; responses explicitly mark inventory_posted=false / physical_stock_readiness=Unverified.
- Audits recorded in the pre-existing application audit infrastructure; scoped to organization and project.
- Unit and source contract checks in `backend/tests/test_stores_phase6_transfer_custody.py`.

## Deferred / limitations
- This is **warehouse-to-warehouse transfer evidence only within the same project**. Cross-project transfers, lot selection, source availability checks, stock postings, in-transit stock accounting, warehouse bin confirmation, custody ownership changes, Partner UI, vendor returns and Command Center are NOT implemented by this checkpoint.
- No physical dispatch or receipt is authorized by these records and no inventory changes are made. Do NOT use these records to assert actual inventory movement or availability.
- Existing `procurement.stock.edit` permissions are reused. Separate Phase 6 role matrix/warehouse-specific permissions are pending.
- Rejected/transit discrepancies have no resolution endpoint yet.
- PostgreSQL transaction/migration test, frontend build, Docker integration and real authorization tests are still deferred/unverified.
- Source-focused 9 test assertions printed as passing, but test runner failed to exit before timeout: do not claim completed clean test execution.

## Next checkpoint
Transfer discrepancy ownership and resolution, custody/bin integration, transfer history and Internal Stores UI; develop gated atomic transfer postings only after necessary PostgreSQL validation.
