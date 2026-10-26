# Phase 8 Checkpoint 2 — Contract obligation reference and custody readiness

## Implemented
- One explicit Stores request → existing Contracts obligation reference, with same project, organization and contractor validation.
- Stores reviewer permission and audit of the link creation.
- Idempotent identical retries; conflicting replacement intentionally blocked pending a dedicated amendment workflow.
- Existing Phase 8 reference-readiness feed now displays verified *reference linkage* separately from legal entitlement and recovery authorization.
- Existing Procurement requirement and Construction work package remain authoritative.
- No duplicate contract register, no duplicate material requirement and no financial/stock posting.

## Not implemented / pending
- A selected obligation is NOT verified to contain an enforceable free-issue entitlement. No inference is made from contract title, company match or obligation description.
- Ownership/title, permitted wastage, recovery rates and charging remain unverified and blocked.
- Custody reconciliation under specific contractual terms is not yet supported; requires structured Contracts entitlement terms and controlled approvals.
- Dedicated UI; separate Command Center runtime; PostgreSQL migration execution and end-to-end tests are pending.
- Physical stock transactions remain disabled; deferred pre-production DB validation remains mandatory.

## API
POST /api/projects/{pid}/stores/phase8/material-requests/{request_id}/contract-obligation-link
Body: {"contract_id":1,"obligation_id":2,"evidence":"Referenced signed contract obligation"}
GET /api/projects/{pid}/stores/phase8/contract-free-issue-reference-readiness

## Verification
6 Phase 8 focused tests passed. Python compiled. One migration head. Archive integrity checked.
