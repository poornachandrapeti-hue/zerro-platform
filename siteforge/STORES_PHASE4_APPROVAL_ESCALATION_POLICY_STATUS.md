# Stores Phase 4 — Approval Escalation Policy (incremental checkpoint)

## Added
- Before assigning a Stores approval task, validate the shared reminder policy's recipients for active organization membership, current project `stores.requests.review` authority and separation of duties.
- Reject invalid policy recipients instead of leaking task reminders to unauthorized users.
- Require the explicitly assigned reviewer to be active.
- Add `GET /api/projects/{pid}/stores/material-requests/approval-escalation-policy` for an authorized reviewer to see whether a project policy is configured and its reminder/escalation timings; no personal recipient data is returned.
- Reuse existing `ReminderPolicy`, `_task`, `schedule_task`, `jobs`, and `notifications`; do not add another scheduling or material ledger system.

## Configuration
Use the existing admin-only endpoint `POST /api/projects/{pid}/reminder-policies` with record_type `stores.material_request.approval`, `reminder_hours`, `escalate_after_hours` and reviewer-authorized `recipient_ids`. The policy must be configured before new tasks are assigned to schedule jobs automatically. Running a jobs worker remains essential.

## Validation
- Six targeted source contract tests (including existing secure Command Center feed tests) passed.
- Python compilation passed.
- Full PostgreSQL migrations, policy/job worker runtime, frontend build, and Docker end-to-end validation not run.

## Still pending
- Command Center backend dashboard consumer (separate service not confirmed in this archive).
- Backfill/schedule existing open tasks created before the reminder policy.
- Full Stores posting and reservation release gates and legacy writer unification.
- End-to-end access and notification checks against local Docker PostgreSQL.
