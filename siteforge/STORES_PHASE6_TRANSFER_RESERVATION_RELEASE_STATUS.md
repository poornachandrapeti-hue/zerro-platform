# Phase 6 — Transfer reservation release checkpoint

Implemented `POST /api/projects/{pid}/stores/material-transfers/reservation-intents/{intent_id}/release`.

- Default OFF: `STORES_TRANSFER_RESERVATION_RELEASE_ENABLED=false`.
- Works with existing `stores_lot_reservations`, `stores_lot_reservation_actions`, and warehouse stock balances; no new ledger.
- PendingActivation releases change only the intent, not aggregate reserved stock.
- Active releases subtract from aggregate reserved quantity after locks and invariant checks.
- Same-key retries are replayed; conflicting payloads fail closed.
- Authorization and organization/project restrictions enforced.

Physical issue of transfer-derived lots is **not implemented**: the existing issue service still requires GRN receipt-lot IDs. Transfer activation, posting, and physical issuing must remain OFF pending PostgreSQL transaction/concurrency tests and a transfer-aware issue writer. No database integration or frontend build was performed here.

Validation: Python compilation passed; four focused pytest assertions passed, but pytest process did not exit before the command timeout. Archive integrity checked separately.
