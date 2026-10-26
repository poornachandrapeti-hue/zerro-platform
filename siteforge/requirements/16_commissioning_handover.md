# 16. Commissioning, Completion & Handover

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Control system completion, punch lists, testing, client acceptance and turnover dossiers.

Backend package: `construction_completion`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

Commissioning Lead owns system readiness. Discipline leads verify technical completion. QA/HSE controls acceptance/permit gates. Client/PMC signs designated handover packages.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- System/subsystem/tag: hierarchy, discipline, equipment/loop references, work scope and test boundaries.
- Completion package: work/QA evidence, checklist revision, prerequisite gates, permits and responsible reviewers.
- Punch: category/severity, source, owner, due date, blocking rule and closure evidence.
- Test/handover: procedure/revision, measured results, witness/signatures, dossier manifest and acceptance decision.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M16-001: Create system/subsystem/tag hierarchy and map Construction work packs/equipment/loops.
- M16-002: Define mechanical completion, precommissioning, commissioning and handover gates by project policy.
- M16-003: Consume completed/accepted execution and required technical documentation.
- M16-004: Run revision-controlled checklists with prerequisite validation and role-based signoff.
- M16-005: Manage punch lists with configurable category-to-blocking rules; no universal category assumptions.
- M16-006: Prevent tests/startup with blocking punches, safety holds or missing permits/isolation evidence.
- M16-007: Record test results, witness attendance, failures and retest links.
- M16-008: Track loop/functional/performance testing through discipline templates.
- M16-009: Assemble dossier from controlled as-built drawings, QA records, manuals, certificates and test reports.
- M16-010: Issue handover transmittals and obtain designated client/PMC decisions.
- M16-011: Support partial system handover and explicitly document exceptions/remaining obligations.
- M16-012: Link warranties, spares, training and O&M deliverables to Contracts/Equipment.
- M16-013: Preserve client acceptance separately from internal completion.
- M16-014: Supply overall project completion readiness to Project Details.

## Workflow and controls

System: Under Construction → Mechanical Completion Review → Mechanically Complete → Precommissioning → Commissioning → Ready for Handover → Client Accepted → Closed. Failed gates return to the appropriate controlled stage. Punch: Open → Actioned → Verified → Closed.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- Construction/QA supplies completion/acceptance; Engineering/Document Control supplies as-builts.
- Safety supplies permits/isolation/holds; Equipment supplies readiness/calibration.
- Contracts supplies handover/warranty obligations; Planning supplies milestones.
- Progress supplies published completion reporting; Project Details consumes final readiness.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- Blocking punch/missing dossier/test failure → commissioning owner and discipline/QA lead.
- Safety prerequisite failure → HSE and affected supervisors immediately.
- Client acceptance overdue → Commissioning Lead, Contracts and PM.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- System readiness matrix, punch aging and test register.
- Dossier completeness and handover package review queues.
- Mechanical completion versus client acceptance progress.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-16-01: Blocking punch prevents handover via API.
- AC-16-02: Failed test retained when retest passes.
- AC-16-03: Partial handover does not mark entire system complete.
- AC-16-04: Dossier manifest pins exact document revisions and signatures.

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
