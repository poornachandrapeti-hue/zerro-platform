# Phase 7 Checkpoint 3 — Cycle Count Management

Implements scheduled per-warehouse cycle-count sessions, receipt-lot count sheets, evidence, submit, independent recount/verification, version checking and audit.

**No stock movement or adjustment is posted.** The receipt lot original quantity is a provenance comparison, **not current on-hand stock**. Variances in this version are comparison to recorded origin quantities, not accounting variances. Reconciliation to point-in-time ledger balances, transfer-derived lots, physical bin counting, and adjustments remain for later checkpoints.

Endpoints: POST/GET `/api/projects/{pid}/stores/cycle-counts`, GET `/cycle-counts/{id}`, POST `/cycle-counts/{id}/lines`, `/submit`, `/review?decision=Verify|Recount`. Requires project `procurement.stock.view/edit` as appropriate.

PostgreSQL/Docker validation deferred. No feature flags enabled.
