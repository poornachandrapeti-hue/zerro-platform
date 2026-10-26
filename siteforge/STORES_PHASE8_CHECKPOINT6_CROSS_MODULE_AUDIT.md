# Phase 8 Checkpoint 6 — Cross-Module Exception Audit

Added read-only `GET /api/projects/{pid}/stores/phase8/cross-module-audit?work_package_id=&limit=200`.

- Uses existing Stores material requests, handovers, returns, construction usage, and Contracts obligation links.
- Scopes the requested material requests, handovers, returns, usage and contract references to the caller's organization and project, under `stores.requests.review`.
- Returns per-request and per-handover exception flags for missing requirement/issue/contract evidence, return references requiring review, non-verified or mismatched construction usage, and missing finance/certification authority.
- Provides exception counts and explicitly marks all Finance / external Zerro-R / billing conclusions unverified.
- No database migrations, new duplicate ledgers, mutations, journal entries, physical movement, or automatic billing.

## Not implemented (explicit dependencies)

1. Zerro-R signed inspection callbacks and validation (external service contract and auth).
2. Authorized Finance cost attribution, valuation, journal and billing proof.
3. Command Center runtime ingestion and durable delivery/replay.
4. Cross-table quantity reconciliation/return overage assertion, which require authoritative stock quantities and posting status joins; this endpoint intentionally flags references only.
5. Docker/PostgreSQL live integration validation.

## Smoke test

`cd siteforge/backend && PYTHONPATH=. pytest -q tests/test_stores_phase8_cross_module_audit.py`

Audit endpoint is an exception review aid, not an approval gate and not evidence of full financial reconciliation.
