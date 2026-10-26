# Phase 6 — Checkpoint 5: Vendor return and replacement tracking

## Source delivered
- Reuses canonical Procurement vendors, POs, PO lines, material items, and warehouse records.
- Implements a project-scoped supplier return: Requested → Authorized/Rejected → Dispatched → Vendor Acknowledged → Replacement Recorded.
- Each transition records evidence, audit, authorized actor and expected version; approval is maker-checker separated.
- A Procurement-authorized employee **records vendor acknowledgment evidence**; this is not authenticated vendor portal acknowledgment.
- Replacement reference is documentary only: no GRN acceptance, stock ledger posting, title transfer, finance adjustment or vendor credit is implied.
- Vendor return record does not prove QA disposition or physical inventory eligibility. QA clearance and actual issue/return ledger integration are future work.
- No stock mutation; activation of any movement remains disabled pending DB validation.

## Follow-up
- QA inspection and supplier return authorization evidence; link return to specific lot/receipt, not just PO item.
- Independent supplier portal acknowledgment, credit/replacement Procurement workflows, shipping evidence.
- Phase 6 Checkpoint 6: controlled transfer posting, always behind feature gate.

## Deferred
Actual Alembic upgrade, PostgreSQL concurrency and end-to-end API/Frontend build.
