# Phase 5 / Checkpoint 15 — Material-specific Construction Usage

## Delivered
- `POST /api/projects/{pid}/stores/phase5/material-usages`: Construction users submit evidence for a specific *posted* issue/handover and work package. Only `Consumed` and `Installed` usage types are accepted; material item, unit, work package and source issue come from the canonical Stores request/posting, not client-supplied IDs.
- `POST /api/projects/{pid}/stores/phase5/material-usages/{usage_id}/verify`: independent authorized QA reviewer verifies or rejects; row locks, optimistic versions, audit events, and quantities bounded by posted issues minus posted returns.
- `GET /api/projects/{pid}/stores/phase5/material-usages`: limited read-only evidence list.
- Separate **evidence** table, never a second physical ledger. No automatic inventory posting, progress earning, certified billing or installation certification beyond explicitly QA-verified material evidence.
- Submission also considers pending QA quantities to avoid evidence over-allocation; approved verification considers already verified usage.
- Alembic revision `a5f15015c001`, chained to the existing single migration head.

## Known limitations and deferred validation
- No dedicated frontend form yet. API workflows implemented; UI is future work.
- This is *source-level* development. Live PostgreSQL migrations, concurrency, FK and Docker integrations have NOT run; they must run before enabling any physical posting.
- Source handover must already be acknowledged/resolved. Previously issued stock without request-linked handover is out of scope.
- Reconciliation with later ledger-posted returns should block conflicting returns or demand investigation; this checkpoint validates at material usage submit/verify only.
- Non-admin list visibility currently shows only user-submitted evidence. Broader approved QA reviewer visibility needs separate scoped read authorization.
- `STORES_LOT_WRITER_CUTOVER` and physical stock mutation gates remain disabled.
