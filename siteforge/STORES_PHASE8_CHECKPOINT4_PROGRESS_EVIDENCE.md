# Stores Phase 8 — Checkpoint 4: Progress Material Evidence

## Delivered
- Read-only `GET /api/projects/{pid}/stores/phase8/progress-material-evidence`, with optional work-package and limit filters.
- Requires project-scoped `construction.view` authorization.
- Reuses existing Stores QA-verified consumption/installation evidence, contractor handover, original Procurement requirement and issued stock-posting references.
- Links only Approved Construction Progress reports where the progress line has the exact stock posting and the Construction activity has the same work-package ID.
- Treats material quantities and construction activity quantities as distinct measurements.
- Includes explicit `progress_earned: false`, `billing_certified: false`, `physical_stock_verified: false` in responses; no stock, Progress or Finance mutation.
- Rejects incomplete or inconsistent material/issue/work-package lineage instead of guessing.

## Validation
- `python -m pytest -q tests/test_stores_phase8_progress_evidence.py -p no:cacheprovider`: 4 passed.
- Python compilation passed.
- Full migration, Docker, PostgreSQL, frontend TypeScript and end-to-end Progress integration are not verified.

## Remaining
- Display Progress evidence within the actual Progress module screens and define an authorized acceptance/rejection workflow.
- Earned Progress / billing certification must remain within authoritative Progress / Contracts / Financials workflows.
- Actual DB and concurrent posting validation remains deferred; physical stock mutation feature flags stay off.
