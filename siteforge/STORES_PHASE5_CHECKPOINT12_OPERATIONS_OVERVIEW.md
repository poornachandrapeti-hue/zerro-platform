# Stores Phase 5 — Checkpoint 12: Consolidated Operations Overview

Implemented the authenticated GET `/api/projects/{pid}/stores/phase5/operations-overview` route and the `Phase 5 Overview` tab in the existing Internal Stores screen.

The API combines authoritative request/work-package references with existing handover and return custody stages. It reports stage counts only for the latest 300 project handovers. Non-admin requesters are restricted to their own request-linked handovers. No cross-unit quantities are summed. It explicitly marks inventory and Construction consumption as unverified; it makes no stock mutations.

The UI shows counts and per-handover request/work-package references, return status, and explicit return posting IDs. It shows an unavailable state rather than invented metrics.

Test assertions: `tests/test_stores_phase5_operations.py`: three passed; the pytest process subsequently did not exit before the command timeout. Python syntax compilation passed. Full frontend TypeScript build, PostgreSQL integration and Docker validation were not performed. The existing live stock posting gates remain disabled. This checkpoint does not certify Phase 5 for production.
