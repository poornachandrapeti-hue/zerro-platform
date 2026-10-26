# Stores Phase 4 — Secure Command Center Approval Feed

## Added
- Internal service-to-service GET `/api/projects/{pid}/stores/internal-command-center/approval-workload`.
- Uses existing `X-ZerroR-Service-Key` + `COMMAND_CENTER_IDENTITY_SERVICE_KEY` configuration and constant-time comparison.
- Project/organization-scoped read-only counts: pending approvals, overdue requirements, partner-origin requests, pending requests with no active shared approval task, and overdue active approval tasks.
- UTC `as_of` timestamp and explicit `Unverified` stock-readiness fields. No physical stock claims, ledger writes or partner data exports.
- Three focused source-contract regression checks.

## Not yet complete
- Actual consumer routes/cards in the **separate** Command Center backend, which is not included in this source ZIP.
- Per-viewer live grant filtering must be enforced by Command Center before showing source feed data.
- Automatic task escalation and dispatch: policies, designated recipient mapping, SLA settings, duplicate suppression and notification workers are not wired yet.
- PostgreSQL, Docker, security integration and frontend builds have not been executed in this environment.
- Lot-specific stock and issues remain gated pending full database validation.

## Suggested next integration
1. Add Command Center backend collector with service key kept server-side (never browser-exposed).
2. Recheck viewer live project grants and cache with `as_of`/stale indicators.
3. Configure project-specific reviewer delegation/escalation policy in shared coordination service; create notifications only against approved recipients.
4. Test unauthorized service call (403), cross-tenant project grants, duplicate task suppression, retries, and stale feeds.
