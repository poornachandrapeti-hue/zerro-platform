# 18. Project Risks & Issues

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Track uncertainty, realized issues, exposure, mitigation and accountable follow-through.

Backend package: `coordination`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

Any authorized team member raises a risk/issue. Discipline/function owner assesses it. PM owns project risk review. Commercial/safety confidential items retain their owning-module restrictions.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- Risk: category, description/cause/event/impact, owner, probability/impact scale, inherent/residual rating and review date.
- Issue: realized event, affected scope, severity, source, responsible owner, due date and resolution evidence.
- Response/action: mitigation/contingency, trigger, cost/schedule estimate, task and completion evidence.
- Assessment history: date, reviewer, rating method/version and linked changes/delays/claims.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M18-001: Configure rating scales and matrix with definitions; label exposure estimates/assumptions.
- M18-002: Create risks manually or from module exceptions and deduplicate source references.
- M18-003: Record mitigation and contingency owners/dates through shared tasks.
- M18-004: Convert realized risks to linked issues while preserving original history.
- M18-005: Track schedule/cost/quality/HSE/resource exposure without duplicating source incidents/NCRs.
- M18-006: Review residual risk and escalation thresholds periodically.
- M18-007: Link issues to recovery plans, Changes, claims and meeting decisions.
- M18-008: Restrict sensitive risk details and attachments by source permissions.
- M18-009: Support acceptance/closure with designated authority and evidence.
- M18-010: Maintain recurring reviews and reopen reasons.
- M18-011: Show trend/history instead of overwriting prior ratings.
- M18-012: Exclude speculative financial exposure from actual financial balances.

## Workflow and controls

Risk: Identified → Assessed → Response Planned → Monitoring → Closed / Realized. Issue: Open → Assigned → Action in Progress → Resolution Verified → Closed.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- All modules supply source exceptions; owning modules retain authoritative records.
- Planning/Financials supplies authorized impact evidence; Changes owns baseline/scope response.
- Meetings links decisions; shared tasks drives mitigation follow-up.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- Critical rating/realized issue → owner, function head and PM.
- Mitigation/review overdue → owner then PM hierarchy.
- Source restriction change → reconcile viewers and notifications.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- Risk matrix, issue register, residual exposure trends and mitigation aging.
- Affected milestone/discipline filters and source drill-through.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-18-01: Risk-to-issue conversion preserves linkage.
- AC-18-02: Restricted incident risk cannot expose original confidential narrative.
- AC-18-03: Closure needs required action evidence.
- AC-18-04: Estimated exposure never posts actual cost.

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
