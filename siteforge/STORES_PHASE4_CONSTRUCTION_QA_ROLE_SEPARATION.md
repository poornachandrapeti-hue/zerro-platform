# Phase 4 — Construction / QA Role Separation

## Change

The construction acknowledgment service now resolves a project through the existing supply-chain project-scope helper and requires `construction.view` and the assigned task owner. It no longer requires `quality.view` from a Construction owner.

The QA verification service requires `quality.edit` through `qa_access` and verifies that the QA reviewer is not the task owner. It no longer requires `construction.view` from a QA reviewer.

Both endpoints retain locked QA-case checks, project/organization filters, optimistic task-version validation, and the requirement for a previously recorded Construction acknowledgment. Shared My Tasks editing remains blocked for these specialized tasks.

## Validation

Run:

```bash
cd siteforge/backend
python -m pytest -q tests/test_stores_construction_qa_role_separation.py tests/test_stores_construction_qa_resolution_contract.py tests/test_stores_qa_construction_task_contract.py tests/test_stores_construction_qa_postgres_application.py
```

The PostgreSQL integration tests require a **disposable migrated** PostgreSQL database configured with `STORES_TEST_DATABASE_URL`. They are skipped without it. These tests stub project/RBAC checks for transaction-focused cases; live authorization tests remain outstanding.

**No inventory or stock issue feature flags were enabled.** Full PostgreSQL/Docker integration, migrations, upstream Command Center deployment and broader end-to-end permissions testing remain outstanding.
