# ZerroBuild integrated source — implementation and verification status

This package uses the original siteforge project as the base and includes previous dashboard/partner read-only endpoint changes plus one **new** audited external partner write workflow.

## New in this build
- `POST /api/partner/projects/{project_id}/purchase-orders/{po_id}/acknowledgments` — supplier submits an acknowledgment request for an **Issued** PO at an explicit version. Requires session, CSRF, active user and company membership and vendor/PO ownership. Does **not** modify the PO.
- `GET /api/partner/projects/{project_id}/purchase-orders/{po_id}/acknowledgments` — supplier views its PO acknowledgment requests.
- `POST /api/partner/internal/projects/{project_id}/acknowledgments/{ack_id}/review` — buyer with `procurement.po.edit` reviews an acknowledgment; approval invokes existing purchasing service, preserving version checks and audit events.
- Alembic migration `d5f9c3a72e08` for partner acknowledgment requests.

## Security and integration constraints
Existing internal procurement routes have **not** been audited for external company isolation. Do not deploy for external partners until an authorization test suite is completed against a configured PostgreSQL instance. No partner can directly approve a PO using these endpoints.

## Not implemented in this build
- Full cross-module drawing impact propagation and costing.
- RA billing certification, invoice matching and payment ledger integration.
- Complete partner write flows for RFQs, deliveries, and inspections.
- Cross-module integrated end-to-end tests and Docker runtime testing.

## Verification
Python syntax and ZIP integrity will be verified during packaging. They are not substitutes for DB migrations and live integration tests.

## Deployment
Back up existing DB and source. Configure `.env`, run migrations using the Compose migration service, then start with `docker compose up --build -d`. Inspect `docker compose logs migrate backend` and run controlled acceptance tests before enabling partner access.
