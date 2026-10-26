# Stores Phase 7 — Checkpoint 6: Scrap Classification and Disposal Evidence

## Implemented
- `stores_scrap_cases` migration and model; project/org scoped, receipt-lot attributed, audited.
- Scrap proposal for Damaged, Obsolete, Expired, Unserviceable, SurplusScrap, with reason and evidence.
- Independent Stores review: Reject or ApproveCustodyReview. This is **not** approval of inventory write-off or legal disposal.
- Third-party disposal evidence recording after review, with a separate operator and reference.
- Read-only scrap case listing with explicit `stock_written_off: false` and `inventory_readiness: Unverified`.
- Conservative open-proposal sum check against original receipt provenance; original receipt quantity is **not** current on-hand quantity.

## APIs
- POST `/api/projects/{pid}/stores/scrap-cases`
- GET `/api/projects/{pid}/stores/scrap-cases`
- POST `/api/projects/{pid}/stores/scrap-cases/{sid}/review`
- POST `/api/projects/{pid}/stores/scrap-cases/{sid}/disposal-evidence`

## Open dependencies
- Actual stock-level quarantine/hold across **all** GRN, transfer-derived and legacy writers.
- Material owner approval, environmental/HSE disposal policy, supporting certificates and financial consequences.
- Authoritative lot-level stock snapshot and controlled write-off posting in existing ledger.
- Dedicated Internal Stores scrap UI, and cross-module notifications/dashboard.
- PostgreSQL migrations, concurrency tests, frontend build and Docker E2E remain deferred; **do not enable physical inventory disposal**.

## Validation
- Three focused tests passed; Python compilation and archive integrity checked.
