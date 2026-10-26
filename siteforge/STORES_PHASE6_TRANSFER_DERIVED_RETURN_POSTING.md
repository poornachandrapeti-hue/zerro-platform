# Phase 6 — Transfer-derived material return posting

Added provenance-aware return posting to the **existing** Stores return flow and Procurement stock ledger.

- Original GRN issues continue to use `stores_outbound_lot_allocations`.
- Transfer-derived issues use `stores_transfer_issue_allocations`; a posted return writes `stores_transfer_return_allocations`, referencing the original issue line and destination transfer lot.
- The posting requires existing Stores return custody, independent QA acceptance, audited bin placement, non-overlap with Construction usage, and original-issue quantity limits.
- The transfer lot must remain in an acceptable QA state; mixed provenance reconciliation must succeed.
- Posting to the existing `StockPosting` / `StockPostingLine` tables and the existing `StockBalance` happens in the same transaction as return provenance/audit writes.
- Transfer-derived returns require `STORES_TRANSFER_LOT_RETURN_ENABLED=true` in **addition** to the existing default-off Stores lot-return and writer-cutover gates.

**Do not enable the flags.** Live migrations, concurrent stock writer tests, transfer-derived return reconciliation across other readers, QA revocation behavior, reversal coverage, and end-to-end PostgreSQL validation have not been completed. Existing downstream reconciliation readers may need to be extended to classify transfer-derived Return lineages correctly before go-live. Inter-project stock movements are not enabled.
