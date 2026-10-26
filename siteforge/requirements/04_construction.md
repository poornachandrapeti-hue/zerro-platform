# 04. Construction

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Control field readiness, work execution and verified quantities across industrial disciplines.

Backend package: `construction_completion`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

Site Engineer/supervisor prepares work packs and daily reports. Discipline Head verifies execution. QA controls acceptance; HSE controls permits and safety holds. PM coordinates blockers.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- Work pack/activity: WBS, discipline, location, contractor, scope/BOQ reference, approved drawing revision, planned quantity/UOM and dates.
- Readiness: engineering release, material reservation, crew eligibility, equipment condition, permits, ITP gates and dependencies.
- Daily report: date/shift, crews, equipment, performed quantities, evidence, delay causes and verifier.
- Quantity ledger: measured increments, cumulative verified amount, corrections/reversals and QA acceptance links.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M04-001: Create work packs from Planning activities and approved execution scope.
- M04-002: Define discipline-specific activity templates for civil, mechanical/piping, electrical and instrumentation; detailed tests live in QA.
- M04-003: Evaluate mandatory readiness gates using current owners before release/start.
- M04-004: Record daily production by work item/date/shift with decimal quantity/UOM and location evidence.
- M04-005: Prevent double counting across crews/dates and over-execution above authorized scope without approved change.
- M04-006: Separate reported, verified, QA-accepted and billable quantities.
- M04-007: Support contractor/site review and independent quantity verification according to policy.
- M04-008: Link material issues, manpower allocations, equipment utilization and approved work permits.
- M04-009: Capture delays, obstructions, weather and idle reasons with responsible owner and recovery task.
- M04-010: Allow measurement correction through approved reversal/replacement entries after verification.
- M04-011: Pause work on safety/quality hold and invalidate affected readiness; require authorized release before resumption.
- M04-012: Generate inspection offers against completed lots/activities and link NCR/rework quantities without inflating production.
- M04-013: Maintain field photos, checklists and revision-specific evidence through Document Control.
- M04-014: Provide activity completion evidence to Planning, Progress, Commissioning and Financials.

## Workflow and controls

Work pack: Draft → Readiness Review → Ready → Released → In Progress → Suspended / Executed → Verified → Completed. QA acceptance is linked separately. Daily quantities: Draft → Submitted → Verified / Returned → Corrected by reversal when posted.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- Planning supplies activity scope/baseline; Engineering supplies released drawings.
- Stores supplies issued/reserved material; Manpower/HR supplies eligible crew/attendance; Equipment supplies readiness.
- Safety and QA supply authoritative gates and holds.
- Progress consumes verified quantities; Financials consumes contract-eligible, QA-accepted evidence; Commissioning consumes mechanical completion.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- Blocked readiness → responsible module owner, discipline head and Planning.
- Safety/quality hold → affected supervisors and QA/HSE immediately.
- Low production/overrun/over-execution attempt → discipline head, Planning and PM.
- Daily report overdue → site engineer then discipline head.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- Work readiness board, daily report register and location/discipline execution dashboard.
- Planned/reported/verified/accepted quantities with explicit units.
- Blockers, rework, contractor productivity and recovery actions.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-04-01: Held work cannot start or resume through direct API calls.
- AC-04-02: Concurrent daily entries cannot exceed authorized cumulative quantity.
- AC-04-03: Corrections retain original verified evidence and adjust downstream reporting once.
- AC-04-04: QA acceptance and billing are never inferred from execution alone.

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
