# Phase 5 — Checkpoint 14: Construction progress evidence integration

## Delivered
- Read-only GET `/api/projects/{pid}/stores/phase5/construction-consumption-evidence` (optional `work_package_id`).
- Joins request-linked Stores posted issues to existing Construction `ProgressLine.stock_posting_id`, approved `ProgressReport` and matching `ConstructionActivity.package_id`.
- Reuses existing project/request visibility, includes only same-organization/project approved reports.
- Exposes progress report/line IDs and activity measurements as evidence, **not** material consumed or installed quantities.
- Reuses existing stock issue/return trace; no second material ledger or constructed installation record.
- No database migration and no inventory feature flag changes.

## Not yet delivered
- Genuine material-specific installed/consumed quantity certification, which requires an authoritative Construction record with item, quantity, unit, lot and verification provenance.
- Live PostgreSQL/Docker workflow validation, TypeScript UI build, and Command Center runtime wiring.
- All source flags for live stock posting stay off.

## Tests
`cd backend && python -m pytest -q tests/test_stores_phase5_construction_consumption_evidence.py tests/test_stores_phase5_construction_trace.py`

Avoid interpreting activity progress units (e.g. meters of pipe installed or cubic meters of civil works) as a measured material usage quantity.
