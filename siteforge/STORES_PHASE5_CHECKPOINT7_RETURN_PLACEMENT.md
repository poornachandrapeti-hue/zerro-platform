# Phase 5 Checkpoint 7 — Return Bin Placement and Custody Reconciliation

## Delivered
- Return custody placement API `POST /api/projects/{pid}/stores/material-returns/{return_id}/placement`.
- Requires active `Bin` belonging to the original posted issue warehouse, organization, and project.
- Independent Stores operator, current accepted QA decision, optimistic version, evidence, audit, row locks.
- Read-only `GET /api/projects/{pid}/stores/material-returns/reconciliation` reports pending placement, awaiting posting, and posted-reference presence; never claims stock verification.
- Existing gated return posting now requires current audited bin placement. This adds **no** bin inventory ledger; location is custody metadata tied to existing return.
- Internal Stores returns screen includes placement, posting reference/evidence, and reconciliation status.
- Migration `stores_phase5_return_bin_placement` adding placement location/evidence/actor columns.

## Explicit limits
- Lot-aware return posting remains off by default (`STORES_ATOMIC_LOT_RETURN_ENABLED=false`, `STORES_LOT_WRITER_CUTOVER=false`).
- Bin placement does NOT increase stock or prove bin-level quantity balances.
- PostgreSQL concurrency testing, migration execution, frontend build, Docker integration deferred.
- Original-warehouse is checked server-side; UI may list bins in other warehouses, which the server rejects.
- Reconciliation is advisory and does not perform independent physical cycle counts.

## Validation
- 4 focused contract tests passed; Python compilation passed; archive integrity checked.
