# Delivery roadmap and dependency order

Numbering organizes requirements; it is not a command to implement every module sequentially or all at once.

| Stage | Implement | Required result |
| --- | --- | --- |
| A | Current foundation startup; Administration; complete Project Details | Working login, scoped memberships, project setup and migrations |
| B | Shared workflow/tasks/alerts; Document Control file service | Real authorization, review routing, audit, private files and durable alerts |
| C | Engineering + basic Planning + basic Contracts + Financials budget | Released drawings, WBS/targets, effective scope/rates and spending authority |
| D | Requests → Procurement → Stores + material QA | Complete approved demand-to-accepted-stock flow |
| E | HR → Manpower → Equipment + Safety readiness | Eligible workers/assets/permits and current hold checks |
| F | Construction + execution QA | Ready work → verified quantities → accepted work with reversals |
| G | Planning forecasts + Progress + Financials certification/payment | Traceable period reporting and controlled billing/settlement |
| H | Commissioning & Handover | Accepted systems, punch closure and pinned dossiers |
| Continuous | Risks, Changes, Meetings, Logistics | Cross-domain controls enabled before any dependent flow needs them |
| Later | Verified Wrench/ERP/schedule/attendance/bank/carrier adapters | Configured contracts, security, reconciliation and truthful connector health |

Stages may need small enabling slices of later modules. For example Change Management must exist before a controlled baseline/contract amendment flow; Logistics can start with manual shipment links before advanced gate scheduling. Maintain one authoritative owner throughout.

## Business settings to configure before relevant release

Approval hierarchy/limits and separation of duties; client review codes and construction-release meaning; QA ITP/acceptance templates; HSE permit/isolation/emergency policies; stock UOM/expiry/costing rules; contract billing/retention/tax/deduction terms; schedule calendars/weights; HR privacy/attendance/overtime; alert SLAs; retention; external connector interfaces.

Do not block basic registers on every optional setting. Block the specific business action whose mandatory configuration is missing, explain why and identify the configuration owner.

## Operational release checks

PostgreSQL migrations and upgrade path; local Compose startup; no default production credentials; authorized real-data UI; negative access tests; ledger/state retry and concurrency tests; restore/reconciliation checks; durable job failures visible; exports/private-file access; coverage tracker and known limitations updated. Production HTTPS, secrets, backup/restore and operational monitoring are deployment work, not implied by laptop startup.
