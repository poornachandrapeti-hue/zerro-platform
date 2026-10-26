# Stores Phase 5 — Partner receipt and discrepancy review

Implemented: partner company/request-owner-scoped material handover listing and versioned acknowledgment; Partner Material Receipts UI; independent internal Stores review of acknowledged discrepancies (Resolved or Escalated) with audit and evidence; internal Stores handover review UI. Both actions update evidence/status only, not the inventory ledger.

Contractor handovers remain based only on authorized, request-linked posted issues. Normal issues stay feature-gated. Only the original material requester may acknowledge; same company alone is not sufficient. Independent review disallows dispatcher or acknowledger as reviewer. Status transitions require current versions and are row-locked.

Important limitation: the resolution decision records review evidence, not a physical quantity correction. Replacement deliveries, returns, stock adjustments, document uploads, task escalation automation, complete project-based UI role testing and live PostgreSQL transactions remain pending.

Verification: see the Phase 5 handover tests and discrepancy-resolution tests. Database-dependent validation is deferred under user direction. Run migrations before invoking changed models or API routes. Frontend build could not run because node_modules is not installed in the execution environment.
