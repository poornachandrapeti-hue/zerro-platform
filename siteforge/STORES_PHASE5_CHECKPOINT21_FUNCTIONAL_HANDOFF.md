# ZerroBuild Stores — Phase 5 Checkpoint 21 Functional Handoff
Date: 2026-10-23

## Decision
**Phase 5 feature-development handoff is prepared; operational and production acceptance are NOT complete.** The next requirements-defined workstream is Phase 6: transfers, in-transit, vendor returns/replacement and owner custody. The user elected to defer live PostgreSQL/Docker validation; deferral is not a test pass.

## Scope and original acceptance gate
Integrated Requirements v2, section L, defines Phase 5 as **issues, signed partner handoff, site returns, Construction consumption links**. Exit gate: **issue vs install separation tested**.

## Verified in current source archive
- Material handover, contractor acknowledgment, discrepancy review: mounted API routes.
- Return request, physical receipt, independent QA disposition, bin placement, gated stock return posting: mounted API routes.
- Construction-specific material usage, independent QA verification and separate QA queue: mounted API routes.
- Construction manager work-package material balance: mounted API route and UI source present.
- Return stock mutation has both `STORES_ATOMIC_LOT_RETURN_ENABLED` and `STORES_LOT_WRITER_CUTOVER` gate references.
- Source-only functional gate `backend/tests/run_stores_phase5_functional_gate.py`: 18/18 passed on 2026-10-23. Generates `backend/stores_phase5_functional_gate.json`.
- Focused regression suite (handover, material usage, manager balance): 24 passed, 1 deprecation warning.

## Functional rules maintained
- Original Procurement material requirement remains authoritative; Stores material requests do not create competing demand.
- Existing stock ledger remains the only stock posting source; custody/discrepancy/Construction evidence must not alter inventory balances implicitly.
- Issue, acknowledged receipt, return custody, ledger-posted return, consumed evidence and installed evidence are represented distinctly. Construction progress % does not imply consumed quantity.
- QA approval does not by itself make a return available for use.
- Physical stock readiness must remain `Unverified` pending validation.

## Open items to carry forward — do not treat as completed
1. **Live database validation**: transactions, locking/idempotency, migration execution, rollback, concurrent issue/return/QA revocation, reconciliation. Deferred by user.
2. **Frontend compilation and UI E2E**: TypeScript/Vite build, contractor and Construction manager workflows, browser authorization tests. Not verified this checkpoint.
3. **Runtime Command Center integration**: separate Command Center backend not present in the source package; read-only feed and components are not a deployed connection.
4. **Actual signature/evidence acceptance**: signed handoff acceptance test and supporting attachments should be verified with the deployed partner workflow. Source-level acknowledgment is not equivalent to a verified cryptographic signature.
5. **Cross-module operational UAT**: Procurement → Stores → Partner → QA → Construction, event notifications, replay, financial/contractual effects and mixed-unit reconciliation.
6. **Safe activation**: stock issue and return posting and lot-writer cutover flags must remain OFF until final database and process checks pass.

## Phase 6 proposed scope
Per Integrated Requirements v2 section L: Inter-warehouse and inter-project transfer; dispatch/in-transit/receipt/discrepancy; vendor returns and replacement; owner-versus-custodian checks. Use shared ledger and existing schemas/RBAC. No production enablement without deferred release gates.

## Commands for repeatability
```
cd siteforge/backend
python tests/run_stores_phase5_functional_gate.py
python -m pytest -q tests/test_stores_phase5_material_handovers.py tests/test_stores_phase5_manager_balance_access.py tests/test_stores_phase5_material_usage_contract.py
```
The static gate inventories source routes; it is not a runtime security or database test.
