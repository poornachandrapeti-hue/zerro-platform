# Stores Phase 4 — Complete Known Legacy Stock Service Writer Guard

## Implemented
- Extended `STORES_LOT_WRITER_CUTOVER` gating to `return_stock` and `cancel_posting` in `backend/app/domains/supply_chain/stock.py`.
- Existing `accept_receipt`, `reserve_stock`, and `issue_stock` remain gated.
- Cutover checks occur **before** authorization, reads, posting or balance mutations; cancellation of any posted Accept/Reservation/Issue/Return is blocked in lot-writer mode.
- Added AST-based regression tests proving each of the five known stock-service writers calls the guard first.
- No schema or transaction data changes. No feature gates enabled.

## Not yet verified
- Direct SQL/ORM mutations outside this service or outside inspected application paths, deployed third-party integrations and scheduled tasks.
- Live PostgreSQL migration/concurrency/rollback, end-to-end Docker deployment, frontend build, separate Command Center runtime.
- New lot-aware return/transfer/adjustment/cancellation flows have **not** been implemented; operations are blocked in cutover mode until replacement flows exist.

## Safety
Keep `STORES_LOT_WRITER_CUTOVER=false`, `STORES_LOT_RESERVATIONS_ENABLED=false`, and `STORES_ATOMIC_LOT_ISSUE_ENABLED=false` in development until a documented cutover rehearsal and database-backed concurrency testing.
