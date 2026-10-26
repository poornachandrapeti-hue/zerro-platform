# Phase 5 — Checkpoint 16: Construction Material Usage & Independent QA

## Delivered
- Internal Stores/Construction material-usage tab for issue-linked, quantified Consumed or Installed evidence, with work-package filter and error state.
- Separately authorized, project-and-organization-scoped QA queue endpoint `GET /api/projects/{pid}/stores/phase5/material-usages/qa-queue` for pending evidence not submitted by the reviewing user. Existing creator-scoped list is not relaxed.
- Dedicated QA verify/reject action with existing optimistic version and maker/checker enforcement.
- Return stock-posting guard against returning quantities already claimed by **Verified** or **Pending QA** material usage, with handover locking and checks before writing to the existing stock ledger.
- No new stock ledger, no inferred progress, no automatic billing.

## Validation
- `PYTHONPATH=. pytest -q tests/test_stores_*.py`: 280 passed, 15 skipped (database tests are deferred).
- Python compile checks passed. Full frontend TypeScript build, live PostgreSQL and Docker tests were not executed.
- Two old source-text tests were refreshed to reflect existing grouped shared-task guards and the current return UI wording; no runtime behavior was weakened.

## Release restrictions
- Lot posting gates remain disabled. A QA-verified material usage record does not prove physical inventory readiness or certified billing. The QA list is capped to 300 recent pending records and should be paginated for large projects.
- Future work: dedicated Construction navigation and field evidence attachments, qualified installation QA checklists, end-to-end PostgreSQL locking tests and separate Command Center runtime integration.
