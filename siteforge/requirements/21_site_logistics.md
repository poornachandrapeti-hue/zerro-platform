# 21. Site Logistics

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Coordinate shipment movement, delivery slots, site access, unloading and transport evidence.

Backend package: `supply_chain`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

Logistics Coordinator schedules deliveries. Procurement/transport owner provides shipment data. Security/gate user records authorized arrivals. Stores owns material receipt; HSE controls movement/lifting safety conditions.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- Shipment: PO/lines, supplier, transport/carrier, dispatch quantities, expected arrival and packing documents.
- Delivery slot: gate/location, time window, unloading resources, contact and capacity constraints.
- Gate/movement: vehicle/driver permitted references, check-in/out, access evidence and route.
- Delivery exception: shortage/damage/delay, receiving handoff, proof of delivery and return trip.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M21-001: Plan inbound/outbound shipments and link exact PO/material/asset references.
- M21-002: Book delivery/unloading slots with site capacity and calendar rules.
- M21-003: Check access authorization, safety induction and lifting/unloading readiness.
- M21-004: Record dispatch, in-transit, arrival, gate entry, unloading and exit timestamps.
- M21-005: Distinguish transport proof of delivery from Stores GRN and QA acceptance.
- M21-006: Coordinate partial deliveries, failed delivery, damage and return transport.
- M21-007: Manage internal transport requests linked to work location and resource readiness.
- M21-008: Keep sensitive driver/vehicle documentation access restricted and retention-controlled.
- M21-009: Provide carriers/suppliers only scoped appointment information if external portal is implemented.
- M21-010: Support manual status/evidence entry; GPS/carrier connectors remain optional verified integrations.
- M21-011: Track demurrage/waiting/delay evidence for Contracts/Finance without posting cost.
- M21-012: Coordinate emergency access/evacuation changes with HSE site policy.

## Workflow and controls

Shipment: Planned → Dispatched → In Transit → Arrived → Unloading → Delivered → Closed; Delayed/Exception tracks actual disruption. Appointment: Requested → Confirmed → Checked In → Completed / Cancelled.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- Procurement supplies shipment/PO; Stores posts authoritative receipt.
- HSE/Equipment supplies unloading/access readiness; Planning supplies required dates.
- Contracts/Finance consumes permitted transport/demurrage evidence.
- Document Control stores packing/proof/access evidence.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- Late shipment/slot conflict → Logistics, buyer, Stores and affected Planning owner.
- Unsafe unloading/access denial → HSE and site supervisor immediately.
- Damage/shortage → Procurement/Stores/QA; demurrage → authorized Contracts owner.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- Shipment board, delivery calendar, gate log and exception register.
- On-time arrival, waiting/unloading time and receiving handoff status.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-21-01: Proof of delivery cannot increase inventory balance.
- AC-21-02: Capacity-conflicting slot is rejected under concurrent booking.
- AC-21-03: Unauthorized vehicle cannot pass gate approval.
- AC-21-04: Partial shipment handoff links correct PO quantities once.

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
