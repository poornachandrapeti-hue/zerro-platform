# Stores Phase 4 — Construction/QA Impact Review Audit Trail

This checkpoint adds organization/project-scoped audit records for creation of QA-revocation Construction review tasks, Construction acknowledgment, and independent QA verification. Each audit record is added to the same SQLAlchemy transaction before the workflow commit. Audit details include the inspection case and task identity, plus applicable work package, owner, and reviewer identifiers. Full task evidence remains on the task; the audit event records the transition without copying potentially sensitive free-text evidence.

The shared Coordination task service, stock ledger and existing permissions are unchanged. QA review completion does not certify complete lot provenance or authorize live inventory issuing.

Validation: 12 focused tests passed. Live PostgreSQL transactions, notification worker and Docker tests were not run. Stock issuing remains disabled.
