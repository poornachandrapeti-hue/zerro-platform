# Stores Phase 4 — PostgreSQL concurrency test gate

## Delivered
- Added `backend/tests/test_stores_postgres_concurrency_gate.py` with opt-in, real-PostgreSQL concurrent issue, reservation, retry/payload conflict, and transaction rollback checks.
- Uses unique, isolated temporary test tables; does not modify operational inventory or require feature flags to be enabled.
- The test verifies the **database transaction protocol**, not full application-service correctness. A passing result must not be treated as authorization to activate issue/reservation cutover.

## Run against a dedicated disposable test database
```bash
cd siteforge/backend
python -m pip install -r requirements.txt pytest
export STORES_TEST_DATABASE_URL='postgresql+psycopg://TEST_USER:TEST_PASSWORD@localhost:5432/zerro_stores_test'
python -m pytest -q tests/test_stores_postgres_concurrency_gate.py
```
This database login needs CREATE TABLE privileges; never point the tests at production. Do not commit credentials.

## Remaining release blockers
1. Run Alembic migrations and seed users/projects/PO/GRN/QA/receipt lots in a disposable clone.
2. Exercise **application** `reserve_lot`, `accept_lot`, `issue_lot` via their authorized endpoints with two concurrent clients, and inject rollbacks to verify that both posted ledger line and lot allocation rollback together.
3. Test QA acceptance revocation, expiry, same-key altered payload, release/reassign, and legacy routes while cutover is selected.
4. Validate every other stock writer outside `stock.py`, including bulk import, scheduled jobs and direct ORM updates.
5. Frontend build, portal authorization, and full Docker E2E tests.

## Safe default flags
`STORES_LOT_WRITER_CUTOVER=false`; `STORES_LOT_RESERVATIONS_ENABLED=false`; `STORES_ATOMIC_LOT_ISSUE_ENABLED=false`.
