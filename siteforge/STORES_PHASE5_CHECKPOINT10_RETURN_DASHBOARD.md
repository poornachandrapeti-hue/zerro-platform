# Phase 5 Checkpoint 10 — Return Exception Workload and Command Center Feed

## Delivered
- GET `/api/projects/{pid}/stores/material-returns/exception-workload`: authorized internal read-only task counts, overdue/blocked metrics, counts by user ID, and unassigned exceptions.
- GET `/api/projects/{pid}/stores/internal-command-center/return-exceptions`: service-key authenticated, organization/project-scoped, read-only return workload feed with `as_of` freshness timestamp.
- Internal Stores return tab: displays assignment/overdue summaries, owner IDs, and explicit unavailable state.
- Stock remains `Unverified`; no new inventory mutations or parallel ledgers.

## Boundaries
- Counts cover up to 500 latest project returns (not all-time totals). No inference of physical readiness or ledger reconciliation.
- The separate Command Center backend must consume the feed server-to-server and verify viewers' live project grants. It is NOT connected/deployed by this archive.
- Service-key must stay server-side; do not expose in browser UI.
- Live PostgreSQL / Docker and frontend TypeScript build not verified. Inventory feature gates remain disabled.

## Verification
- Focused pytest: 8 passed (`test_stores_phase5_return_workload.py` and `test_stores_phase5_return_exception_tasks.py`).
- Python source compilation and ZIP integrity verified.
