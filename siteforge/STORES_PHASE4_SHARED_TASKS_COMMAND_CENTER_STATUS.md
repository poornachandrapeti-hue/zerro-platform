# Stores Phase 4 — Shared Approval Tasks and Command Center Approval Summary

## Changes
- Existing Stores material request router extended with `POST /api/projects/{pid}/stores/material-requests/{request_id}/approval-task`.
- Authorized internal reviewer explicitly specifies `reviewer_user_id`; backend checks organization, project RBAC and independent approval constraints.
- Pending request is row-locked; an existing active task is returned on repeat assignment, or conflicting assignee returns 409.
- Reuses the central Coordination `_task` function and its notification path; no parallel notification ledger.
- Adds `GET /api/projects/{pid}/stores/material-requests/command-center-approval-summary` with project-scoped pending and overdue counts.

## Boundaries
- API is a project-scoped summary consumed by a future Command Center integration; this checkpoint does **not** connect the separate Command Center service or publish events.
- Only manually invoked reviewer assignment creates tasks. No automatic escalation or task closure on approval is implemented.
- Physical stock readiness remains Unverified. No QA release, lot issuing, reservation activation or verified shortage indication added.
- Assignee's company/work-package segregation requires further contractor/owner-specific task visibility review before rollout.

## Tests
- Python compilation passed.
- `python -m pytest -q tests/test_stores_phase4_shared_tasks_contract.py tests/test_stores_readiness_exceptions.py`: 6 passed.
- Live database migrations, API integration and frontend TypeScript/Docker builds not executed.

## Next
- Wire assignment into an authorized Internal Portal reviewer selection workflow.
- Add task completion on actual approval/rejection and configure deduplicated escalation through shared Coordination service.
- Integrate authorization-checked summary subscription into separate Command Center backend and verify user scopes.
