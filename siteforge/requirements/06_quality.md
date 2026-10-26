# 06. Quality / QAQC

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Own inspection outcomes, quality acceptance, nonconformances and quality holds across all modules.

Backend package: `quality`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

QA/QC Head approves ITP/templates and hold release. Inspectors perform assigned checks. Site engineers offer work. Client/PMC witnesses and acceptance reviewers act only on designated steps.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- ITP/template versions: discipline/activity, checkpoints, acceptance criteria reference, hold/witness/review points and authorized reviewers.
- Inspection/RFI: work lot/quantity/material, location, drawing/spec revision, test records, results and witness evidence.
- NCR/CAR: issue, severity, affected records/quantity, containment, cause, disposition, corrective action and closure evidence.
- Quality hold/release: scope, reason, authority, affected work/material and validated release conditions.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M06-001: Maintain approved ITPs, checklists and procedure references with controlled versions.
- M06-002: Create material receipt inspection and construction inspection offers against exact source records.
- M06-003: Require evidence for mandatory hold/witness points before acceptance; configure attendance/waiver rules explicitly.
- M06-004: Record test values, units, acceptance criteria references, laboratory reports and inspector competence.
- M06-005: Track discipline-specific inspection/test sequences through configurable templates.
- M06-006: Keep accepted, rejected, quarantined and pending quantities separate and reconcile lot quantities.
- M06-007: Raise NCRs from inspections/audits; document containment, root cause, approved disposition and reinspection.
- M06-008: Allow accept-as-is only through specifically authorized concession and required client approval.
- M06-009: Issue quality holds that block impacted material use, work release, billing or handover under policy.
- M06-010: Release holds only after designated reviewer verifies corrective evidence.
- M06-011: Manage inspector qualification and instrument calibration references from HR/Equipment.
- M06-012: Track supplier quality, incoming inspection, site audits and corrective-action trends.
- M06-013: Do not edit original test reports after decision; use revision/retest links.
- M06-014: Produce signed inspection dossier for Commissioning/Handover through Document Control.

## Workflow and controls

Inspection: Draft → Offered → Scheduled → Inspected → Accepted / Accepted with Authorized Concession / Rejected / Retest Required. NCR: Open → Contained → Disposition Approved → Corrective Action → Verification → Closed. Hold: Active → Release Requested → Released.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- Construction/Stores create inspection sources; QA owns decisions.
- Engineering/Doc Control supply specifications and revision evidence.
- Safety shares impacted work restrictions without replacing quality authority.
- Financials/Commissioning consume eligible acceptance; Risks/Changes receive material impacts.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- Failed critical test or hold → affected work/store owner and QA Head immediately.
- Inspection/NCR overdue → inspector, QA Head, discipline head then PM.
- Calibration/qualification expiry → QA and Equipment/HR.
- Repeated supplier rejection → Procurement Head.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- Inspection queue, acceptance status, NCR aging and hold register.
- First-pass acceptance, rework and supplier rejection metrics with explicit populations.
- Dossier readiness and missing evidence.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-06-01: Quarantined material cannot be issued as usable stock.
- AC-06-02: Failed mandatory checkpoint prevents acceptance.
- AC-06-03: Only authorized QA/client route can release/concede.
- AC-06-04: Retest preserves original failure and downstream acceptance references.

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
