# Phase 5 Checkpoint 20 — Construction Manager Material Dashboard

## Implemented
- Dedicated **Material balance** tab in existing Construction module, using existing component styles.
- Calls project-scoped, `construction.view`-protected GET `/api/projects/{pid}/stores/phase5/construction-manager-material-balance` (Checkpoint 19 source API).
- Optional positive integer work-package filter; request isolation on project change; refresh, empty/loading/error states.
- Line-level issue, posted return, outstanding, pending custody return, QA pending usage, QA verified consumption and QA verified installation, unallocated outstanding, and unit.
- Work-package selection displays a scoped handover count.
- Explicit `Unverified` inventory label; source coverage and as-of; no misleading aggregation of dissimilar units.
- No posting or financial/progress side effects; no partner scope expansion.

## Deferred release checks and limitations
- No installed frontend dependencies in this archive/runtime; full TypeScript/Vite build NOT executed.
- PostgreSQL and Docker integration tests intentionally deferred at user's request.
- This endpoint reflects only request-linked handovers / mapped source records, not total physical available stock.
- Construction-manager cross-project permissions still must be integration tested with deployed roles.
- Separate Command Center runtime remains disconnected.
- `STORES_ATOMIC_LOT_RETURN_ENABLED` and stock writer cutover must remain disabled until operational validation.

## Phase 5 next milestone
Checkpoint 21: reconcile functional coverage with approved requirements, complete remaining cross-module integration components, deliver closure report with deferred verification clearly identified.
