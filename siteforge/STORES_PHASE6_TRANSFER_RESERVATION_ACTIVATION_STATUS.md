# Phase 6 — transfer reservation activation (source checkpoint)

## Added
- `backend/app/domains/stores_inventory/transfer_reservation_activation.py` is mounted in `app/main.py`.
- `POST /api/projects/{pid}/stores/material-transfers/reservation-intents/{intent_id}/activate`
- A two-flag, default-off gate: both `STORES_LOT_WRITER_CUTOVER=true` and `STORES_TRANSFER_RESERVATION_ACTIVATION_ENABLED=true` are required.
- The implementation validates same-project destination lot, independent QA acceptance, paired stock posting reconciliation, original Procurement demand and approved Stores request, material/unit, demand allocation limits, lot-specific held quantity, warehouse balance and mixed provenance reconciliation.
- Uses the **existing** `stores_lot_reservations` and `stock_balances` tables (no duplicate inventory ledger). Sets an intent Active and increments aggregate reserved in one transaction, without stock issue.

## Critical safety status
- **Do not turn the activation flag on.** The downstream physical issue and reservation release writers do not yet support transfer-derived lot references; activation without those paths would strand reservations. This checkpoint is code only, not approved for live operations.
- Tests cover numerical boundaries and default-off behavior only, not PostgreSQL isolation or actual service transactions.
- Deferred prerequisites: implement transfer-derived lot issue/release path, concurrency tests against migrated PostgreSQL, safe multi-writer migration, reconciliation checks, complete cross-project treatment and live QA revocation interactions.

## Tests executed
- `pytest -q tests/test_stores_phase6_transfer_reservation_activation.py -p no:cacheprovider`: 8 passed.
- `python -m py_compile`: passed for the new module.
- PostgreSQL and Docker end-to-end tests: deferred.
