# Phase 6 — Transfer-derived lot allocation preview

Implemented a read-only, project-scoped transfer destination-lot allocation preview. It binds the destination lot to its original GRN source lineage, derives its item/unit from the original receipt, checks the existing warehouse ledger reconciliation, and reports QA/posting/quantity blockers. The preview never mutates reservations, postings, or balances and always returns `reservation_allowed=false`, `issue_allowed=false`, and `physical_stock_readiness=Unverified`.

Endpoint: `GET /api/projects/{pid}/stores/material-transfers/destination-lots/{lot_id}/allocation-preview?quantity=...`.

**Remaining implementation:** Extend the canonical reservation schema and both lot writers for transfer-derived lots; enforce provenance-specific available quantities and downstream QA in the same transaction; reconcile returned/issues across types; complete actual PostgreSQL concurrency and Docker testing before activation. Feature gates remain off.
