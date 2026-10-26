# Phase 7 Checkpoint 5 — Adjustment review authorization (source-level)

- Added count-linked stock adjustment requests and independent reviewer decisions.
- Creation requires a verified physical count, but **this is not a verified book variance**.
- Decision options: RecordReview (blocked), RequestRecount, Reject. There is no approval/posting decision.
- No stock movement, no second ledger and no adjustment of StockBalance.
- A future accounting-grade adjustment workflow requires lot-level point-in-time ledger snapshot (including transfer-derived lots), movement cutoff, variance adjudication, dual authorization, idempotent posting, rollback and real PostgreSQL concurrency tests.
- Database validation, migrations against a running instance, frontend build and Docker integration remain deferred.
