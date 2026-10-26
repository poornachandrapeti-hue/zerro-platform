# Phase 6 — Transfer-derived reservation intent canonical-demand gate

## Implemented
- Requires `material_request_id` from an already approved project-scoped Stores issue request.
- Rechecks the canonical Procurement requirement, material/unit, authorized work package and WBS using the existing Phase 5 issue authorization function.
- Locks the destination lot and approved Stores request; guards cumulative pending intents against destination lot and approved request quantities.
- Idempotent retries must match destination lot, quantity and Stores request.
- Reuses the single reservation table, storing `PendingActivation` only. Does not increase `StockBalance.reserved` or post inventory.

## Not complete
Transfer-derived activation, physical issue posting, transfer lot quantity consumption and final available-stock reconciliation. These require service and PostgreSQL concurrency tests. Feature flags must remain disabled.

## Checks
Five focused tests pass locally. Python compilation and archive integrity checked. Live PostgreSQL / Docker validation deferred.
