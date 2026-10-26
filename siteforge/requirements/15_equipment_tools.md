# 15. Equipment & Tools

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Manage equipment/tool identity, operational allocation, maintenance, inspections and utilization.

Backend package: `resources`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

Equipment Coordinator controls allocation. Custodians acknowledge handover. Maintenance team records service. QA owns calibration acceptance; HSE controls safety eligibility; Finance owns cost posting.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- Asset: code/serial, type, ownership/rental, capacity, company, location, custodian and documents.
- Eligibility: inspection, certification, calibration, maintenance due dates and current holds.
- Booking/handover: work pack, dates/shift, operator/competence, custody and condition evidence.
- Usage/service: hours/meter readings, productive/idle/breakdown, fuel where tracked, maintenance and repair orders.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M15-001: Register owned, hired and subcontractor equipment/tools with unique identity.
- M15-002: Track availability and location without duplicating Stores consumable balances.
- M15-003: Reserve/allocate equipment by capacity, location, dates and operator requirements.
- M15-004: Prevent overlapping bookings and allocation of unsafe/expired assets.
- M15-005: Record issue/handover/return and condition, custodian and loss/damage.
- M15-006: Schedule preventive maintenance using date/runtime thresholds; retain service history.
- M15-007: Track breakdowns, downtime, corrective maintenance and release-to-service authority.
- M15-008: Maintain calibration and inspection certificate references with QA/HSE decisions.
- M15-009: Record authorized meter readings and utilization; flag rollback/outlier entries.
- M15-010: Track rental agreement/date references through Contracts and rental invoices through Finance.
- M15-011: Raise spare/service requests through Requests/Procurement.
- M15-012: Maintain tool kits and return reconciliation at offboarding/work completion.
- M15-013: Provide cost allocation evidence using explicit policy; do not independently pay vendors.
- M15-014: Archive retired assets while preserving historical usage.

## Workflow and controls

Asset: Available → Reserved → Issued/In Use → Returned → Available; Maintenance / Breakdown / Hold prevents availability. Retirement requires approval. Service order: Open → Assigned → In Progress → Verified → Closed.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- Construction/Commissioning/Planning supplies demand.
- HR/HSE supplies operator eligibility; QA supplies calibration acceptance.
- Stores owns stocked spares/consumables; Equipment owns tracked asset custody.
- Contracts/Finance supplies rental terms and cost; Requests manages service demand.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- Maintenance/certificate/calibration due → asset owner, QA/HSE as applicable.
- Breakdown/unsafe asset → affected supervisor, equipment lead and Planning.
- Overdue return/loss/rental extension → custodian and equipment lead.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- Asset availability/booking board, utilization and breakdown dashboard.
- Maintenance/calibration calendar and custody register.
- Rental expiry and return reconciliation.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-15-01: Expired inspection prevents issue.
- AC-15-02: Conflicting bookings fail transactionally.
- AC-15-03: Asset return does not create inventory for a consumable item.
- AC-15-04: Service release retains inspection/custodian evidence.

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
