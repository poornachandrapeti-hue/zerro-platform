# Stores Phase 8 — Checkpoint 10: Integration Verification Safeguards

## Implemented in source
- Default urllib transport uses a redirect-blocking handler, preventing credential forwarding on HTTP 3xx.
- Optional strict `allowed_origins` pinning refuses a mismatched origin before any outbound call. **Deployment must provide an explicit configured allowlist.**
- `verify_project_mapping` fail-closed helper checks authenticated viewer authorization and exact organization/project mapping before calling the source. **The separate Command Center backend must invoke it using independently resolved grants and mappings, not browser-supplied IDs.**
- Existing schema/authority/freshness validation remains intact, as do read-only semantics.
- 35 focused adapter/reliability/security tests passing.

## Not completed (requires external deployment/repository)
- Missing standalone Command Center backend route and project grant resolver; helper is not yet wired into that app.
- Docker PostgreSQL seeded end-to-end/API tests; deployed identity and service-key verification.
- Frontend TypeScript build and live UI walkthrough.
- DNS pinning and egress firewall allowlisting. Runtime SSRF controls require network and DNS policy enforcement.

## Operational validation checklist
1. Configure allowlisted HTTPS source origin on Command Center service, not user input.
2. Resolve browser viewer grant and canonical mapped source IDs from Command Center database.
3. Call `verify_project_mapping` before `fetch_phase8_exceptions` with the resolved values.
4. Reject mismatched organization/project, revoked grant, missing service key, 3xx, 401/403, 5xx, malformed, oversized and stale snapshots; never display fake zero counts.
5. Verify source freshness and exceptions in seeded projects across both backend services.
6. Verify service key is absent from browser network requests, logs and JSON responses.
7. Run PostgreSQL/Docker and TS build gates before considering deployment complete.
