# 19. Change Management

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Coordinate controlled impact review of scope, drawings, quantities, schedule, cost and contract changes.

Backend package: `coordination`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

Originator proposes. Discipline leads, Planning, Contracts, Finance, QA and HSE review relevant impacts. Designated change authority approves. Each affected domain applies its own authorized change.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- Change: source/cause, description, affected project/WBS/drawings/contracts, priority and proposed effective date.
- Impact assessment: quantity, cost/currency, schedule, resources, safety/quality and reviewer evidence.
- Decision: policy/version, approved limits/conditions, client approval and status.
- Application: domain command IDs, old/new versions, completion state, failures and reconciliation.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M19-001: Raise change proposals from revisions, field instructions, claims or planning deviations.
- M19-002: Classify technical, scope, commercial and baseline changes and determine mandatory reviewers.
- M19-003: Capture cross-domain impacts and assumptions; no-impact must be an explicit reviewer decision.
- M19-004: Prevent implementation before required approval except documented emergency policy with limited authority and retrospective review.
- M19-005: Separate technical approval from contract valuation and financial/baseline approvals.
- M19-006: Freeze approved scope/conditions and invalidate affected decisions when material proposal content changes.
- M19-007: Apply approved changes through domain commands; do not write other modules tables directly.
- M19-008: Track partial application and retry/reconcile failures idempotently.
- M19-009: Record revised drawing/BOQ/budget/baseline versions and notify affected work owners.
- M19-010: Preserve original baseline, terms and quantities for comparison.
- M19-011: Check active work/stock/billing implications before cancellation/reversal.
- M19-012: Close only after affected owners confirm application and evidence.

## Workflow and controls

Draft → Submitted → Impact Assessment → Approval Review → Approved / Returned / Rejected → Applying → Applied → Closed. Partial/Failed Application remains visible. Withdrawn proposals retain evidence.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- Engineering/Construction/Planning supplies triggers and impacts.
- Contracts/Finance authorizes amendments/budgets; QA/HSE assesses gate effects.
- Requests/Procurement/Stores/Manpower/Equipment applies demand/resource consequences.
- Progress consumes approved revised baselines; shared workflow coordinates reviews.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- Missing impact/approval overdue → reviewer, function head then change authority/PM.
- Unauthorized implementation/material new impact → affected domain lead and PM.
- Partial application failure → change owner and affected domain administrator.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- Change register, impact comparison, approval queue and application checklist.
- Approved versus pending change exposure with currency/baseline references.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-19-01: Approved technical proposal cannot directly revise budget/contract.
- AC-19-02: Replay applies each domain command once.
- AC-19-03: Partial application is never displayed as fully implemented.
- AC-19-04: New proposal version requires affected reviewers to decide again.

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
