# Stores Phase 4 — Approval Task Lifecycle Checkpoint

## Delivered
- Stores material-request review now closes open matching `stores.material_request.approval` tasks using the already-installed shared coordination service helper `_close_tasks`.
- Task completion and material-request approval/rejection take place in the **same database transaction** before commit. Both approval and rejection close the review task, with the actor and reason recorded as task evidence.
- Existing maker-checker, source requirement approval, contractor ownership and released-work-package checks are retained.
- Added `GET /api/projects/{pid}/stores/material-requests/approval-task-status`, a read-only project/org-scoped task status summary with reviewer ID, overdue tasks, completion count, and a clear **Unverified** stock-readiness label.
- No new ledger, procurement requirement, inventory posting, stock availability assertion or standalone notification system was added.

## Caveats / next work
- Command Center consumption is **not wired** into the separate Command Center backend in this checkpoint. Its service identity, project scopes and per-user drill-down access must be enforced before connecting.
- Configurable escalations are not yet connected to the new task summary. The existing shared Task scheduling machinery is retained.
- No new database schema migration is necessary for this change; existing Task columns are reused.
- Live PostgreSQL transaction testing, frontend TypeScript build, full Docker E2E, and legacy issue/reservation writer protection remain pending. Live material issuing remains gated.
- A request approved/rejected before this upgrade might have open tasks; a separate audited historical cleanup should be planned, not silently changed.

## Validation
- Python compilation: PASS.
- `python -m pytest -q tests/test_stores_task_lifecycle_contract.py`: 3 PASS.
- ZIP integrity: verified at packaging.

## Follow-up
1. Authorize Command Center service-to-service read-only consumption with project entitlements and freshness indicators.
2. Connect shared task escalation/reminder policy and cancellation handling.
3. Run live SQL transaction/concurrency tests and UAT before enabling inventory movement paths.
