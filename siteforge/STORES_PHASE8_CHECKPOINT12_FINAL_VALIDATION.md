# Stores Phase 8 — Checkpoint 12: Evidence-based End-to-End Validation & Sign-off

## Scope
This checkpoint adds a **fail-closed sign-off report**. It does not alter physical stock, accounting, QA approvals or billing certifications. An offline test result is never proof of live production integration.

## Run
From `siteforge`:

```bash
python -m pytest integrations/tests/test_phase8_*.py -q
python -m integrations.command_center.phase8_deployment --preflight
python -m integrations.command_center.phase8_signoff --output phase8_signoff.json
```

The sign-off command returns code **1** (blocked) until required external evidence is provided; this is expected. A blank run is a conservative status report, not a failure of the tool.

Provide operator-verified results as an explicit JSON map (bool values only), e.g. `{"source_tests":true,"frontend_build":false}`; supply it via `--evidence verified_checks.json`. Do **not** assert true based only on code review.

## Mandatory live checks before closure
- Source automated tests and frontend TypeScript build pass.
- Existing PostgreSQL schema/migrations checked against the running Docker environment.
- Docker services, logs and readiness probes work.
- Source feed smoke validates authenticated retrieval for an authorized project.
- Separate Command Center backend route actually exists and enforces authenticated viewer permissions.
- Cross-organization access denied, including mismatched project IDs and missing grants.
- Canonical organization/project mapping confirmed with production-like records.
- Zerro-R QA source of truth is reconciled, without treating missing approvals as accepted.
- Finance valuation reconciles against its authoritative postings without duplication.
- Recovery, alerts, logs and feed-freshness monitoring exercised.

## Current assessment
The uploaded archive contains a Command Center adapter and embedded UI, but **not** the separate Command Center backend implementation. No live Docker, database, network smoke, RBAC or QA/finance authority validation has been carried out here. Accordingly **Phase 8 remains BLOCKED for operational sign-off**. Source-level validation results should be recorded separately.
