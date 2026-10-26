# 12. Stores & Inventory

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Own physical receipt, stock condition/custody, reservations, issues, returns and reconciled inventory.

Backend package: `supply_chain`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

Storekeeper records movement; Store Manager approves controlled postings/adjustments. QA decides acceptance/quarantine. Construction requests/acknowledges issues. Finance consumes valuation references.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- Item/material master: code, specification, UOM, approved conversion, lot/serial tracking and storage requirements.
- Receipt: PO/shipment/line, quantity/UOM, lot/heat/serial, location/bin, condition, document/inspection links.
- Stock ledger: immutable movement ID, item/lot/location, stock condition, quantity, source and posting/reversal keys.
- Reservation/issue/return/transfer/count: work pack/company/person references, balances, approvals and evidence.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M12-001: Receive partial deliveries against authorized POs; flag excess/short/damaged quantities.
- M12-002: Keep received, inspection-pending, accepted, rejected/quarantined and available stock distinct.
- M12-003: Calculate usable available quantity as accepted on-hand less active reservations; exclude held/quarantined stock.
- M12-004: Maintain warehouses/bins and lot/heat/serial traceability.
- M12-005: Reserve stock for work packs and release expired/cancelled reservations under rules.
- M12-006: Issue only eligible stock to authorized work/recipient; prevent negative balances using transactional locking.
- M12-007: Track consumed/returned/scrapped quantities; returns need condition assessment before reuse.
- M12-008: Transfer stock through dispatch/in-transit/receipt states so it is never available in two locations.
- M12-009: Support cycle counts and approved adjustments with variance evidence and maker/checker review.
- M12-010: Use immutable ledger entries and reversals; no direct balance editing.
- M12-011: Link material certificates, shelf-life/expiry and QA inspection to lots.
- M12-012: Track minimum stock/reorder suggestions through Requests; Stores does not issue purchase orders.
- M12-013: Support barcode/QR identification as a later usable feature with exact item/lot resolution.
- M12-014: Supply movement/valuation evidence to Finance; agree costing policy before claiming inventory valuation.

## Workflow and controls

Receipt: Draft → Posted to Inspection Pending → Accepted / Quarantined / Rejected by QA. Issue: Draft → Authorized → Posted → Acknowledged. Transfer: Draft → Approved → Dispatched → Received. Adjustment: Draft → Reviewed → Approved → Posted.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- Procurement owns PO; Logistics supplies shipment; QA owns condition decisions.
- Construction/Manpower/Equipment consume issues and custody records.
- Financials consumes receipt/movement evidence; Requests receives replenishment demand.
- Document Control owns certificates/files.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- Low stock/late issue/reservation shortage → Store Manager and requesting discipline owner.
- Quarantine/expired material → QA and store owner; affected work owners informed.
- Count mismatch/unacknowledged transfer → Store Manager; Finance if material.
- Receipt mismatch → Procurement buyer.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- Stock by item/lot/bin/condition, usable availability and reservations.
- GRN/issue/return/transfer registers and aging.
- Traceability, expiry and inventory variance dashboard.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-12-01: Two concurrent issues cannot create negative stock.
- AC-12-02: A receipt replay does not duplicate inventory.
- AC-12-03: Quarantined/expired lot fails issue gate.
- AC-12-04: Transfer/reversal conserves correct location balances and history.

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
