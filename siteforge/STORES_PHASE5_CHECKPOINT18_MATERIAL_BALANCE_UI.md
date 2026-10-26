# Phase 5 Checkpoint 18 — Work-package material balance UI

## Delivered
- Added a Work-Package Material Balance tab to the existing Stores workspace.
- Uses the already implemented read-only `/api/projects/{pid}/stores/phase5/work-package-material-balance` route and optional `work_package_id` query.
- Shows issued, ledger-posted returns, outstanding, pending return custody, pending QA usage, verified consumed/installed and unallocated outstanding quantities separately by issue handover.
- Includes loading, permission/error, empty and source-coverage states; no synthetic balances.
- Does not modify physical stock, billing, project progress, or consumption records.

## Outstanding
- PostgreSQL-backed workflow testing deferred at user request.
- Frontend TypeScript build not verified (dependencies not installed in workspace).
- Focused pytest process timed out/stalled during execution: not claimed passed.
- Material balance API restricts request-linked rows to original request creator for non-admin users; Construction manager-wide visibility needs a separate authorized read model.
- Separately deployed Command Center integration remains pending.
- Physical stock posting remains disabled and requires concurrency and reconciliation verification before activation.
