# Phase 6 — Transfer-derived allocation safety checkpoint

## Delivered

The ordinary GRN receipt-lot reservation and issue flow now fails closed when the same warehouse/item has a posted `TransferIn` movement. This guard runs in the existing `_require_full_coverage()` path shared by both reservation and issue services. It prevents quarantined destination transfer credits from being treated as available through the GRN-only lot allocation model. The guard checks posted `TransferIn` rows in the current project/warehouse/item and leaves ordinary GRN-only warehouses on their existing provenance checks.

## Why allocation is not enabled yet

The current `StoresLotReservation` table links only to `stores_receipt_lots` (GRN receipt lots). The issue writer similarly requires a GRN source line and accepts only receipt-lot outbound allocations. Destination transfer lots have separate provenance and cannot safely be represented by a GRN lot ID. Simply bypassing those checks could result in misattributed issuing or over-allocation of quarantined transfer credits.

## Remaining functional development

- Add a reservation allocation model for `StoresTransferDestinationLot` with request/work-package reference, unique idempotency keys and posted transfer-lot balance tracking.
- Extend posting-line provenance and `_require_full_coverage` to distinguish QA-cleared transfer credits from quarantined ones, without masking GRN stock or blocking unrelated lots.
- Extend physical issue and return provenance for transfer-derived stock.
- Verify concurrency, inter-project authorization, and PostgreSQL rollback before activation.

## Verification

`tests/test_stores_phase6_transfer_quarantine_guard.py` exercises both the quarantined-transfer block and ordinary GRN-only path. Relevant focused tests were run against the unpacked source. No PostgreSQL or Docker integration was run. All physical stock feature flags remain disabled.
