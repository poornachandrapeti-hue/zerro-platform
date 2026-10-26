# Phase 7 — Checkpoint 1: Preservation and Expiry

Added receipt-lot preservation schedules, append-only inspection checks, due/overdue/expiry monitoring and project-scoped audit. This is evidence-only and does not change stock.

APIs: POST /api/projects/{pid}/stores/preservation/plans; GET /api/projects/{pid}/stores/preservation/plans; POST /api/projects/{pid}/stores/preservation/plans/{plan_id}/checks.

Outstanding: transferred-lot preservation, independent QA hold enforcement across issuing, owner-specific access tests, reminders, cycle counts, adjustment and disposal modules, frontend UI. PostgreSQL migration and Docker validation are deferred. Do not enable stock issuing on this basis.
