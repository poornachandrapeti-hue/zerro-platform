# Stores Phase 4 — Procurement and Planning Context Checkpoint

## Implemented
- Extends work-package readiness report with work package planned start/finish.
- Adds schedule alignment indication between material required date and work-package planned start.
- Traces linked PO commitments using authoritative requirement line → purchase requisition line → purchase requisition → RFQ → PO foreign keys.
- Scopes PO and requisition links to the authenticated organization and project.
- Returns PO number/status/promised date as a supplier **commitment**, not verified arrival or QA release.
- Preserves existing Stores approved-request/reservation lifecycle and marks physical workfront readiness `Unverified`.
- No changes to stock postings, ledger balances, QA release, approval flows, or material requirements.

## Important limits
- A PO may include several requisition lines. The report shows linked purchase orders, **not** a guaranteed quantity against each individual requirement line.
- No goods-receipt/accepted quantity is assigned to a requirement line by this API.
- Historical or migrated data with broken RFQ or requisition links will not appear as a commitment.
- Planning precedence beyond planned start/finish, delivery reliability, lead times, actual QA-cleared lot availability, and task notifications are not validated by this checkpoint.
- Live PostgreSQL/SQLAlchemy execution, Docker startup, frontend build, and concurrency tests remain pending.

## Verification
- `python -m py_compile app/domains/stores_inventory/material_requests.py` passed.
- `python -m pytest tests/test_stores_readiness_commitment_contract.py -q` — 4 source-contract checks passed.

## Next
- Verify these joins against actual migrated database data and improve PO-line-to-requirement quantity attribution.
- Integrate verified QA eligible balance and receipts; implement approval-task notification delivery through existing task service.
- Keep reservation/issue feature gates off until legacy posting routes and live database concurrency checks pass.
