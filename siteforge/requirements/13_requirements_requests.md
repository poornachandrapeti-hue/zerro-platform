# 13. Requirements & Requests

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Centralize operational demand intake and routing without duplicating fulfillment in receiving modules.

Backend package: `coordination`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

Any authorized requester creates a scoped request. Discipline/function head validates need. Receiving Procurement/Stores/Engineering/HR/Manpower/Equipment/IT owner fulfills. PM resolves cross-functional overdue blockers.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- Request: type/category, title/details, priority, requester/company/discipline/location, required date, work pack and evidence.
- Lines: item/service/resource specification, quantity/UOM or duration, target module and approval requirements.
- Routing/approval: owner, reviewers, due dates and decision evidence.
- Fulfillment links: accepted handoff ID, allocated quantity, receiving-module state and closure acknowledgment.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M13-001: Support material, drawing/technical information, manpower, equipment, service and administrative request types.
- M13-002: Require category-specific fields and project/company/discipline scope.
- M13-003: Suggest existing duplicate/open requests and allow explicit linking, not silent merging.
- M13-004: Route need validation and expenditure approvals separately where applicable.
- M13-005: Assign accountable receiving owner and SLA; missing configuration blocks routing.
- M13-006: Convert approved demand into receiving-module records through idempotent commands.
- M13-007: Support partial fulfillment and multiple receiving records with allocations.
- M13-008: Derive fulfillment from receiving-module evidence; generic approval cannot mark it fulfilled.
- M13-009: Allow clarification/return with comment history and attachment evidence.
- M13-010: Cancellation checks dependent POs/reservations/assignments and coordinates compensating action.
- M13-011: Provide requester acknowledgment/closure rules and reopen flow with reason.
- M13-012: Link blockers, risks and meeting actions; avoid duplicate tasks by source ID.
- M13-013: Maintain searchable request history and cross-module audit lineage.
- M13-014: Support configurable templates rather than a second full requirements engineering tool.

## Workflow and controls

Draft → Submitted → Need Review → Approved / Returned / Rejected → Assigned → In Fulfillment → Partially Fulfilled → Fulfilled → Closed. Cancellation after handoff requires receiving-domain confirmation.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- Stores fulfills stock demands; Procurement buys approved shortages.
- Engineering resolves technical requests; HR/Manpower/Equipment fulfill resource requests.
- Financials checks budgets; Planning consumes readiness/blocker state.
- Shared workflow/tasks tracks review and owner SLAs.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- Unassigned/overdue request → receiving owner/function head then PM.
- Urgent demand threatens schedule → Planning and relevant discipline head.
- Failed handoff/cancellation conflict → source and target owners.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- My requests, team queues and cross-module status board.
- Approved versus fulfilled demand, SLA aging and unresolved blockers.
- Handoff/fulfillment links with source evidence.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-13-01: Submitting twice creates one target demand.
- AC-13-02: Approval does not imply fulfillment.
- AC-13-03: Wrong-scope recipient cannot receive private request details.
- AC-13-04: Cancellation cannot orphan an active PO/reservation.

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
