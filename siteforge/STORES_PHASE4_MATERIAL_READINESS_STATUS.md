# Stores Phase 4: advisory material readiness and approval queue

## Added
- GET /api/projects/{pid}/stores/material-requests/work-package-readiness?work_package_id=...
- GET /api/projects/{pid}/stores/material-requests/approval-aging
- Pure allocation-status classification, distinct from QA-cleared stock availability.
- Project-scoped read permissions; reviewer-specific permission for approval aging.

## Intentional limitations
- No PO promise matching: PurchaseOrderLine lacks an authoritative requirement-line association in this endpoint.
- No claim of available/issued/installed/earned progress beyond existing reservation lifecycle.
- No outgoing notifications or SLA escalation events (requires notification service wiring).
- Stock posting/reservations remain behind existing gates.
- Run live DB, frontend, and Docker tests before enabling operations.
