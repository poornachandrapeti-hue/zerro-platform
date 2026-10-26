# Stores Phase 4 — Command Center HTTP Integration Gate

## Delivered in this checkpoint
- Added HTTP-level tests for the drop-in Command Center FastAPI Stores route with a mocked internal Stores feed and a live-grant callback fixture.
- Verified success response, tenant/project scope passed to upstream, no-cache header, security of the server-side service key, access denied before upstream fetch, and fail-closed behavior for stale and unavailable feeds.
- Hardened failed/stale feed responses to use `Cache-Control: private, no-store` as successful responses already did.
- Kept physical stock readiness `Unverified`: the integration only reports approval workload, not QA-cleared stock, physical issue, installation or progress.

## Verified
- `python -m pytest -q integrations/tests/test_stores_workload_router_http.py integrations/tests/test_stores_workload_router.py integrations/tests/test_stores_approval_feed.py` -> **18 passed**.
- Python compilation for changed integration files -> passed.
- ZIP integrity -> passed when packaged.

## Not verified / outstanding
- The actual separately deployed Command Center backend is NOT included in this repository. The router still needs to be installed there with its genuine authenticated-viewer/project-grant resolver; no fake resolver should be deployed.
- Live PostgreSQL, real HTTP service-to-service, frontend TypeScript build and Docker E2E tests have not been verified here.
- Approval escalation worker runtime and real notification delivery still require tests.
- Legacy Procurement stock routes, QA/lot reconciliation, and live reservations/issues must pass runtime safety tests before activation. Do not remove feature gates.

## Next implementation dependency
Mount the router in the separate Command Center backend, supply current viewer-to-project entitlement mapping, configure the service secret, and run allowed/denied/wrong-tenant/stale/downstream-outage tests in staging.
