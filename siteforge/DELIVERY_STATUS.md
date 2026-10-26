# ZerroBuild integrated source — implementation status

This archive merges the original siteforge-derived Phase 2 UI with the partner security foundation and additional partner-safe, read-only API endpoints. It is **NOT** a production-ready implementation of all requested workflows.

## Implemented in this delivery
- Existing FastAPI app, React UI, business domains and Docker Compose configuration retained from the baseline.
- Redesigned internal home and role-view partner portal from the earlier UI phase.
- Partner company + active project-company + active user membership checks for partner API routes.
- Project/company-scoped read-only APIs: GET `/api/partner/context`, `/api/partner/projects`, `/api/partner/projects/{project_id}/overview`, `/api/partner/projects/{project_id}/transactions?kind=rfqs|quotations|purchase_orders|invoices|work_packages`, `/api/partner/projects/{project_id}/trace/drawings/{drawing_id}`.
- Partner UI has real transaction counts and items for the selected project (where authorized).
- Python syntax compilation succeeded for the new backend routes.

## Not implemented or verified
- External-partner self-registration, invitations, per-resource writable authorization, bid/quotation submission, PO acceptance, document uploads.
- Detailed cross-system change propagation and full downstream financial/schedule impact calculation.
- Full drawing-to-QA-to-payment trace chain, RA billing certification, invoice matching, bank payment processing and payment ledger.
- Full API/database integration tests, browser tests, Docker build verification; dependencies and a running PostgreSQL server are not available here.
- The older internal API routes have NOT been security-audited for partner access; this is a release blocker for exposing the partner UI to third parties.

## Safety notes
Do not deploy to external vendors until the internal routes are restricted or partner usage is isolated. Partner role tabs are visual filters, not entitlements. Do not interpret a recorded invoice as paid.

## Local Docker start
Copy this directory to the target computer. Create `.env` from `.env.example` and set your own secrets. Run `docker compose up --build -d`, inspect `docker compose ps -a`, and follow `docker compose logs -f backend frontend migrate`. See original README for bootstrap and env settings.
