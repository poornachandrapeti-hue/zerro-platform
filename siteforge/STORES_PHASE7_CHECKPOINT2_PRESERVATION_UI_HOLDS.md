# Phase 7 — Checkpoint 2: Preservation Inspection UI and GRN-Lot Holds

Implemented:
- Stores > Preservation & Expiry tab for plan entry, due/expiry visibility, inspections, and recent inspection history.
- Authorized plan/check API reused; added project/organization-scoped read-only inspection history endpoint (latest 100 checks).
- Existing GRN receipt-lot reservation and atomic issue services now reject recorded Quarantined, Attention, overdue, or unrecognized preservation conditions. The plan is row-locked during the check.
- No physical stock movements, reservation activation, or feature-flag changes.

Important limitations:
- A missing preservation plan does **not** automatically block previously registered receipt lots (legacy plan coverage must be audited before production); it does not imply clearance.
- Expiry-date checks already existed in GRN-lot reservation/issue paths; this checkpoint adds preservation condition and inspection due-date checks.
- Transfer-derived lot writers and legacy inventory paths are **not** covered by these new preservation holds yet.
- Existing plan condition 'Good' is a preservation check, not substitute for QA release.
- Frontend compile, PostgreSQL migrations, live Docker integration, and transaction races were not validated here.
- The preservation list and inspection history are bounded (500 plans, 100 checks).

Verification: `python -m pytest -q tests/test_stores_phase7_preservation.py tests/test_stores_phase7_preservation_holds.py` => 12 passed.

Next: physical stock cycle-count plan and reconciliation workflow with independent verification; extend holds to all legacy/transfer-derived stock paths before activation.
