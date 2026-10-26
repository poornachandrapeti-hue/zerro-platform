# Stores Phase 8 — Checkpoint 8: Command Center exception dashboard integration

## Delivered in this package

- New server-only, timeout-bounded, HTTPS authenticated snapshot client: `integrations/command_center/stores_phase8_exceptions.py`.
- Strict organization/project matching, freshness, response contract, negative authorities, bounded rows, and totals validation.
- Embedded Command Center dashboard now attempts `/command-api/api/projects/{projectId}/stores-phase8-exceptions` and shows source window, code counts and affected request/work package rows only after validation.
- Clears figures on project/role changes and feed failures, polls every 60 seconds. No browser service secret.
- 11 isolated adapter tests.

## IMPORTANT: Separate Command Center backend is NOT in the uploaded ZIP

This UI endpoint does **not** yet exist in this source package. Wire it into the actual separate `command_backend`:

1. Authenticate Command Center user/session and resolve CURRENT organization and project grants (server-side only); reject unauthorized with 403.
2. Resolve approved canonical mapping to ZerroBuild project and organization; do not accept browser-provided org or project mapping at face value.
3. `fetch_phase8_exceptions(base_url=ZERROBUILD_API_URL, service_key=COMMAND_CENTER_IDENTITY_SERVICE_KEY, organization_id=resolved_org_id, project_id=resolved_zerrobuild_project_id, viewer_authorized=True)`.
4. Return JSON from adapter and `Cache-Control: no-store` for `GET /api/projects/{projectId}/stores-phase8-exceptions`. If Command Center project ID differs from ZerroBuild ID, map response `project_id` to authorized Command Center ID only after validating source scope; prefer canonical IDs where possible.
5. Return 503 on source exception, timeout, or stale sample; 403 on unauthorized, 404 if no mapping. Never return zero counts on failure. Do not log service key.
6. Deploy server-only key and HTTPS URL to the separate service environment; never expose in browser/frontend variables.

## Boundaries

Not durable event delivery, not inspection attestation, financial posting authority, billing certification, complete-history reconciliation, or project-wide exception counts. No Postgres/Docker live test performed. Frontend TypeScript build not validated here without installed node_modules.
