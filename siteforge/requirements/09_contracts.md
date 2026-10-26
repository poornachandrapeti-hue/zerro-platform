# 09. Contracts

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Own agreements, contractual scope, BOQ/rates/terms, notices, variations and claims.

Backend package: `commercial_financials`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

Contracts Manager prepares/controls terms. Technical scope reviewers validate discipline content. Designated commercial authorities approve agreements/variations. Finance consumes effective terms; client/contractor sees only shared records.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- Agreement: parties, contract type, dates, currency, commercial permissions, scope, obligations and controlled signed evidence.
- BOQ/version: item code, description, quantity/UOM, rates, measurement rules, effective version and supersession.
- Terms: billing milestones, retention, advance/recovery, taxes/deductions references, payment periods, warranty and guarantees.
- Notice/variation/claim: cause, source change, notice deadline, impact, valuation, correspondence and decision.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M09-001: Maintain client, contractor, subcontractor and supplier agreement types with versioned terms.
- M09-002: Route scope, commercial and signature approvals according to authority limits.
- M09-003: Store signed agreements through Document Control and verify required execution evidence.
- M09-004: Maintain effective BOQ/rate versions and measurement eligibility rules; do not let other modules edit them.
- M09-005: Track obligation dates, guarantees, insurance, warranty and renewal evidence.
- M09-006: Create contractual notices/claims with delivery/transmittal evidence and configured deadlines.
- M09-007: Value approved/pending changes distinctly; approval of a technical change alone does not amend contract value.
- M09-008: Issue contract amendments only after commercial approvals and effective-date validation.
- M09-009: Record disputed quantities/rates and resolution evidence for Financials.
- M09-010: Monitor contract consumption against committed/certified amounts supplied by Financials.
- M09-011: Keep confidential terms restricted to granted commercial roles.
- M09-012: Manage termination/suspension/closeout with open-claim and obligation checks.
- M09-013: Support contractor/client submissions without exposing other companies.
- M09-014: Retain prior terms so historical billing can be reproduced.

## Workflow and controls

Agreement: Draft → Internal Review → Approved for Execution → Executed → Active → Suspended / Closed / Terminated. Variation/Claim: Draft → Submitted → Assessed → Negotiation → Approved / Rejected / Disputed → Implemented via Amendment.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- Financials consumes BOQ/rates/terms; Procurement consumes supplier agreements.
- Construction supplies measurements; QA supplies acceptance; Changes supplies impact proposals.
- Planning consumes contractual milestones; Doc Control supplies executed files and notices.
- Risks tracks claims/obligations exposure without duplicating agreement ownership.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- Notice/guarantee/insurance/warranty deadlines → Contracts Manager and accountable owner.
- Unapproved scope/rate change → Contracts, Finance and PM.
- Claim dispute/contract overrun → authorized commercial hierarchy.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- Contract/BOQ register, obligations calendar, variation and claim registers.
- Original versus approved revised contract value and pending exposure by currency.
- Closeout readiness and confidential commercial dashboard.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-09-01: Historic bill retains its effective rate version.
- AC-09-02: Technical change cannot directly change signed contract terms.
- AC-09-03: Wrong-company client user cannot see another agreement.
- AC-09-04: Closing contract requires open-obligation resolution or documented authorized exception.

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
