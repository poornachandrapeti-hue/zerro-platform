# 05. Financials

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Track budgets, commitments, certified billing, invoices, costs and payment status with auditable ledgers.

Backend package: `commercial_financials`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

Finance prepares/posts authorized transactions; quantity certifiers and Contracts validate eligibility. PM receives authorized summaries. Payment authorization is separate from preparation; client/contractor access is restricted to assigned claims.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- Budget versions: WBS/cost code, currency, approved limit, contingency and effective date.
- Ledger: commitment, accrual, invoice, certification, credit, payment, retention, advance and adjustment entries with source/idempotency key.
- Bill/claim: contract BOQ/rate version, period, measurement references, QA acceptance, deductions, taxes and supporting evidence.
- Settlement: invoice/ref, authorized payee reference, due date, payment approval, provider/manual reference, reconciliation and reversal.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M05-001: Create/revise budgets through controlled approval; retain baseline and variance history.
- M05-002: Track approved commitments from issued POs/contracts; avoid counting commitment again as actual cost.
- M05-003: Define separate financial metrics: budget, open commitment, accrual/actual cost, certified amount, invoiced amount, paid amount and forecast.
- M05-004: Prepare contractor/client running bills from eligible measured/accepted quantities and effective contract rates.
- M05-005: Prevent the same measurement from being billed beyond its eligible balance; allocate partial certification explicitly.
- M05-006: Support advances, recovery, retention, taxes, deductions, penalties and credit notes using configurable terms.
- M05-007: Implement PO/receipt/invoice matching with configurable tolerances; mismatches become blocked exceptions.
- M05-008: Separate bill submission, certification, invoice posting, payment authorization and bank settlement states.
- M05-009: Use decimal arithmetic, explicit currencies, controlled exchange-rate sources/date and rounding rules.
- M05-010: Freeze certified/posted entries; correct through authorized reversal/adjustment, never editing history.
- M05-011: Restrict bank/salary data and financial exports; enforce amount limits and maker/checker approval.
- M05-012: Support manual payment reference entry with reconciliation; gateway/bank/ERP connectors remain optional verified integrations.
- M05-013: Provide aging, cash-flow and cost forecasts with documented assumptions.
- M05-014: If a general ledger/tax/payroll engine is outside the implementation, expose approved exports and label the scope clearly instead of implying full statutory accounting.

## Workflow and controls

Budget: Draft → Reviewed → Approved → Superseded. Bill: Draft → Submitted → Measured/Reviewed → Certified / Returned / Rejected. Invoice: Draft → Matched → Posted / Disputed → Settled. Payment: Prepared → Authorized → Initiated → Confirmed / Failed → Reconciled; partial allocations allowed.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- Contracts owns BOQ/rates/terms; Construction owns verified quantities; QA owns acceptance.
- Procurement supplies commitments; Stores supplies receipt evidence; HR supplies approved timesheet/payroll references if enabled.
- Planning supplies forecast; Progress displays authorized financial summaries.
- Approved Changes update budget only through financial approval; ERP/bank connectors use reconciliation.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- Budget/commitment breach → Finance Manager, cost owner and PM.
- Unmatched invoice/certification overdue → accountant, certifier, Contracts and Finance Manager.
- Payment overdue/failure/reconciliation difference → authorized Finance hierarchy only.
- Commercial change awaiting valuation → Contracts and Finance.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- Budget versus actual/open commitments/forecast by cost code and currency.
- Bill certification queue, invoice matching exceptions, payables/receivables aging and cash flow.
- Progress versus certified/paid percentages with clearly distinct denominators.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-05-01: Concurrent claims cannot certify the same quantity twice.
- AC-05-02: Payment preparation cannot authorize its own release under default policy.
- AC-05-03: Posted correction creates reversing entries and preserves balances.
- AC-05-04: Unauthorized PM/site/client responses omit sensitive amounts and bank fields.

- Cross-project, wrong-company, wrong-discipline, revoked-user and unauthorized-file/export tests pass.
- Creation → submission → review → decision → domain application works through real frontend/API flows.
- Duplicate retries and concurrent state transitions preserve quantities, ledgers and audit consistency where applicable.
- Required notification/overdue cases work with a controllable clock and authorized recipients.

## Suggested delivery slices

1. Masters, scoped registers, draft/detail screens and controlled attachments.
2. Submission/review/domain transitions, required current-data gates and audit.
3. Internal integrations, ledger/handoff reconciliation, alerts and role-aware dashboards.
4. Verified optional external connectors, advanced reports and operational hardening.

Do not label an entire module complete after slice 1. Update the coverage tracker after each tested requirement.
