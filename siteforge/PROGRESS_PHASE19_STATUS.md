# Phase 19 — formatted Progress report exports

## Implemented
- Two authorization-gated GET endpoints under the existing Progress report router for XLSX and PDF.
- Excel sheets for summary, activities, approved planning targets and data-quality exceptions.
- PDF sections with report identifiers, baseline revision, cutoff, measurement basis and frozen values.
- UI buttons follow existing visual styling and use the authenticated fetchBlob utility.
- Data is taken from the original submitted snapshot, not refreshed live sources.
- Restricted-scope users are denied full-report export by the same server-side checks used for viewing reports.

## Not implemented / blockers
- Financials/billing/collection and Commissioning source integrations: the relevant authoritative, permission-safe certified measures are not connected; do not infer them from physical progress.
- A fully templated customer report, charts embedded in PDF, cross-module evidence bundles and advanced executive reporting.
- Database-backed and browser acceptance testing must precede production rollout.
- Existing report capture only supports current reporting data date, not historical as-of reconstruction.

## Deployment
Add `reportlab==4.2.5` from backend requirements and rebuild the backend + frontend. No new database migration is required in this phase.
