# 03. Procurement

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Manage approved purchasing demand, sourcing, commitments, delivery and supplier performance.

Backend package: `supply_chain`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

Requester/site engineer raises demand. Discipline Head validates technical scope. Buyer prepares RFQs/POs. Procurement Head and financial authorities approve within limits. Stores owns receipt; QA owns material acceptance.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- PR and lines: item/specification, approved drawing/MTO reference, UOM, required quantity/date, WBS/location, requester, budget/contract reference.
- RFQ/quote: supplier, validity, price/currency, tax, freight, lead time, commercial and technical deviations, attachments.
- PO/amendment: supplier, contract terms/version, lines, commitments, approval route, delivery schedule and cancellation/reversal history.
- Expediting: promised dates, dispatch/inspection evidence, shipment refs, receipt links, shortage and supplier performance.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M03-001: Convert approved Requests/material demands into purchase requisitions without duplicate lines.
- M03-002: Check usable stock and reservations through Stores before buying; display availability but do not mutate inventory.
- M03-003: Support partial requisition fulfillment and split suppliers/POs with traceable allocations.
- M03-004: Create RFQs and compare quotations with authorized technical/commercial evaluations.
- M03-005: Maintain supplier master, approved categories, qualification documents and expiry; bank data stays restricted.
- M03-006: Record technical deviations and require discipline review before commercial selection.
- M03-007: Evaluate approved budget availability through Financials; route over-budget exceptions explicitly.
- M03-008: Apply amount/currency-specific approval thresholds and separation of buyer/approver.
- M03-009: Issue POs only after required reviews; keep issued revisions immutable; amendments reapprove affected changes.
- M03-010: Track supplier acknowledgment, manufacturing, inspection, dispatch, delivery and partial receipts.
- M03-011: Handle cancellations, shortages, damaged deliveries, returns/replacements and PO closure with reasons.
- M03-012: Compute ordered/received/accepted/returned/open quantities from owning records with consistent UOM.
- M03-013: Provide invoice-match evidence to Financials; procurement does not post payments.
- M03-014: Maintain long-lead equipment/material flags and supplier delivery performance.

## Workflow and controls

PR: Draft → Submitted → Reviewed → Approved / Returned / Rejected → Partially Ordered → Fully Ordered → Closed. PO: Draft → Approved → Issued → Acknowledged → Partially Received → Received → Closed; amendments/cancellation preserve history.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- Engineering supplies revision-specific specifications/MTO; Requests owns intake.
- Stores supplies availability and posts receipts/returns; QA supplies inspection outcomes.
- Financials owns budget checks, commitments and invoice matching; Contracts supplies terms/rates.
- Planning consumes required/promised dates; Logistics consumes shipment/delivery schedules.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- PR review overdue → discipline head/Procurement Head then PM.
- Budget breach/quote expiry/unauthorized deviation → Procurement Head and Finance/Contracts as applicable.
- Late delivery or shortage threatening activity → buyer, Planning, site owner and PM.
- Repeated supplier failure → Procurement Head.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- PR/RFQ/PO registers, approval queues and expediting board.
- Ordered versus received versus QA accepted quantities; open commitments with currency separation.
- Long-lead risks, supplier on-time delivery and invoice-match exceptions.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-03-01: Concurrent PO issue cannot duplicate commitment.
- AC-03-02: Partial receipt updates the correct PO line only once.
- AC-03-03: Buyer cannot bypass approval limit or QA material hold.
- AC-03-04: Amendment retains original PO and reapproves changed commitment.

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
