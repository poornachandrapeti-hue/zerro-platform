# Integration contracts and ownership

## Single source of truth

| Data / decision | Owning module | Principal consumers |
| --- | --- | --- |
| Identity, memberships, project/companies/locations | Administration / Project Details | Every module |
| Review routing, tasks, alerts | Shared coordination | Every module; final action enforced by source owner |
| Drawing preparation/technical review/construction release | Engineering | Construction, Planning, Procurement, QA |
| File bytes, revision identity, dispatch evidence | Document Control | Every module |
| Buying, PO lines, supplier commitments | Procurement | Stores, Financials, Logistics, Planning |
| Receipt, stock condition, reservations and movements | Stores | Procurement, Construction, Financials |
| Field execution and verified quantities | Construction | Quality, Planning, Progress, Financials |
| Inspections, quality acceptance/holds | Quality | Stores, Construction, Financials, Commissioning |
| Permits, safety holds and release | Safety | Construction, Commissioning, Manpower, Equipment |
| Personnel, deployment and attendance | HR | Manpower, Safety, Quality, Financials |
| Crew demand/allocation/utilization | Manpower | Construction, Planning, Financials |
| Asset identity/custody/readiness/utilization | Equipment | Construction, Planning, Safety, QA |
| Agreements, BOQ/rates/terms | Contracts | Financials, Procurement, Planning |
| Budget, certified billing, posted cost/payment | Financials | PM/Progress within commercial permissions |
| WBS, calendars, baseline/forecast/targets | Planning | Construction, resources, Progress |
| Published consolidated snapshots | Progress | Authorized management and client reviewers |
| Request intake and routing | Requirements & Requests | Receiving module owns fulfillment |
| Systems, completion gates, punch/handover | Commissioning | Project Details, Progress, client reviewers |
| Risk/issue assessment and response | Risks & Issues | Planning, PM, Changes |
| Cross-domain impact approval coordination | Change Management | Each affected owner applies its own change |
| Minutes and decisions | Meetings | Shared tasks/source modules |
| Shipment transport, slots and gate movement | Logistics | Stores, Procurement, Planning |

## Critical transaction flows

1. Request → need approval → stock check → reservation OR approved PR → RFQ/evaluation → approved PO → supplier delivery → Stores receipt → QA inspection → accepted stock → authorized issue → Construction consumption.
2. Engineering revision → review → client outcome where required → authorized construction release → work readiness. Supersession creates impact review for affected active work; it does not silently switch drawings.
3. Planning activity → readiness (drawing/material/crew/equipment/QA/HSE) → execution → verified quantity → QA acceptance → contract eligibility → bill certification → invoice → authorized payment → reconciliation.
4. HR deployment/eligibility → Manpower allocation → actual HR attendance → operational utilization → authorized financial allocation. No second attendance ledger.
5. Change proposal → all relevant impact reviews → scoped approvals → contract/budget/baseline/drawing/domain application → reconciliation → updated forecast and published progress.

## Application interface rules

- In-process commands/queries within modular monolith; no service-to-service HTTP between packages. Domain APIs return restricted DTOs, not writable ORM models from other packages.
- Gate queries return authoritative current eligibility with reasons and source/version references. Recheck at commit/action time. Dashboard cache never authorizes work/payment/issue.
- Financial commitment and inventory postings use local transactions or explicit recoverable coordination with visible pending states. Do not claim all-or-nothing across asynchronous handlers.
- Events use event_id, event_type, schema_version, organization_id, project_id, aggregate_id/version, actor_id, occurred_at, correlation_id and minimal payload. Private HR/bank/medical data stays out of general events.
- Suggested events: drawing.released/superseded; po.issued/amended; stock.received/accepted/issued; construction.quantity_verified; quality.hold_issued/released; safety.hold_issued/released; attendance.approved/corrected; contract.amended; budget.approved; bill.certified; payment.reconciled; baseline.approved; system.accepted.
- Write outbox events with source transaction. Consumers track processed event IDs and source versions, reject out-of-order updates when necessary, retry/backoff and expose failed jobs. Periodic reconciliation compares owner records with derived data.
- New permissions/scopes are enforced for event-triggered notifications and projections, not only interactive requests. Deactivation/revocation updates accessible views.

## External connector phases

MVP includes manual entry and validated file imports/exports. Optional adapters: Wrench, Primavera/MS Project, ERP/accounting, attendance devices, bank/payment provider, email and carriers. Actual adapter endpoints/auth/rate limits/signature verification must come from verified vendor/customer documentation during implementation. This requirements pack intentionally supplies no invented endpoint or claim of working vendor integration.
