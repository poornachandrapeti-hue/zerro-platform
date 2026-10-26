# Stores Phase 8 — Checkpoint 9: Integration reliability

## Delivered
- Hardened `integrations/command_center/stores_phase8_exceptions.py` read-only service adapter.
- Validates HTTPS root origins, disallows URL credentials, paths, query strings, loopback and direct non-global IP destinations.
- Bounds upstream JSON to 512 KiB and maps transport/parse/oversized errors to a generic feed-unavailable exception.
- Adds `classify_feed_health` for available / degraded / stale / unavailable / invalid-clock monitoring; no fabricated zero counts.
- 15 new reliability tests; 26 adapter and reliability tests total passed on 2026-10-24.

## Important limitations
- This does not create the missing separate Command Center backend route or integrate its persistent project authorization/mapping.
- URL validation does NOT eliminate DNS rebinding or enforce TLS trust, network egress allowlisting, or redirect policy. Production should use explicit domain allowlisting, outbound firewall, and redirect suppression.
- Health helper is not yet wired to persistent monitoring; source remains polled and read-only.
- Docker/PostgreSQL, end-to-end API, UI TypeScript build and deployed Command Center validation have not been run.
- No inventory mutations, accounting postings, or QA/billing certification authority added.

## Next deployment actions
1. Mount the separate Command Center backend repository, add the authenticated project-scoped endpoint described in Checkpoint 8.
2. Enforce HTTPS egress allowlist and no redirects in the production HTTP client.
3. Expose health classifications without leaking service keys or returning false zero counts.
4. Run actual Docker Compose with seeded projects and unauthorized access scenarios.
