# Phase 8 — Checkpoint 1: Contracts/free-issue reference readiness

## Delivered
- Added project-scoped GET `/api/projects/{pid}/stores/phase8/contract-free-issue-reference-readiness` (optional `work_package_id`).
- Returns Stores request, canonical Procurement requirement line, work package/WBS, handover IDs, and *candidate* contract IDs matched to the contractor company within the same project and organization.
- Uses `stores.requests.review` authorization; does **not** expose contract prices, terms, recovery amounts or other confidential commercial information.
- Explicitly marks all records **Blocked**: existing Stores requests lack an authoritative contract/free-issue obligation linkage. Company matching is not authorization.
- No changes to stock postings, demand, financials, progress, or contracts; no migration.
- Read model bounded to the most recent 500 project requests, with `as_of` and coverage notes.

## Follow-up development
- Add a reviewed source reference to a published/effective contract obligation and permitted free-issue terms, with distinct material owner, custodian, contractor and physical location.
- Contract owner must authorize entitlement and quantity/waiver rules; Finance determines accounting recovery and valuation; Planning/Progress consume read-only approved evidence.
- Build cross-module UI, notification/outbox, and reconciliation, then integrate separate Command Center securely.
- Deferred PostgreSQL, frontend and Docker tests remain mandatory before production; all live stock writer flags remain disabled.

## Verification
- Python syntax: passed.
- New focused unit tests: 3 passed.
- Archive integrity: verified after packaging.
