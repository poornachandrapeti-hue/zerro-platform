# Phase 6 — Same-project paired transfer posting (source-level implementation)

## Implemented
- Feature-gated `POST /api/projects/{pid}/stores/material-transfers/{id}/post-stock`.
- Only fully acknowledged, discrepancy-resolved, same-project transfers with matching source-lot and destination-transfer-lot plans qualify.
- Current source QA case/version and explicit QA accepted quantity are rechecked before posting.
- Source inventory aggregate available balance and destination balance invariants are checked; both balances are locked in warehouse-ID order.
- Exactly one `TransferOut` and one `TransferIn` posting (linked by `source_posting_id`) and matching posting lines use the existing `stock_postings`, `stock_posting_lines`, `stock_balances` ledger inside a single transaction/commit.
- Outbound posting records original receipt lot provenance; destination transfer lot is left `PostedPendingQA` and is NOT a GRN lot or valid reservation/issue lot.
- Transfer lineage stores both posting IDs and transitions to `Posted` only within the same transaction. Repeated attempts are rejected.

## Not ready to activate
- **DO NOT ENABLE** `STORES_ATOMIC_TRANSFER_POSTING_ENABLED` or `STORES_LOT_WRITER_CUTOVER` in any live deployment. Both default to false.
- Current coverage and reconciliation helpers are still oriented around legacy `Accept/Issue/Return` kinds; they must be updated to account for paired `TransferOut/TransferIn` without double counting.
- Destination transfer-derived lot has no independently verified QA clearance/release workflow. Its quantity is on the destination aggregate ledger, but cannot be reserved/issued through lot-based APIs. Other potential stock mutation/readiness routes need a final access audit.
- Inter-project stock posting remains blocked. Transfer-to-destination-lot issue authorization, return, reversal, and cancellation must be specified and built before activation.
- Live migrated PostgreSQL transaction tests (rollback, simultaneous requests, cancellation, QA revocation), frontend build and Docker E2E testing have not run.
- A focused offline test printed `7 passed` but the process timed out during shutdown. Python compilation and ZIP integrity were checked separately.

## Deployment note
Use the included source for continued development only. Do not treat this checkpoint as a sign-off for live stock movements.
