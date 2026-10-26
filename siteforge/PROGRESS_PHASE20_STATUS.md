# ZerroBuild Progress — Phase 20: Staging validation and release gate

## Phase 20 deliverables
- Added `siteforge/scripts/check_progress_release.py`, a non-destructive release gate to validate migration graph, run targeted Progress tests, check FastAPI application imports, and compile React frontend.
- Audited Alembic migration graph: 74 unique revision IDs, no missing parents, one head (`p18a1c4e7f725`). **This checks graph structure only; no migration was executed against PostgreSQL.**
- Confirmed 41 targeted Progress tests pass in the available Python environment.
- Confirmed full backend application import fails here because `psycopg` is not installed. This is an *environment dependency blocker*, not proof that application code is correct or incorrect.
- The frontend package has no `node_modules` or standard `package-lock.json` and offline dependency resolution fails (`ENOTCACHED`). Build remains unverified.
- The full backend test run did not complete inside the allotted check window. Its result is **unknown**, not passed.

## Release decision: NOT READY FOR PRODUCTION

The release gate deliberately exits nonzero if imports/tests/frontend build cannot be verified. No existing source-module tables were modified, and no database migrations were applied in this environment.

## Staging commands

```bash
cd siteforge/backend
python -m pip install -r requirements.txt
python -m pytest tests/test_progress_*.py -q
python -m alembic current
python -m alembic heads
# Review migration history and inspect schema before: python -m alembic upgrade head
cd ../frontend
npm install
npm run build
cd ..
python scripts/check_progress_release.py
```

Before any migration, back up staging PostgreSQL and check if older Phase 4 `progress_reports` migrations have already been applied, because Phase 8 changed table naming in source. Then complete project/company/discipline RBAC test matrix; published-report immutability and revision flow; approved engineering/procurement/construction E2E evidence; partner restrictions; worker deduplication/lock tests; and signed-off customer acceptance. Commissioning and Financials source integrations remain incomplete and must not be called implemented.
