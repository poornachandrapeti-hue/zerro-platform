# Phase 4 — QA-revoked material outbound impact checkpoint

## Added
- Read-only GET `/api/projects/{pid}/stores/inspection-cases/{case_id}/revocation-impact`.
- Requires internal Stores QA project access; case, lots and allocated movements are organization/project scoped.
- Only explicit lot allocations against posted Issue/Return records appear as attributed outbound exposure and work-package references.
- Explicit `impact_scope_verified=false`, `stock_available_to_issue=null`, and warning about unmapped legacy movements.
- Does not create an extra physical ledger, adjust inventory, undo issue, or auto-recall installed material.

## Validation
- Six focused tests passed (new endpoint helper and existing QA revocation terminal coverage).
- Python source compilation passed; source archive integrity checked.
- Live PostgreSQL, deployed construction impact workflow, notification routing and end-to-end tests remain pending.

## Release gate
- Keep live lot issue disabled until real PostgreSQL transaction/concurrency validation and cross-module QA impact workflows are completed.
