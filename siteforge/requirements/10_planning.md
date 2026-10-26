# 10. Planning

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Own WBS, schedules, approved baselines, targets, dependencies and recovery forecasting.

Backend package: `planning_reporting`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

Planner creates schedules. Planning Head validates logic and baseline. PM/designated authority approves project baselines. Discipline heads provide forecasts; execution modules remain owners of actual facts.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- WBS/activity: code, hierarchy, discipline/location/company, work scope, quantity/UOM, duration, calendar and owner.
- Dependencies: predecessor/successor, FS/SS/FF/SF relationship, lag, constraints and validation.
- Baseline/version: approved planned dates/quantities/weights, approval and effective date.
- Forecast/lookahead: remaining duration, readiness, resource demand, blockers, recovery assumptions and actual source links.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M10-001: Create project WBS and measurable activities linked to scope/BOQ/work packs.
- M10-002: Support calendars, shifts, holidays and working-time duration calculations.
- M10-003: Validate dependency cycles, invalid dates and orphaned required activity links.
- M10-004: Support approved baseline versions; distinguish original/current baseline from live forecast.
- M10-005: Create weekly/daily lookaheads with material, drawing, permit, crew and equipment readiness.
- M10-006: Consume verified actual start/finish/quantities from Construction and completion facts.
- M10-007: Define progress weights/methods by activity; prohibit summing incompatible units and double-counting parent/child weights.
- M10-008: Compute schedule variance and forecast using documented algorithms; critical-path calculation must be implemented/tested before showing it.
- M10-009: Record delay events, responsible causes and recovery plans with impacted activities.
- M10-010: Generate manpower/material/equipment demand from approved plans using explicit productivity assumptions.
- M10-011: Route baseline changes through Change Management and required baseline approval.
- M10-012: Support validated schedule CSV/XLSX import/export; Primavera/MS Project connectors are optional after verified format/interface mapping.
- M10-013: Keep planned dates editable only in authorized forecast/rebaseline contexts.
- M10-014: Publish frozen period plans for Progress comparison.

## Workflow and controls

Schedule: Draft → Logic/Resource Review → Submitted → Baseline Approved → Active → Revised Forecast. Rebaseline: Proposed → Impact Assessed → Approved → New Baseline Version. Lookahead: Draft → Reviewed → Published.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- Construction/Commissioning supply actuals; Engineering/Procurement/Stores/QA/HSE supply readiness.
- Manpower/Equipment supply availability; Contracts supplies contractual milestones.
- Changes controls baseline change approval; Progress owns consolidated reports.
- Financials supplies authorized cost forecasts if enabled.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- Milestone slip/critical readiness blocker → activity owner, discipline head and PM.
- Missing actuals/resource overload → Planning Head and source owner.
- Unapproved baseline edit attempt → Planning Head; audit required.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- WBS/Gantt, baseline versus forecast, lookahead readiness and milestone dashboard.
- Dependency/critical path views only when calculations are implemented.
- Delay/recovery register and resource demand profile.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-10-01: Cycle import is rejected with affected activity IDs.
- AC-10-02: New baseline preserves previous approved dates/weights.
- AC-10-03: Execution fact cannot be overwritten by planner.
- AC-10-04: Progress weight totals and mixed-UOM rules are validated.

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
