# Phase 6 — Mixed GRN and Transfer-Derived Lot Reconciliation

## Delivered

- `GET /api/projects/{pid}/stores/lot-provenance/warehouse-balance?warehouse_id=...&item_id=...&unit=...`
- Read-only stock movement split for original GRN Accept, Issue, Return, TransferOut and TransferIn posted movements.
- Transfer-derived destination-lot lineage checks (paired posting references, QA status and quantity).
- Explicit flags for orphan destination lots, missing transfer provenance, unsupported movement kinds, invalid quantities, and aggregate ledger mismatches.
- Project/organization-scoped read model using existing stock view permission.
- Six tests for balanced GRN, transfer non-availability, missing transfer lineage, quarantined lot, orphan and mismatch, and unsupported movements.

## Important limitations

This is an accounting **diagnostic**, not an issue or reservation allocator. `reservable=false` and `issuable=false` unconditionally. It does not add new physical balances or duplicate material demand. Aggregate stock remains the existing Procurement StockBalance row.

Original GRN-only lot reservation/issue paths stay unchanged and existing mixed-provenance quarantine guards continue to block warehouses/items with posted TransferIn movements. Provenance-aware live reservation, issue, aggregate reserved attribution, transfer reversals and cross-project posting still require implementation and PostgreSQL concurrency validation.

The diagnostic recognizes only posting kinds explicitly covered. It fails closed on other kinds; those must be reconciled before a reliable historical opening-to-closing balance conclusion. It does not provide QA-releasable availability even on a reconciled item. The endpoint currently reads a single warehouse/item/unit; it is not an all-time project dashboard.

## Local checks

`python -m pytest -q -o addopts='' tests/test_stores_phase6_mixed_lot_provenance.py`

Six tests passed. Python compilation passed. PostgreSQL and Docker execution remain deferred and **no posting feature flags were enabled**.
