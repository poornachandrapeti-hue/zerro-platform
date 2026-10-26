# Stores approval dashboard integration contract — Phase 4 checkpoint

The embedded Command Center UI expects an authenticated GET `/command-api/api/projects/{project_id}/stores-approval-workload` endpoint on the separate Command Center backend.

The Command Center backend is NOT included in this archive; this endpoint is NOT operational until wired in that service. No browser service key or direct cross-system connection is permitted.

## Server-side implementation contract

1. Authenticate the viewer with the Command Center's existing session/auth handler.
2. Resolve the viewer's organization ID and the canonical ZerroBuild project ID from trusted server mapping (never trust a browser-supplied organization ID).
3. Recheck the viewer's *current* project entitlement via live grants on every request; return 403 for unauthorized scope.
4. Call `integrations/command_center/stores_approval_feed.fetch_stores_workload` with the server-only `COMMAND_CENTER_IDENTITY_SERVICE_KEY` and HTTPS `ZERROBUILD_API_URL`.
5. Serialize `organization_id`, `project_id`, `as_of`, `stale`, `pending_approval_count`, `past_required_date_count`, `partner_origin_pending_count`, `pending_without_active_task_count`, `overdue_active_task_count`, `physical_stock_readiness` from its validated result. Add `Cache-Control: no-store`.
6. Return 503 (not zero counts) on upstream failure, stale feed, mapping error, or unavailable live grants. Avoid leaking source credentials in error messages.
7. The UI rechecks timestamp, project, field types, and stale indicator and clears prior project/role figures on changes or outages. It refreshes at 60-second intervals.

## Boundaries

- Read-only approval workload; `physical_stock_readiness` always `Unverified`.
- Do not use issued material as installed progress.
- Do not wire the front-end directly to a service-key-protected ZerroBuild endpoint.
- Pending production validation: real live-grants integration, cross-org tests, 401/403/404/503, source outage, key rotation, Docker E2E, frontend build.
