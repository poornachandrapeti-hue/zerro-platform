# Phase 4 QA revoked-material construction follow-up checkpoint

Added `POST /api/projects/{pid}/stores/inspection-cases/{case_id}/construction-review-tasks` to the existing Stores QA exposure router.

- Requires QA editing permission and Construction viewing permission in the project.
- Locks the revoked QA case while evaluating idempotent task creation.
- Reuses only existing explicitly lot-attributed posted issues to identify work packages. Does not infer installed quantities.
- Creates high-priority shared My Tasks for active responsible work-package owners with matching project/discipline access. Missing or unauthorized owners are reported without task creation.
- Existing tasks (including completed tasks) are returned instead of duplicated or reopened; task notifications and reminder policies follow the existing Coordination service.
- No stock postings, holds, recalls, balance changes, or automatic closure of construction work packages.
- Unmapped legacy exposure remains possible; manual QA and Construction investigation remains mandatory.

## Release limitations

Focused source-contract tests pass. A PostgreSQL test database, connected notification worker, real authorization fixtures, Docker integration and frontend build were **not** exercised here. The new endpoint does not close Phase 4 or permit physical issuing; release feature flags remain disabled.
