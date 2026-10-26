# Stores Phase 8 — Checkpoint 3: Planning Material Readiness

Read-only project-scoped `GET /api/projects/{pid}/stores/phase8/planning-material-readiness` with optional `work_package_id` and `limit` (1–500).

Uses canonical Stores requests, Construction work-package planned start, original Procurement-linked PO promised dates, and existing allocation read model. Flags administrative and schedule mismatches; **never** claims live stock availability, verified shipment, confirmed construction progress or financial amounts. Incomplete request scopes are labelled rather than silently assumed ready. No migration or inventory writer changes.

Run: `cd backend && python -m pytest -q tests/test_stores_phase8_planning_readiness.py`.

Deferred: database/Docker execution, Planning/Command Center dashboard wiring, physical QA-cleared availability, and authoritative PO actual delivery confirmation. Continue keeping inventory posting feature flags disabled.
