# 11. Progress

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Publish traceable consolidated progress snapshots across engineering, procurement, construction and completion.

Backend package: `planning_reporting`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

Progress/Planning team prepares reports. Discipline Heads validate their summaries. PM approves publication. Client/PMC receives explicitly published permitted views.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- Reporting period/snapshot: cutoff, timezone, baseline version, source versions/IDs, freshness, preparer and publication decision.
- Metric definitions: domain, population, denominator, weighting/UOM and calculation version.
- Progress facts: planned, reported, verified, accepted and completion milestones from owning modules.
- Narrative: accomplishments, delays, risks, recovery, photos and distribution/access scope.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M11-001: Define daily/weekly/monthly reporting periods with explicit cutoff.
- M11-002: Consume owning-module facts instead of letting users edit consolidated source totals.
- M11-003: Show engineering preparation/review/release, procurement ordering/delivery/acceptance, construction verification and commissioning acceptance separately.
- M11-004: Calculate project/discipline/location/contractor progress using approved methods and weights.
- M11-005: Prevent double-counting summary and child activities; handle zero/changed denominators explicitly.
- M11-006: Keep physical progress, certified billing and paid percentages distinct.
- M11-007: Support draft snapshots with data freshness/missing-source warnings.
- M11-008: Route discipline validation and PM publication according to policy.
- M11-009: Freeze published snapshots; corrections create a superseding snapshot with reason.
- M11-010: Provide client-safe published reports and hide confidential HR/commercial fields.
- M11-011: Show drill-through lineage from dashboard metric to source records.
- M11-012: Generate authorized PDF/XLSX exports and trend charts using actual data.
- M11-013: Track forecast completion/variance from Planning with assumptions and baseline reference.
- M11-014: Publish reporting task completion and distribution history.

## Workflow and controls

Snapshot: Draft → Discipline Validation → PM Review → Published → Superseded. Incomplete sources remain flagged; publication exceptions require explicit authorization and disclosure.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- Planning supplies baseline/targets; all domain owners supply metrics/facts.
- Financials supplies permitted certification/payment aggregates; Contracts provides denominator references.
- Document Control stores issued report; Meetings/Risks/Changes supply narrative links.
- Client-facing portal sees only permitted published snapshots.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- Missing data/stale source → source owner and report preparer.
- Review/publication overdue → discipline head then PM.
- Published material correction → subscribed authorized recipients.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- Executive progress dashboard, S-curves and planned versus actual trends.
- Discipline/contractor/location drill-down and period reports.
- Data-quality/source-freshness panel and snapshot history.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-11-01: Snapshot totals reproduce from recorded definitions/source references.
- AC-11-02: Published report cannot change after source correction.
- AC-11-03: No division by zero or mixed-UOM aggregation.
- AC-11-04: Client publication filters remove internal-only metrics and files.

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
