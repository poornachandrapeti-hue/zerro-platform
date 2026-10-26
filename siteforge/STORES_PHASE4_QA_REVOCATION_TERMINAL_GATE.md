# Phase 4 — QA revocation terminal hold

## Change
- Ordinary inspection disposition decisions may not reopen a `Quality Revoked` case. Identical retries of an already recorded decision still return the existing case, without mutation.
- Acceptance, reservation and issue now accept only the recognized QA case workflow statuses (`Pending Inspection` and `Disposition Recorded`); revoked or unexpected statuses fail closed.
- All three physical paths still check case-version-linked QA lot attributions and lock the inspection case row. Revocation itself takes the same row lock, bumps the case version and holds the case.

## Limitations / release gate
- This is an application-source correction, NOT proof of a successful PostgreSQL concurrent revocation test.
- Do not enable STORES_ATOMIC_LOT_ISSUE_ENABLED or lot-reservation cutover until real PostgreSQL and full cross-module tests pass.
- No automatic reinstatement of revoked quality cases; an explicit authorized reinspect/release workflow remains future work.
- Running `pytest` from `siteforge/backend` verifies source tests. Database tests require a dedicated disposable PostgreSQL database.
