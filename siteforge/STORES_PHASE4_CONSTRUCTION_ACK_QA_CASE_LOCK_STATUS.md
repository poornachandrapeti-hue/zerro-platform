# Phase 4 — Construction acknowledgment QA-state transaction gate

## Change

The construction acknowledgment endpoint now obtains a PostgreSQL `FOR UPDATE` row lock on the matching, organization- and project-scoped Stores inspection case **before** locking the linked task. It rejects missing or no-longer-`Quality Revoked` cases before updating task evidence/status/version.

This matches the case-then-task ordering already used for independent QA verification, preventing inconsistent lock ordering and serializing the two operations with case-state transitions that lock the QA case row.

## Scope and safety

- No new inventory ledger, reservation, quantity mutation, stock release or enablement of live issue.
- Existing maker-checker and task-version requirements preserved.
- QA verification remains required for completion.
- Only a transactional source-level safeguard; this does not prove serializability of all QA workflows, nor full external Construction completion.

## Checks executed

`cd backend && python -m pytest -q tests/test_stores_construction_qa_resolution_contract.py tests/test_stores_qa_construction_task_contract.py` — **7 passed**.

`python -m compileall -q app/domains/stores_inventory/qa_issued_impact.py` — passed.

## Still required

Run migrated app on a disposable PostgreSQL database, then test races between QA transitions, Construction acknowledgment, and QA verification using independent sessions. Also test permissions, duplicate submissions, notification worker, UI and Docker end-to-end paths. Do not activate live stock issuing.
