# Stores Phase 4 — Material Readiness Exceptions

## Changes
- Added request-level `readiness_blockers` and `readiness_exception_count` to the existing work-package readiness read model.
- Added `GET /api/projects/{pid}/stores/material-requests/readiness-exceptions?work_package_id=...` for authorized internal project users, reusing the existing Stores request view authorization and work-package scope validation.
- Detects incomplete allocation, overallocated/inconsistent quantities, passed required dates, absent PO commitment, PO promises later than required, and unverified QA/physical inventory.
- Keeps PO promised date as a supplier commitment, never a confirmed ETA.
- The endpoint never posts material, approves issue, writes stock, sends notifications, or creates Command Center events.

## Tests
- Focused pure calculation tests: 3 passed.
- Python module compilation: passed.
- Live PostgreSQL, Docker API integration, frontend build, and concurrency tests: NOT performed.

## Remaining
- Verified lot-level physical balances and QA clearance in a unified stock service.
- Legacy Procurement transaction writer gating and live reservation/issue test coverage.
- Shared task routing/notifications and Command Center data delivery with tenant-scoped authorization.
- Required-date cross-validation against actual Planning scheduling dependencies.
