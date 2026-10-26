# Phase 4 — Lot Issue Aggregate Balance Safety

## Change
Atomic lot issue now rejects negative/corrupt aggregate stock, reserved quantities beyond on-hand, physical over-issue, and reservation-backed issues that exceed aggregate reserved quantity, before any stock or reservation decrement. The existing inventory ledger and QA/cutover gates remain intact.

## Verification
`cd backend && python -m pytest -q tests/test_stores_issue_balance_invariants.py tests/test_stores_atomic_lot_issue_unit.py tests/test_stores_action_key_serialization_pg.py` yielded 11 passed, 2 skipped (the skipped tests require a configured PostgreSQL database). Python compilation passed.

## Release constraints
Not ready for live material issue. PostgreSQL application integration, legacy cutover, QA concurrency, and Docker end-to-end validation remain outstanding. No runtime feature flags were enabled.
