# 01. Project Details

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Provide the project master and access context used by every business module.

Backend package: `identity_projects`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

PM owns project coordination. Organization Administrator manages membership and participating companies. Discipline heads see their assigned scope. Finance/Contracts control commercial references.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- Project: code, name, description, type, status, client, lead PM, timezone, location/address, coordinates, planned/actual dates and version.
- Participation: company, company type, participation dates, status and project memberships with role/discipline scope.
- Hierarchy: units, areas and blocks with parent references; project disciplines, calendars and configuration references.
- Links: contract IDs, controlled attachments, project milestones, project contacts and status history. Do not duplicate contract terms or financial ledgers.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M01-001: Create Draft with code and name; require client, lead PM, location, timezone, disciplines and planned dates before activation.
- M01-002: Maintain configurable project types; validate case-insensitive project code uniqueness within organization.
- M01-003: Enforce planned/actual date ordering; prohibit future actual dates in project timezone; record hold/cancellation reasons.
- M01-004: Manage participating client, PMC, contractor and subcontractor companies; activate/deactivate without deleting referenced records.
- M01-005: Assign multiple roles per user and explicit ALL/SELECTED disciplines; prevent cross-organization assignments.
- M01-006: Create/edit/archive unit → area → block hierarchy; prevent cycles, wrong-project parents and removal of referenced locations.
- M01-007: Store contacts by function with permission-controlled contact details; distinguish contacts from authorized approvers.
- M01-008: Upload categorized project documents through Document Control and retain revision/access history.
- M01-009: Show project readiness and missing mandatory setup; show linked module counts only from real data.
- M01-010: Use explicit status transition commands; update PM assignment and require review of former PM memberships.
- M01-011: Expose contract value/currency and budget summaries only to authorized viewers via owning module interfaces.
- M01-012: Maintain setup/configuration changes and project audit timeline.

## Workflow and controls

Draft → Planned → Active → On Hold → Active → Completed → Archived; Cancelled requires reason. Completion needs approved handover requirements or an explicit authorized exception with evidence. Archive is read-only; reopening requires authorized reason.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- All modules consume project/company/discipline/location IDs.
- Contracts supplies commercial agreement references; Financials supplies authorized budget summaries.
- Planning supplies milestones; Commissioning supplies completion readiness; Document Control owns attachment bytes.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- Missing setup → PM and administrator.
- Project start/end approaching or active date slippage → PM and Planning Head.
- Membership/PM change → affected users and authorized access administrator.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- Project list with status/client/PM/date filters.
- Overview, location hierarchy, team/access, milestones, documents and audit tabs.
- Role-aware project dashboard with dated summaries and links to owning modules.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-01-01: Cannot activate an incomplete project.
- AC-01-02: Wrong-project location parent and unscoped membership are rejected.
- AC-01-03: Status/PM edits create audit entries and preserve history.
- AC-01-04: Unauthorized users never receive commercial values.

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
