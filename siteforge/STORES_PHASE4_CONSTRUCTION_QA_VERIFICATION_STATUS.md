# Phase 4 — Construction acknowledgment and QA verification

## Implemented
- POST `/api/projects/{pid}/stores/inspection-cases/{case_id}/construction-review-tasks/{task_id}/acknowledge`: assigned Construction reviewer records evidence, moves an Open task to In Progress.
- POST `/api/projects/{pid}/stores/inspection-cases/{case_id}/construction-review-tasks/{task_id}/qa-verify`: independent authorized QA reviewer completes the task only after Construction acknowledgment, while the original QA case is still Quality Revoked.
- Both actions require optimistic task version matching, organization/project scope, task source identifiers and role checks.
- Generic My Tasks completion/cancellation is rejected for this special review task type to prevent bypass.
- Completion means a **documented Construction/QA review**, never stock reinstatement or proof that every impacted lot or installation is mapped.

## Not validated or implemented
- Live PostgreSQL transactional or race tests, database migration/test suite, Docker and frontend build are not run here.
- Historical outbound records without explicit lot mapping still need manual investigation.
- No automatic material recall, inventory reversal, installation certification or live issuing is authorized.
- The separate Command Center backend connection remains deployment-dependent.
