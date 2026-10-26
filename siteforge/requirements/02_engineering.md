# 02. Engineering & Drawing Management

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Track planned deliverables and every drawing revision from preparation through discipline/client review and release for construction.

Backend package: `engineering_documents`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

Engineering Coordinator maintains register. Electrical, Mechanical, Civil and Instrumentation Heads own technical review. Assigned Client/PMC reviewers decide client submissions. Site engineers consume released drawings.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- Deliverable: drawing number/title/type, discipline, WBS/work package, location, originator/company, responsible engineer, planned issue date and priority.
- Revision: revision code/sequence, file reference, source, checksum, preparation/review dates, review outcome and construction release state.
- Review: submission/transmittal, reviewer, comments/markup, response, due date, decision and reviewed revision.
- External mapping: provider/project/document/revision IDs, synchronization checkpoint and conflict status.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M02-001: Create master drawing register manually, from validated imports, or configured external synchronization.
- M02-002: Distinguish planned/to-be-prepared drawings from prepared revisions; assign owners and dates.
- M02-003: Support civil, mechanical/piping, electrical, instrumentation and configurable additional disciplines.
- M02-004: Keep drawing identity separate from revisions; preserve superseded revisions and review evidence.
- M02-005: Route internal discipline review then client/PMC review when policy requires; support return and resubmission.
- M02-006: Record comment lists by revision, page/location, severity, owner, response and closure evidence.
- M02-007: Use configurable review codes with explicit meaning; accepted-with-comments does not automatically mean construction-released.
- M02-008: Require designated engineering authority to release a reviewed revision for construction under project rules.
- M02-009: Flag work packs referencing superseded/withdrawn revisions and require engineering impact assessment.
- M02-010: Link material take-offs to exact drawing revision; send controlled demand changes to Requests/Procurement.
- M02-011: Track technical queries/RFIs through controlled correspondence with owner and resolution links.
- M02-012: Implement manual tracking with source evidence even if Wrench is unavailable.
- M02-013: Implement a disabled-by-default Wrench adapter interface; build real connector only after customer supplies verified API/export specifications and credentials.
- M02-014: Show last sync, rejected records and reconciliation; never overwrite a manual approval with an external status without an approved mapping.

## Workflow and controls

Preparation: Planned → In Preparation → Prepared. Review: Draft → Internal Review → Client Review → Accepted / Accepted with Comments / Returned / Rejected. Release: Not Released → Released for Construction → Superseded / Withdrawn. Keep these dimensions separate.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- Document Control owns files/transmittals; Engineering owns technical review and release.
- Planning consumes deliverable dates and engineering readiness.
- Construction consumes exact released revisions; QA consumes approved inspection-related drawings.
- Requests/Procurement consume approved material demand; Changes assess revision impact.
- Wrench connector supplies provenance and external references; conflicting updates enter reconciliation.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- Overdue preparation/review/comment response → engineer, discipline head, then PM.
- Superseded revision linked to active work → affected site engineers, QA and discipline head.
- External sync failure/conflict → integration administrator and Engineering Coordinator.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- Drawing register with revision/review/release filters.
- Distinct drawing counts: to prepare, in preparation, under review, accepted, accepted with comments, returned, rejected and released; define whether latest revision or all revisions is counted.
- Client review aging, unresolved comments and deliverable plan versus actual.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-02-01: New revision never deletes old comments or decisions.
- AC-02-02: A reviewed but unreleased revision cannot pass construction readiness.
- AC-02-03: Imported duplicate revisions are idempotent and conflicting content is visible.
- AC-02-04: Dashboard counts reconcile to their filtered register populations.

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
