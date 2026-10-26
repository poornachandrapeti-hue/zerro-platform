# Phase 6 — Transfer-Derived Lot Eligibility Checkpoint

## Added
- Read-only GET `/api/projects/{pid}/stores/material-transfers/{transfer_id}/destination-lot-eligibility`.
- Project/organization-scoped authorization using existing Stores permission and authenticated user.
- Paired posting reconciliation, independent destination QA acceptance status, and explicit stock-activation blockers in one response.
- Contract regression tests for accepted and quarantined destination lots.

## Still pending
- Typed transfer-lot reservation allocations and downstream physical issue posting integration; GRN receipt lots must not be impersonated by transfer destination lots.
- Transfer-derived per-lot available quantity accounting and existing stock balance reconciliation.
- PostgreSQL transactional validation, Docker deployment and complete frontend build.
- Physical transfer/issue feature gates remain disabled; this endpoint performs no stock mutations.

## Verification
- Python compileall completed; two focused test assertions passed locally.
