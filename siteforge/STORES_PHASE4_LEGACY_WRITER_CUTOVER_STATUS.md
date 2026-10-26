# Stores Phase 4 — Legacy Stock Writer Cutover Gate

## Scope
This checkpoint addresses a release safety gap in the ZerroBuild Stores/Procurement integration: legacy item-level writers can modify balances without lot provenance while new lot-aware writers rely on lot-specific attribution. Those paths must not run concurrently.

## Implementation
- `supply_chain/stock.py`: accept_receipt, reserve_stock and issue_stock now check `STORES_LOT_WRITER_CUTOVER`. With this flag set to `true`, they refuse mutations with HTTP 503.
- `stores_inventory/atomic_lot_acceptance.py`, `atomic_lot_issue.py`, `lot_reservations.py`: reject new lot writers unless `STORES_LOT_WRITER_CUTOVER=true`.
- Existing `STORES_ATOMIC_LOT_ISSUE_ENABLED` and `STORES_LOT_RESERVATIONS_ENABLED` gates are NOT switched on and remain mandatory.
- No migrations or stock ledger schema changes in this checkpoint.

## Deployment modes
| Mode | STORES_LOT_WRITER_CUTOVER | STORES_ATOMIC_LOT_ISSUE_ENABLED | STORES_LOT_RESERVATIONS_ENABLED | Meaning |
|---|---|---|---|---|
| Default/development | false | false | false | Legacy entry points remain as before; new reservations/issues disabled |
| Block legacy (maintenance) | true | false | false | Legacy writer entry points blocked; lot issue/reserve disabled; atomic lot acceptance is callable but must not be used until transaction testing and operational authorization are complete |
| Future lot cutover | true | true | true | **DO NOT USE YET** — requires verified migration, coverage of every remaining balance writer, race tests, rollback and authorization validation |

This guard is a defense-in-depth safeguard, **not** a completed global inventory writer cutover: other mutation paths (including transfers, returns, adjustments, reversals or direct database writes) need review. It is not a production activation recommendation.

## Checks completed
- Python compilation of changed modules
- 15 regression tests (including 8 new cutover-focused tests) passed; an additional 22 focused tests passed before new tests were added
- Alembic revision metadata audit: 120 revisions, zero duplicate IDs, zero missing parents, one head
- ZIP archive CRC check

## Pending gates
- Live PostgreSQL migration and rollback test (DATABASE_URL not provided)
- Verify all legacy stock writers, not only accept/reserve/issue, use an equivalent guard
- Transaction isolation/concurrency/idempotency tests against real PostgreSQL
- Frontend TypeScript build and Docker end-to-end runs
- Partner Portal and Command Center full viewer authorization checks in deployed services
- Do not enable live lot issuing until those gates pass
