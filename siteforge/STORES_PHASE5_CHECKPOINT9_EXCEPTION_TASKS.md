# Stores Phase 5 — Checkpoint 9: Return Exception Ownership

## Implemented
- `POST /api/projects/{pid}/stores/material-returns/{return_id}/exception-task`: project-scoped assignment to a live authorized Stores or QA assignee. Reuses shared `Task`, reminders and notifications, with no second task ledger.
- `POST /api/projects/{pid}/stores/material-returns/{return_id}/exception-task/{task_id}/resolve`: records evidence and closes only after the underlying return's classified exception has changed. It does **not** modify stock quantities, QA disposition or the custody record.
- Active task deduplication, independent QA recipient checks, tenant isolation, audit events, and generic My Tasks mutation bypass protection.

## Important limitations
- Separate Command Center backend and dashboard not updated in this checkpoint.
- State-based resolution only confirms a workflow transition; physical reconciliation and stock readiness remain **Unverified**.
- No PostgreSQL runtime, Docker integration, notification-worker or TypeScript build validation performed. Feature-gated stock posting remains disabled.
- PostgreSQL concurrency/race tests for new endpoints are deferred with other database tests.

## Run focused tests
`cd backend && pytest -q tests/test_stores_phase5_return_exception_tasks.py tests/test_stores_phase5_return_exception_monitor.py tests/test_stores_phase5_returns_contract.py`
