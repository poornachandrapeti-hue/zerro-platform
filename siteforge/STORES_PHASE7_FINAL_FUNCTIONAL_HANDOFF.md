# ZerroBuild Stores & Inventory — Phase 7 Functional Handoff

## Handoff decision
Phase 7 preservation, cycle-count, adjustment-review, scrap/disposal-evidence and operational-monitor **source workflows are ready for development handoff**, but Phase 7 is **not fully functionally closed or production-ready**. In particular, accounting-grade variances and stock write-offs remain unimplemented/unvalidated. Physical stock-changing feature gates must stay disabled.

## Implemented source workflows
| Workstream | Source-level coverage | Known restriction |
|---|---|---|
| Preservation/expiry | Receipt-lot plans, schedules, independent inspection evidence, history, due/overdue monitoring, GRN lot holds | Unplanned lots and transfer-derived lots are not comprehensively held; legacy writers require coverage |
| Cycle counts | Create count sessions, enter receipt-lot physical counts, submit, independent review/recount | No authoritative point-in-time lot-level stock snapshot; no automatic adjustment |
| Variance reconciliation | Read-only ledger-context view with explicit blocked/unverified status | Cannot certify book variances from original receipt quantities |
| Adjustment requests | Evidence-backed requests, independent reject/recount/blocked review, audit trail | Approval to post and ledger posting intentionally disabled |
| Scrap and disposal | Receipt-lot proposals, independent review and disposal evidence | No legal disposal certification or stock write-off |
| Monitoring | Bounded Internal Stores screen and secured read-only source feed for Command Center | Latest 500 records per workflow, not all-time; separate Command Center backend unconnected |

## Actual checks executed at handoff
- `cd backend && python -m pytest -q tests/test_stores_phase7_*.py`: **30 passed**, 0 failed, 0 skipped (offline focused suite).
- `python backend/tests/audit_stores_phase7_handoff.py`: **9/9 checks passed**, one Alembic migration head.
- Python syntax compilation and ZIP integrity should be validated for the packaged artifact; these do not replace application startup or database migration execution.

## Deferred release gates (mandatory before activation)
1. PostgreSQL migration execution and transaction/concurrency tests in an isolated, migrated database.
2. Point-in-time lot-level inventory snapshot and complete GRN plus transfer-derived count coverage, with actual movement reconciliation.
3. Correct approval of verified variances and atomic, authorized stock adjustment posting to the existing stock ledger.
4. Scrap quarantine, disposal compliance and authorized stock write-offs with reconciled lot provenance.
5. Preservation and expiry holds across GRN, transfer-derived, legacy and every alternate allocation/issue path.
6. Frontend TypeScript build and actual role-by-role UI/API testing; Docker end-to-end test.
7. Separate Command Center backend integration with live per-viewer project authorization and freshness/error handling.

## Next development
Proceed with Phase 8 requirements-defined functionality if desired, carrying the above items as a tracked backlog. Do not label Phase 7 production-ready or turn on stock-mutating flags merely because offline tests pass.
