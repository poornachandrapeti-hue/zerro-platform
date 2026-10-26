# 07. Safety / HSE

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Control site safety readiness, permits, incidents, observations and stop-work/release authority.

Backend package: `safety`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

HSE Officer coordinates checks; designated permit issuer issues permits. Work supervisor accepts conditions. HSE Head controls safety hold release. PM coordinates corrective actions but cannot bypass safety authority.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- Risk assessment/JSA: activity/location/hazards, risk rating method, controls, responsible owner and approval version.
- Permit: type, work scope, location, validity window, isolation references, crew, issuer/acceptor, required checks and closure evidence.
- Incident/near miss/observation: event, severity, affected location/person references, restricted details, actions and investigation.
- Safety hold, induction/training, toolbox talk, inspection and emergency plan records.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M07-001: Configure permit types such as hot work, confined space, excavation, height, lifting and electrical isolation.
- M07-002: Link permits to current work packs, crew eligibility and risk assessments.
- M07-003: Validate required isolations, gas tests, rescue plans and competent persons according to approved site policy.
- M07-004: Define permit start/expiry, suspension, renewal and closure checks; renewal is a reviewed action.
- M07-005: Record induction, toolbox attendance and safety training using HR personnel IDs.
- M07-006: Raise observations and near misses with owner, due date and closure evidence.
- M07-007: Support immediate stop-work/safety hold by authorized field personnel; notify affected teams.
- M07-008: Permit release/restart only after authorized checks; PM escalation never automatically releases a hold.
- M07-009: Record incidents, investigation, root cause and corrective actions with confidentiality controls.
- M07-010: Maintain site emergency contacts, assembly points, drills and response plans.
- M07-011: Record HSE audits, equipment/lifting inspection links and subcontractor compliance.
- M07-012: Provide offline-friendly draft capture only if implemented; synchronize and validate server gates before work authorization.
- M07-013: Configure any external reporting obligations per project; do not claim regulatory compliance from record storage alone.
- M07-014: Track metrics using configurable definitions and worked-hour denominators; protect personal/medical details.

## Workflow and controls

Permit: Draft → Submitted → Reviewed → Issued → Active → Suspended / Expired / Closed. Renewal creates a new validity decision. Incident: Reported → Triaged → Investigating → Actions → Verified → Closed. Safety hold: Active → Release Requested → Released.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- Construction/Commissioning use current permit/hold checks.
- HR supplies induction/fitness eligibility only, with confidential details masked.
- Equipment supplies inspection/maintenance readiness; QA shares impacted activities.
- Manpower provides assigned crews; Risks/Meetings track actions; Doc Control retains evidence.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- Critical incident/stop work → affected supervisors, HSE Head and designated emergency escalation immediately.
- Permit expiry/unsafe equipment → issuer, work supervisor and HSE.
- Overdue corrective action/expired training → action owner, HSE hierarchy and HR as applicable.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- Active/expiring permits, safety holds, observations and action aging.
- Incident trends and safety-hour metrics with defined calculation methods.
- Induction/training readiness and confidential investigation view.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-07-01: Expired/suspended permit blocks gated work at action time.
- AC-07-02: Stop-work alert reaches only authorized affected recipients.
- AC-07-03: Unauthorized users cannot read medical/investigation attachments.
- AC-07-04: Renewal/release retains issuer evidence and cannot be self-assigned to an administrator.

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
