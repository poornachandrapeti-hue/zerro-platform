# Stores Phase 8 — Checkpoint 7: Command Center exception snapshot

Adds a read-only service-to-service snapshot endpoint:

`GET /api/projects/{pid}/stores/internal-command-center/phase8-exception-snapshot?work_package_id=&limit=200`

- Uses existing `X-ZerroR-Service-Key` against `COMMAND_CENTER_IDENTITY_SERVICE_KEY` with constant-time comparison, denies absent configuration/key, resolves organization from canonical project.
- Reuses Checkpoint 6 project's bounded (1..500) scoped audit query. Produces schema_version 1, project/org identifiers, timestamp, coverage, count by exception code and per-request exception summaries.
- Response does not expose individual handover/return/usage IDs, and avoids claiming external inspection, finance authority or billing certification.
- Intended for Command Center **polling**, not a durable push, event delivery or automatically populated dashboard.
- No migrations, duplicated stock ledgers, adjustment, posting, or billing state changes.

## Run tests

`cd backend && PYTHONPATH=. pytest -q tests/test_stores_phase8_cross_module_audit.py tests/test_stores_phase8_command_center_snapshot.py`

## Integration still required

1. Connect an actual Command Center backend client to this authenticated endpoint, with secret managed as environment configuration; implement secure network routing, request deadlines, retry, observability and project authorization.
2. Build downstream widget / historical persistence or alerts where approved. Polling snapshots are bounded, not complete totals or guaranteed-delivery events.
3. Authenticate Zerro-R signatures separately; establish financial and billing authorities separately.
4. Live Docker/PostgreSQL verification and cross-organization access tests.
