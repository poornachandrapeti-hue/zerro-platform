# Phase 5 Checkpoint 8 — Return Exception Monitoring

## Implemented
- Internal read-only `/api/projects/{pid}/stores/material-returns/exception-monitor` endpoint, tenant/project scoped and permission gated.
- Conservative classification of 500 most recent return records into pending Stores receipt, pending QA, quarantine, rejection, pending bin placement, pending gated posting, and posted but unverified.
- Embedded Internal Stores screen monitor showing all category counts and an explicit unverified physical stock status.
- Unit tests for states, unknown status and posted-but-unverified state.

## Limitations
- The summary is for the most recent 500 returns; **not** an all-time total, verified inventory quantity, or location-specific balance.
- Does not connect to the separately deployed Command Center backend. This endpoint may be consumed by an authorized server-side integration after project authorization.
- No stock mutation or flag activation. PostgreSQL migration/runtime, production deployment and TypeScript build remain unverified.
- Focused tests printed 7 passed but command timed out after output; do not call the command a clean completed test run.
