# 20. Meetings & Actions

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Record project coordination decisions and track linked actions with accountable owners.

Backend package: `coordination`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

Meeting organizer prepares agenda/minutes. Chair/designated reviewer confirms minutes. Action owners complete tasks. Sensitive records retain module-specific permissions.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- Meeting: type, project, date/timezone, chair, attendees, agenda and confidential scope.
- Minutes/version: discussion points, decision text, linked domain records, reviewer and distribution.
- Action: source minute, owner, due date, priority, status, evidence and shared task ID.
- Follow-up: previous actions, amendments, acknowledgments and closure.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M20-001: Schedule coordination, discipline, progress, QA/HSE and commercial meetings.
- M20-002: Prepare agenda from authorized blockers/risks/changes and open actions.
- M20-003: Record attendees/apologies and minutes with controlled revisions.
- M20-004: Assign actions using the shared task service; avoid a duplicate task ledger.
- M20-005: Confirm minutes through designated review and distribute permitted versions.
- M20-006: Track action evidence, overdue status and follow-up across meetings.
- M20-007: Link decisions to source records but do not treat a meeting minute as technical/financial approval.
- M20-008: Amend confirmed minutes through a new version with history.
- M20-009: Keep commercial/HSE/HR details restricted in mixed-audience meetings.
- M20-010: Support recurring meeting templates; external calendar/video integration is optional and requires explicit setup.
- M20-011: Reassign departed owners with auditable replacement.
- M20-012: Close meeting actions only when owning domain evidence is satisfied.

## Workflow and controls

Meeting: Planned → Held → Minutes Draft → Reviewed → Confirmed → Archived. Actions use shared Open/In Progress/Blocked/Completed/Cancelled states.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- Shared tasks/workflows supplies assignments and review.
- Risks/Changes/Planning/all modules supplies authorized agenda links.
- Doc Control stores confirmed minutes and distribution evidence.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- Action due/overdue → owner then function head/PM.
- Minutes review overdue → chair/designated reviewer.
- Unassigned or inactive owner → organizer and administrator.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- Meeting calendar/register, minutes and action follow-up board.
- Overdue actions by responsible owner and linked project blockers.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-20-01: Confirmed minute does not authorize a PO/payment/hold release.
- AC-20-02: Restricted agenda link does not expose confidential source fields.
- AC-20-03: Action created once despite repeated minute submission.
- AC-20-04: Amendments preserve original confirmed minutes.

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
