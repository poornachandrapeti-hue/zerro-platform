# Phase 4 — QA revocation concurrency checkpoint

## Changes
- `backend/app/domains/stores_inventory/router.py`: A QA case already marked `Quality Revoked` now refuses any NEW revocation. Identical idempotency-key retries still return their existing result; normal QA decisions were already blocked by the previous checkpoint. Reinspection/release remains a separate workflow (not implemented here).
- `backend/tests/test_stores_qa_revocation_concurrency_gate.py`: source contract checks on real lot-writer QA locking and three opt-in PostgreSQL row-lock protocol tests (accept/reserve/issue).

## Verification and limitations
- `python -m pytest -q tests/test_stores_qa_revocation_terminal_gate.py tests/test_stores_qa_revocation_concurrency_gate.py`: 5 passed, 3 skipped when PostgreSQL URL was not configured.
- To run the PostgreSQL protocol probes, export `STORES_TEST_DATABASE_URL` pointing to a disposable test DB with CREATE TABLE permission, then run the same command. The probes make isolated temporary tables; **they are not full application ORM/API concurrency tests**.
- Existing QA row locks and case version checks in the lot services are unchanged. No feature gates enabled, no inventory ledger mutation from this patch.
- Full application-level PostgreSQL transaction tests, QA revocation after partial issuance, construction impact remediation, Docker and Command Center runtime integration remain unverified.
