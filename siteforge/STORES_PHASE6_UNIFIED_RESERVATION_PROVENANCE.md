# Phase 6 — Unified reservation provenance checkpoint

## Implemented
- Extend the existing `stores_lot_reservations` table to identify **exactly one** source: a GRN receipt lot or a transfer-derived destination lot. Do not create another inventory ledger or reservation table.
- Add database check constraint, nullable legacy receipt-lot identifier, destination-lot foreign key and index.
- Introduce `POST /api/projects/{pid}/stores/material-transfers/destination-lots/reservation-intents` for **PendingActivation** entries. Idempotency keys and destination-project scope are enforced; entries do not reserve physical inventory.
- Keep existing GRN reservations in the `Active` lifecycle. Existing issuing/release paths continue to require `Active` receipt-lot reservations. A transfer-derived intent does not authorize physical issue, does not count toward `StockBalance.reserved`, and cannot be consumed.

## NOT completed / release blockers
- No transfer-lot activation, reserved-stock increment, issue posting, downstream return, or release/reassignment support for transfer provenance.
- Pending intent must be linked to approved authoritative Procurement requirement and Stores request **before future activation**. It is not proof of approved demand.
- No tested PostgreSQL migration or row-concurrency execution. Tests here validate source contracts only. **Do not enable stock writer feature gates.**
- The stored intent is an expression of demand, not an allocation of physical stock and may exceed simultaneously available lot quantities across multiple requests; activation must serialize and enforce aggregate limits.
