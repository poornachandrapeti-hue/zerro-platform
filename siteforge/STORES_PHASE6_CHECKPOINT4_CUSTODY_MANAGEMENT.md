# Phase 6 Checkpoint 4 — Owner Declaration & Destination Custody

Source-level implementation:
- Transfer creation optionally captures all three company IDs together: declared material owner, source custodian, destination custodian. All must be active companies belonging to the same organization; custodians must be distinct.
- Destination custody confirmation is a separate, audited, version-checked transaction after receipt and any discrepancy resolution, and requires an independent user from the designated destination company.
- API: POST /api/projects/{pid}/stores/material-transfers/{transfer_id}/confirm-custody (body: version, evidence).
- Transfer payload exposes declarations and confirmation; `ownership_verified=false`, `ownership_transferred=false`, and `inventory_posted=false` explicitly prevent title/balance misrepresentation.
- Existing lot-level ownership provenance and existing single inventory ledger remain unchanged.

Limitations / follow-up:
- Company declarations are not documentary proof of legal ownership. Reconcile to authoritative receipt-lot provenance before enabling inventory movement.
- No automatic lot/batch allocation or actual title-change workflow is provided by this checkpoint.
- The new DB migration must be applied and application-level tests run on Docker PostgreSQL before release. No live stock feature flag was changed.
- A destination-side user confirmation is recorded; manager UI for change visibility can be added in next checkpoint.

Validation: Python syntax compilation passed. Focused pytest invocation stalled in this runtime; PostgreSQL driver not installed in standalone shell. Live DB, Docker and frontend TypeScript tests not executed.
