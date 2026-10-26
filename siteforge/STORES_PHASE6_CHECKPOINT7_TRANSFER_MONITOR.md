# Phase 6 Checkpoint 7 — Transfer monitoring and Command Center feed

## Implemented
- Read-only Internal Stores transfer custody monitor (`GET /api/projects/{pid}/stores/material-transfers/monitor`).
- Service-key-authenticated source feed (`GET /api/projects/{pid}/stores/internal-command-center/transfer-monitor`).
- Transfer custody summary on Internal Stores transfer tab.
- Organization/project scoping, timestamp and clear freshness/coverage metadata.
- In-transit, pending approval, open/escalated discrepancy, and pending custody confirmation counts.
- Configurable aging threshold (1–720 hours, default 48).

## Accurate limitations
- Transfer dispatch time is not stored in the current transfer model. The overdue indicator is a **request creation age proxy**, not actual dispatch-to-receipt aging.
- The monitor covers the most recent 500 source-project transfers only; it does not represent all-time transfer counts.
- Independent Command Center backend not included in this package and is **not connected**. It must enforce viewer authorization before proxying the service feed.
- Physical inventory and atomic transfer posting remain disabled. No posting gates or inventory balances were changed.
- PostgreSQL and Docker integration and frontend build remain deferred/unverified.
