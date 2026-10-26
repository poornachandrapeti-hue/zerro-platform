# Phase 6 — Transfer-derived issue downstream handover integration

## Delivered
- The existing Phase 5 dispatch API accepts posted transfer-derived issue lines backed by exactly one complete `StoresTransferIssueAllocation`, in addition to the existing original-GRN provenance allocation.
- Transfer-derived demand linkage resolves through the existing `StoresLotReservation.material_request_id`, scoped to the same organization/project and destination lot; the linked Stores material request must still be approved.
- Existing contractor acknowledgment/discrepancy actions and Construction material usage/independent QA verification continue using the one `StoresMaterialHandover` and one `StoresConstructionMaterialUsage` workflow, with no duplicate ledger or demand records.
- Ambiguous, partial, or missing lot provenance is rejected.

## Still pending / deliberately blocked
- Transfer-derived return custody requests may be tracked via existing handovers, but **physical return stock posting does not yet support transfer-derived lot provenance**: the existing return writer requires a `StoresOutboundLotAllocation` against an original GRN lot and rejects transfers. Do not bypass this condition or invent a GRN lot.
- Transfer-aware posted-return lineage, return QA stock allocation, reversal, reconciliation, separate Command Center runtime integration, migrations, live PostgreSQL transactions, frontend build, Docker tests and end-to-end partner/Construction workflow validation remain outstanding.
- Keep all physical stock feature flags OFF, including transfer lot issuing/reservation activation and paired transfer posting, until database-backed validation and downstream safety checks pass.

## Checks performed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_stores_phase6_transfer_handover_integration.py`: 6 passed.
- No live database or frontend deployment executed.
