# Stores Phase 4 — Command Center Server Adapter

## Implemented
- Added `integrations/command_center/stores_approval_feed.py`, a portable Python server-side feed client for the separately deployed Command Center backend.
- Calls the existing service-key-protected source endpoint: `GET /api/projects/{pid}/stores/internal-command-center/approval-workload`.
- Requires an affirmative viewer-project authorization decision from Command Center's existing **live-grants** check before fetching. This flag does **not** implement live-grants lookup; consumer must perform it.
- Validates source name, read-only flag, organization/project identity, timestamp and nonnegative integer workload counts.
- Marks data stale after a configurable threshold (default 300 seconds), rejects future timestamps and unsupported physical stock readiness assertions.
- Requires HTTPS; never expose the integration key to browser or embed it in the frontend.
- Fails explicitly when the feed is unreachable; does not display zero as a fallback.

## Integration handoff for separate Command Center backend
1. Place `integrations/command_center/stores_approval_feed.py` in the backend runtime, or package it as a shared internal library.
2. After the existing viewer authentication and `live-grants` verification, map the Command Center project to the canonical ZerroBuild project ID **and** organization ID.
3. Call `fetch_stores_workload(base_url=ZERROBUILD_API_URL, service_key=COMMAND_CENTER_IDENTITY_SERVICE_KEY, organization_id=..., project_id=..., viewer_authorized=True)` server-side.
4. Publish only the validated, permitted counts through an authenticated Command Center API. Include `as_of`, `stale`, and `physical_stock_readiness: Unverified`.
5. The UI must show stale/unavailable states, not a green ready indicator; refresh/project changes must revalidate live grants.
6. Configure HTTPS service-to-service communication and keep the service key in server environment secrets.

## Validation
- `python -m unittest discover -s integrations/tests -v` — 8 focused tests passed.
- `python -m compileall -q integrations/command_center integrations/tests` — passed.
- No real Command Center backend is included in this package; therefore no real dashboard route, live-grant lookup, or E2E ingestion is implemented.
- Live Postgres migrations, Docker deployment, frontend build and cross-service auth remain unverified.

## Still pending
- Wire the adapter into the **separate** Command Center backend, configure project mapping and live viewer grants, and render project-scoped approval workload.
- Test service key rotation, failure/retry and 403/404 paths in the real environment.
- Verify material availability against QA-cleared lot balances and legacy writers before publishing material readiness or enabling live stock operations.
