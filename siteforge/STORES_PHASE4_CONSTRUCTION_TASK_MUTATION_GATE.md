# Stores Phase 4 — Construction QA Review Task Mutation Gate

## Change
Generic Coordination/My Tasks updates now reject **all** writes to tasks whose source_type is `stores.qa_revocation.construction_review`, not only `Completed`/`Cancelled` transitions. This closes a route by which evidence, assignment, or `In Progress` status could previously be changed outside the controlled Construction acknowledgment and independent QA verification workflow.

Dedicated domain endpoints remain the supported writers:
- POST `/api/projects/{pid}/stores/inspection-cases/{case_id}/construction-review-tasks/{task_id}/acknowledge`
- POST `/api/projects/{pid}/stores/inspection-cases/{case_id}/construction-review-tasks/{task_id}/qa-verify`

Their QA-case row lock, task row lock, optimistic task version check, project scoping, and reviewer separation remain in place.

## Tests
Focused source-level regression suite: 6 passed. Python compilation passed. No live PostgreSQL or Docker integration was run in this workspace. Run full application-level multi-session tests in disposable PostgreSQL before production cutover. Live issuing remains disabled.
