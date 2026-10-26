# Shared foundation and implementation rules

Version: 1.0 | Product: ZerroBuild | Requirements baseline: 2026-10-05

These files describe the target product. They do not assert that the features already exist. The separate foundation source ZIP implements authentication, basic administration, project access and a first Project Details implementation. Cursor must inspect actual code and migration history before estimating or implementing any requirement.

## Architecture

One React + TypeScript frontend, one FastAPI modular backend, PostgreSQL, Alembic and Docker Compose. Use the existing ten backend packages. Do not introduce microservices, Kubernetes or Kafka for the initial implementation. Background jobs may run separately using the same application packages. Introduce an outbox when durable asynchronous business events are needed.

| Backend package | Modules |
| --- | --- |
| identity_projects | Administration; Project Details |
| coordination | Shared approvals/tasks/alerts; Requests; Risks; Changes; Meetings |
| engineering_documents | Engineering; Document Control |
| supply_chain | Procurement; Stores; Logistics |
| construction_completion | Construction; Commissioning & Handover |
| quality | Quality |
| safety | Safety |
| resources | HR; Manpower; Equipment |
| commercial_financials | Contracts; Financials |
| planning_reporting | Planning; Progress |

## Mandatory requirements for every module

- SF-001: Enforce organization isolation and project membership in the backend for reads, mutations, searches, exports, files and background jobs. A guessed ID must not reveal another project's record.
- SF-002: Evaluate action permission plus company and discipline scope. Explicit ALL or SELECTED discipline scope is required; missing scope grants no access. Location scope may further restrict access, never widen it.
- SF-003: Use immutable internal IDs, project-scoped human references, created/updated actor and UTC timestamps, business date, version and audit references. Display timestamps in the project's IANA timezone.
- SF-004: Drafts allow partial data; submissions validate required fields. Enforce uniqueness, valid parent relationships and nonnegative quantities where applicable. Do not silently reuse an ID after a duplicate human reference.
- SF-005: Every approval route identifies accountable owner, approvers, due dates and escalation recipients. The shared workflow records the decision; the owning business domain authorizes and applies its state change.
- SF-006: Maintain immutable decision history. Submitted revisions cannot be overwritten. Return for correction creates an editable revision while retaining the original. Revocation requires permission, reason and downstream impact handling.
- SF-007: Implement server-side pagination, filter/sort allowlists, validated search, role-aware detail pages, clear empty/error/loading states and authorized exports. Export filters and access scope must match the screen.
- SF-008: Store decimal quantities and money with explicit UOM/currency. Define precision and rounding per master/configuration. Conversions must be approved and traceable. Never add unlike units or currencies.
- SF-009: Concurrency: conditional version updates for editable records; transactions and appropriate locks for inventory, balances and transitions. Return conflict responses with actionable messages. Idempotency keys prevent duplicate submissions/postings.
- SF-010: Attachments use Document Control's file service with private storage, file size/type allowlists, malware scan/quarantine where enabled, content hash, authorized download and retention rules. Failed or quarantined uploads cannot serve as approval evidence.
- SF-011: Audit meaningful mutations, decisions, permission changes, sensitive access and exports. Never log passwords, session tokens, connector secrets, bank details or private medical information.
- SF-012: Keep authoritative holds and authorization synchronous. If current safety, quality or required approval evidence cannot be verified, deny the gated action. Reporting snapshots may be eventually consistent and must show their refresh time.
- SF-013: Integrations are explicitly configured per organization/project. Encrypt secrets, map external IDs, track import batches, validate payloads, expose conflicts, retry safely and reconcile failures. Do not invent vendor endpoints or credentials.
- SF-014: Define data retention, backups and restore tests before production use. Referenced posted records are archived or reversed, not hard deleted. A restore must retain audit and ledger consistency.
- SF-015: Create migrations, real APIs, usable UI and meaningful tests together. Do not mark a requirement complete because a menu, placeholder or mock data exists.

## Common API and UI contract

- Use existing `/api` routes and naming conventions. Domain commands use explicit actions such as submit, approve, issue or reverse, rather than allowing clients to PATCH arbitrary status values.
- List responses return items, total, page/cursor metadata and applied filters. Detail responses expose only authorized fields and include version plus available actions.
- Use 401 for missing/expired login, 403 for forbidden actions, scoped 404 for inaccessible objects, 409 for duplicate/concurrency/state conflicts and validation responses for invalid fields. Never expose SQL or secrets.
- Mutation requests include CSRF protection for cookie sessions. Preserve existing session security. Include a request/correlation ID for operational troubleshooting.
- Use typed schemas and reject unknown writable fields. Treat frontend permission checks as presentation only.
- Each record screen includes overview, domain details, linked records, controlled attachments, review history and audit tabs where authorized.
- Imports provide template, dry run, row-level validation, duplicate detection and a downloadable result. Exports avoid spreadsheet formula injection.

## Shared masters

Organization/company, project, discipline, location hierarchy, UOM/conversions, currencies, calendars/shifts, document types, priority/severity, reason codes and approval policies. Domain masters such as inspection templates and material catalogs stay with their owner. Retired masters remain readable for historical records.

## Release definition

A feature is complete only when migrations run on PostgreSQL, scoped APIs and UI work, required approvals/alerts integrate, negative authorization cases pass, workflow/ledger concurrency is verified where relevant, and documentation records limitations. Test integrations against verified interfaces or explicit local test adapters; never label an unverified external connector production-ready.
