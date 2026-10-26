# Stores Phase 5 — Checkpoint 19: Functional Closure Review

## Delivered in this checkpoint

- Added project-scoped GET `/api/projects/{pid}/stores/phase5/construction-manager-material-balance`.
- This distinct read-only Construction view requires `construction.view`; it can inspect cross-request handover/material balances for the project. Optional work-package ID limits the request selection.
- Preserved the existing `/phase5/work-package-material-balance` endpoint's `stores.requests.view` authorization and requester-only visibility for non-organization-admin users.
- Both views use the same fail-closed quantity reconciliation and inventory-unverified markings. Neither creates stock postings nor invents installation quantities.
- Added focused tests for role selection, requester isolation, and invalid work-package filters.

## Functional review against Phase 5 site issue and return scope

| Requirement | Evidence in package | Remaining limitations |
| --- | --- | --- |
| Issue references approved demand and reservations | Issue authorization and atomic lot issue services | Physical posting feature-disabled; PostgreSQL execution deferred |
| Dispatch and receiver acknowledgment | Material handover APIs, Partner and Internal UI | Full browser build and runtime QA pending |
| Shortage/damage dispute handling | Handover discrepancy decision workflow | Settlement does not auto-post corrective inventory |
| Contractor site return and Stores receiving | Return request, verify and Partner UI | Return posting disabled by feature gates |
| Independent QA disposition | Return QA disposition route | Live end-to-end database and role testing deferred |
| Warehouse/bin placement | Return placement API and Internal screen | Bin level verified physical balance not established |
| Work-package issue/return/usage trace | Material balance and verified usage APIs; new manager view | Legacy unmapped movements not exhaustively covered |
| Construction evidence and independent QA | Material-specific usage and QA verification | No automatic progress or certified billing inference |
| Command Center reporting | Secure source feeds and integration adapter/components | Separately deployed Command Center backend not wired and runtime verified |

## Test evidence

Focused tests: `python -m pytest -q tests/test_stores_phase5_manager_balance_access.py tests/test_stores_phase5_material_balance.py` → 11 passed in source worktree.

## Release decisions

**Functional development: advanced but not signed off.** A distinct Construction-manager access path is now present. This checkpoint does not prove full backend/frontend integration or satisfy deferred PostgreSQL and Docker release gates. Inventory feature flags must remain disabled; no production go-live recommendation is made.

## Next functional milestone

1. Surface the Construction manager material balance view in the Construction UI/navigation, retaining the role boundary.
2. Wire separate Command Center backend to scoped Stores feeds once its source is available.
3. Perform cross-module acceptance flows and postponed DB migration/concurrency verification before enabling physical stock writers.
