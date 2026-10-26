# Phase 5 Checkpoint 4 — Return-to-Stores custody and QA

## Delivered
- `stores_material_returns` records: unique one return request per dispatched handover; linked to original issued material and approved source material requirement through handover.
- Internal endpoints: POST/GET `/api/projects/{pid}/stores/material-returns`, POST `/material-returns/{id}/receive`, POST `/material-returns/{id}/qa-disposition`.
- Partner endpoints: POST/GET `/api/partner/projects/{pid}/stores/material-returns`, restricted to source requester and company.
- Return quantity must be positive and not greater than acknowledged contractor-received quantity; unresolved discrepancies block submission.
- Three-step maker/Stores/independent-QA separation and optimistic version checks; audit events in same transaction.
- QA dispositions Accepted/Rejected/Quarantined are evidence only. There is NO stock posting and NO stock balance change or replenishment. A future controlled return-posting step must use the existing stock ledger once database tests pass.

## Limitations / deferred
- Single return request per handover in this checkpoint; multi-partial returns require a revised allocation policy.
- Stores receipt accepts a verified quantity up to the submitted amount. Short-receipt discrepancy workflow beyond this custody evidence is future work.
- No new return-specific UI form yet; API usable by a future Internal/Partner screen.
- Actual PostgreSQL migration, database concurrency, Docker end-to-end, frontend builds were not executed. Stock issuing and lot-writer cutover remain disabled by default.

## Validation executed
- `python -m pytest -q tests/test_stores_*.py` — 222 passed, 15 skipped.
- Python compilation passed.
- `python -m alembic heads` — `stores_phase5_return_custody_qa` (one head).
