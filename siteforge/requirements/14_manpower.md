# 14. Manpower

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Plan trade demand, build crews, allocate eligible workers and monitor field utilization.

Backend package: `resources`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

Manpower Coordinator schedules crews. Supervisors confirm deployment. Discipline Head validates demand. HR owns personnel/attendance; HSE/QA owns eligibility gates.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- Demand: activity, trade/skill, headcount/hours, shift, location, period, productivity assumption and priority.
- Crew: supervisor, company, personnel memberships with effective dates and qualifications.
- Assignment: worker/crew, work pack/date/shift, allocated hours, approval, actual attendance link and release.
- Utilization: productive/idle/rework hours, reason codes, timesheet sources and output quantities.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M14-001: Generate or enter demand from Planning activities and Construction lookaheads.
- M14-002: Compare demand with available deployed personnel and approved trade/skill eligibility.
- M14-003: Build crews with supervisor and company-scoped membership.
- M14-004: Allocate workers without overlapping shift/hour assignments beyond policy.
- M14-005: Check induction, fitness/qualification flags and current deployment before allocation.
- M14-006: Keep planned allocation separate from actual HR attendance.
- M14-007: Record operational productive/idle/rework allocation against approved attendance hours; prevent allocated actual hours exceeding attendance.
- M14-008: Reassign absent workers and record replacements/history.
- M14-009: Raise shortages through Requests/HR and equipment substitution only under approved execution policy.
- M14-010: Capture idle causes and manpower recovery plans linked to delay owners.
- M14-011: Calculate trade/crew productivity using verified Construction output and approved time denominators.
- M14-012: Keep payroll rates/private HR documents out of operational screens.
- M14-013: Support contractor workforce summaries and forecast demand curves.
- M14-014: Release crew assignments when work ends/cancels and reconcile open allocations.

## Workflow and controls

Demand: Draft → Reviewed → Approved → Allocated → Fulfilled / Shortfall → Closed. Assignment: Proposed → Confirmed → Active → Released / Reassigned. Utilization: Draft → Supervisor Verified → Published.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- HR owns availability, deployment, qualifications and attendance.
- Planning/Construction owns activities, demand dates and verified production.
- HSE/QA supplies eligibility; Requests routes recruitment/subcontract demand.
- Financials consumes authorized time-allocation evidence, not duplicate payroll.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- Trade shortage/assignment conflict → coordinator, discipline head and Planning.
- Eligibility expiry/absent crew → supervisor, HR and HSE/QA as applicable.
- Idle/low utilization → supervisor, manpower lead and PM for major blockers.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- Demand versus availability by trade/date/shift.
- Crew assignment board and utilization/productivity trends.
- Shortage, attendance mismatch and qualification readiness views.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-14-01: Double-booking worker is rejected under concurrent allocation.
- AC-14-02: Expired eligibility blocks assignment without exposing medical records.
- AC-14-03: Actual allocation cannot exceed approved attended hours.
- AC-14-04: HR attendance correction triggers utilization reconciliation.

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
