# Phase 6 / Checkpoint 3 — Inter-project custody transfers

- Transfer requests may identify a destination project within the same organization. The initiating operator must be authorized on both projects.
- Source warehouse must belong to source project; destination warehouse must belong to destination project.
- Source project retains original approval, dispatch and discrepancy investigation controls.
- Destination project has an independently scoped inbox, destination acceptance and destination receipt endpoints.
- Cross-project transfers cannot use the source-project receipt endpoint.
- Independent destination custodian and receiving operator are required, with version checks, evidence and audit entries.
- Existing same-project transfer path is preserved. Historical rows are migrated with destination_project_id equal to source project.
- No inventory, title or ownership is posted or transferred in this checkpoint. Physical stock movement stays disabled.

## New routes
- GET /api/projects/{pid}/stores/material-transfers/destination-inbox
- POST /api/projects/{pid}/stores/material-transfers/destination/{transfer_id}/accept
- POST /api/projects/{pid}/stores/material-transfers/destination/{transfer_id}/receive

## Deferred
PostgreSQL migrations/runtime validation, frontend build, Docker E2E, actual transfer stock posting. Deployment requires applying the migration before using the endpoints.
