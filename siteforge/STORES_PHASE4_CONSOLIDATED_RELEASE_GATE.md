# Stores Phase 4 — Consolidated Release Gate (2026-10-23)

## Actual checkpoint outcome: BLOCKED (not release ready)

From this unpacked source, the Stores-focused suite runs **183 passed, 15 skipped**, with no failing tests. The 15 skipped tests include PostgreSQL-dependent scenarios; **STORES_TEST_DATABASE_URL** was not configured in this environment, so the real database transaction gate is NOT satisfied. There is no claim of Docker, frontend or separate Command Center runtime validation.

## Source corrections

- `backend/tests/test_stores_readiness_exceptions.py`: removed a hardcoded `/mnt/data/...` source path, allowing ZIP portability and collection from a clean workspace.
- `backend/tests/test_stores_phase4_partner_review_gate_static.py`: changed obsolete expected `procurement.master.edit` to current canonical `stores.requests.review` permission while maintaining Pending Approval assertion.
- `backend/tests/run_stores_phase4_release_gate.py`: new single-command Stores-focused regression gate, producing JUnit XML and JSON result. Refuses to return success if skipped tests remain or PostgreSQL test URL is absent. Blocks running with enabled lot cutover/atomic writer flags and forces cutover off for test process.

## Running on your disposable, migrated PostgreSQL test DB

1. Copy/extract this archive locally, create a disposable PostgreSQL database with the application's migrations. Do NOT use production DB.
2. Set `STORES_TEST_DATABASE_URL` according to existing tests (e.g. `postgresql+psycopg://tester:password@localhost:5432/zerro_stores_test`).
3. From `siteforge/backend` run `python tests/run_stores_phase4_release_gate.py`.
4. Inspect `stores_phase4_release_report.json` and `stores_phase4_release_junit.xml`. A PASS is only test-suite completion, NOT final production sign-off.

## Outstanding gates

- Real PostgreSQL transaction and concurrent operations on application paths, with migration validation.
- Procurement–Stores–QA–Construction workflow on running Docker services using role-scoped users.
- Separate Command Center backend route registration, authentication, project scope and freshness live tests.
- Frontend build, Docker E2E smoke, rollback handling and full inventory writer audit. Live physical issuing/cutover must remain disabled.

The existing one-authoritative-demand/one-ledger constraints are unchanged.
