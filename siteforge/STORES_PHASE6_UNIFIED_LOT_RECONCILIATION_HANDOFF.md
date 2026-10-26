# Phase 6 — Unified transfer lot issue/return reconciliation

## Implemented
- Phase 5 Construction manager/requester material-balance and return-trace endpoints now batch-load project/organization-scoped transfer issue and return allocations from the existing provenance tables.
- For transfer-derived posted issues, report the transfer destination lot ID and issue origin; reject partial or mismatched issue provenance quantities.
- For ledger-posted returns from a transfer-issued lot, require one associated posted return line and an allocation matching the original issue line, destination lot, and posted returned quantity. Fail closed with 409 if provenance is inconsistent or missing.
- A custody-only return does not reduce ledger outstanding quantity. Existing QA-verified Construction usage remains separate.
- Retain explicit `physical_inventory_verified: false` reporting. Original GRN/legacy issues are labeled **GRN / legacy unverified**, not declared fully provenance verified.

## Validation
- Focused Python tests executed (see accompanying test file); PostgreSQL/Docker and frontend build not executed.
- Transfer posting, reservation activation, physical issuing and return posting flags remain disabled.

## Open Phase 6 items
- End-to-end database concurrency, migration execution, transfer-derived reserve/issue/return posting validations.
- Original GRN return provenance verification in this read model, handling of unmapped historical movements, and transfer reversal scenarios.
- Separate Command Center runtime integration, vendor replacement GRN and inter-project atomic stock posting remain pending.
