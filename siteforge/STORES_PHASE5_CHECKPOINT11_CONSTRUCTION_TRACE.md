# Phase 5 — Checkpoint 11: Construction work-package material trace

## Delivered

- Read-only `GET /api/projects/{pid}/stores/material-returns/construction-trace?work_package_id=...`
- Project/organization-scoped, authorized `stores.requests.view` users; non-admin users see their own request-linked records.
- Joins the canonical Stores request (approved Procurement requirement line / WBS / work package), actual issue posting line, handover, return custody and posted Return posting.
- `ledger_outstanding_quantity = posted issue quantity - confirmed ledger-posted return quantity`; QA-accepted-but-unposted returns are only `pending_custody_return_quantity`.
- Explicit `construction_consumption_verified=false` and `inventory_verified=false`. No inferred installation/consumption, no new ledger, no stock mutation.
- Fails closed for invalid source or posted return references; skips unavailable/unmapped handovers rather than presenting fabricated coverage.

## Validation

Five focused unit tests passed. Python compilation and package integrity checked. Live PostgreSQL / migration / Docker integration and cross-module UI integration remain deferred. Inventory writer cutover and return posting feature flags remain disabled by default.

## Outstanding

- Real PostgreSQL tests of the source joins and tenant scoping.
- Tie to a construction-installed/consumed evidence model only when that canonical model is identified and approved.
- Support multiple authorized partial returns per handover in a separately controlled design; present schema currently permits one.
- Consumer wiring to the separate Command Center backend with live viewer permissions.
