# Architecture

One React application and one FastAPI deployment. This is a modular monolith with ten domain boundaries, not ten deployed microservices.

| Package | Responsibility |
| --- | --- |
| identity_projects | Organizations, login, users, roles, companies, projects and assignments |
| coordination | Approvals, tasks, requests, meetings, risks, change coordination |
| engineering_documents | Drawings, revisions, controlled documents and transmittals |
| supply_chain | Purchasing, stores, inventory and logistics |
| construction_completion | Execution, commissioning and handover |
| quality | Inspections, acceptance, NCRs and quality holds |
| safety | Permits, risk assessments, incidents and safety holds |
| resources | HR, manpower, equipment and tools |
| commercial_financials | Contracts, terms, budgets, certification and settlement |
| planning_reporting | WBS, schedules, baselines, progress and reports |

`identity_projects` owns organizations, login, companies, users, projects, memberships and locations. `coordination` owns approval policies, review decisions, tasks, notifications and durable jobs. `engineering_documents` owns stored file bytes, the drawing register, revisions, review comments, construction release and drawing transmittals. A Wrench adapter stores configuration and manual external identifiers and stays disabled. Project screens call those services. Supply chain, construction, quality, safety, resources, commercial and planning packages are not implemented. Email delivery is disabled.

## Future extraction rules

Each domain owns its tables and writes. Other domains consume public application interfaces and documented events. Do not build inter-service HTTP calls inside this monolith. Keep common code limited to technical concerns.

When domains become services, access their data through APIs/events. Stock reserve/issue remains local to supply chain. Financial certification/posting remains in its owning domain. Workflow routing does not independently authorize a domain mutation.

Use an outbox, idempotent consumers and reconciliation when implementing asynchronous business events. These components are not yet implemented.

Dashboard data may be eventually consistent. Mandatory HSE/quality/authorization checks must use authoritative current information and fail closed if it cannot be verified.

The role catalogue includes future roles but their only current permission is project overview access. PM additionally has project edit and area management. Future permissions require explicit definition and tests.
