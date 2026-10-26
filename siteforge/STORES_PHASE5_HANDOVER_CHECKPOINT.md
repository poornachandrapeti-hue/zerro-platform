# Phase 5 — Material dispatch and contractor acknowledgment (checkpoint 2)

## Delivered
- `stores_material_handovers` non-ledger table and reversible Alembic migration
- POST `/api/projects/{pid}/stores/material-handovers`: Stores stock-editor records dispatch evidence against an already posted, fully lot-attributed single-line issue whose attribution carries an approved Stores request reference; one handover per posting line
- POST `/api/projects/{pid}/stores/material-handovers/{handover_id}/acknowledge`: the original request creator (not the dispatcher) records received and damaged quantities and evidence; shortages and damage require notes; optimistic version check
- GET `/api/projects/{pid}/stores/material-handovers`: project/organization-scoped listing; non-admin users restricted to their own original requests
- Audit trail recorded through existing audit infrastructure. No stock posting created or balance changed.

## Tests
- 206 Stores-focused tests passed, 15 PostgreSQL-dependent tests skipped (no configured DB).
- Python compilation passed; migration execution not tested.

## Limitations / next checkpoint
- This is a minimal handover API, not yet a completed Partner Portal screen or multi-party sign-off.
- Confirmed discrepancies do not automatically adjust stock, invoice, earned progress, or install quantities.
- Source request linkage currently derives from the canonical lot issue allocation reason; replacing this text link with a dedicated FK will be a later migration task.
- Partner requester creation and company-scoped list access require dedicated partner API wiring before external rollout.
- Validation against PostgreSQL and Docker deferred per user request. Live issue feature flags stay disabled.
