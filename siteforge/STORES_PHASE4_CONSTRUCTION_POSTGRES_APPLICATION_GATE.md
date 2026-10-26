# Phase 4 — Construction/QA PostgreSQL application transaction gate

Added `backend/tests/test_stores_construction_qa_postgres_application.py`.

## Test scope

Uses the real application ORM models (`StoresInspectionCase`, `Task`) and directly invokes the actual Construction acknowledgment and QA verification service functions. On a disposable **already migrated** PostgreSQL test database, creates an isolated schema with clones of the two relevant tables; no operational rows are changed.

Tests:
- Concurrent acknowledgment submissions sharing the same task version: only one succeeds.
- Stale version cannot be used for independent QA verification.
- Only the assigned Construction owner can acknowledge; the owner cannot QA-verify.
- Two concurrent QA verification submissions: exactly one succeeds and evidence is appended once.

Authorization dependencies are stubbed solely to isolate the transaction paths. These are **not** real HTTP/RBAC or production DB integration tests. PostgreSQL execution has **not** been completed in this environment.

## Run

Set `STORES_TEST_DATABASE_URL` to a **disposable database with current migrations already applied** (do not use the application/production database):

```bash
cd siteforge/backend
STORES_TEST_DATABASE_URL='postgresql+psycopg://user:pass@localhost:5432/zerro_stores_test' \
  python -m pytest -q tests/test_stores_construction_qa_postgres_application.py
```

Requires CREATE/DROP SCHEMA grants. The suite clones `public.stores_inspection_cases` and `public.tasks`; if migrations use a different schema, adapt the suite before running. Missing URL skips tests by design.

## Remaining release gates

- Execute tests on actual PostgreSQL and remediate any failures.
- Validate migrations, HTTP endpoints and live RBAC/project scopes end to end.
- Validate QA revocation races, ledger/lot posting paths, Docker deployment, and notification jobs.
- **Do not enable physical inventory issuing or writer cutover.**
