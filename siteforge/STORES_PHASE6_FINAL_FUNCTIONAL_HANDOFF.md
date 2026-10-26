# Stores & Inventory Phase 6 — Final Functional Handoff (Development)

## Decision
**Functional source handoff prepared; full functional and production closure NOT approved.** Phase 7 development can proceed independently while keeping all unvalidated physical stock mutation paths disabled.

## Developed source-level workflows
1. Same-project transfer request, independent approval, dispatch and destination receipt; discrepancy resolution and custody confirmation.
2. Inter-project transfer request and destination acceptance (custody only; atomic inter-project inventory movement pending).
3. Vendor return authorization, dispatch and Procurement-recorded vendor acknowledgment/replacement reference (vendor portal and replacement GRN not integrated).
4. Source transfer-lot planning, destination transfer-derived lot provenance, paired same-project ledger posting code, destination QA controls, reconciliation and allocation preview.
5. Approved-demand-linked transfer reservation intent, gated activation and release, gated physical issue, handover and Construction usage integration, gated returns, issue/return provenance reconciliation.
6. Internal transfer monitoring API/UI and secure read-only source feed for Command Center (separate runtime not connected).

## Verified in this package
- Offline source audit: **16/16 checks pass**; only one Alembic migration head.
- Focused Phase 6 regression run: **11 tests passed** (return provenance balance, destination-lot eligibility, reservation release contracts).
- These tests do **not** establish live stock safety.

## Deferred / open items (do not silently close)
- Actual PostgreSQL migrations, multi-session concurrency, rollback, ledger reconciliations and project-level isolation.
- Docker deploy and frontend TypeScript build, end-to-end UI roles and permissions.
- Inter-project atomic inventory transfer posting and transfer reversals.
- Original GRN provenance of legacy and unmapped movements; mixed-lot availability correctness under concurrency.
- Vendor replacement GRN linkage and live supplier acknowledgment.
- Connection to separate Command Center backend and per-viewer project authorization.
- QA clearance/issue/return flags and all physical stock mutation gates must remain disabled before validation.

## Reproduce
From `siteforge/backend`:

```bash
python tests/run_stores_phase6_handoff_audit.py
python -m pytest -q tests/test_stores_phase6_return_provenance_balance.py tests/test_stores_phase6_transfer_eligibility.py tests/test_stores_phase6_transfer_release_contract.py
```

See `STORES_PHASE6_FINAL_SOURCE_AUDIT.json` for machine-readable check results. These checks are intentionally not a deployment sign-off.
