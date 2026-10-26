# 17. Document Control & Correspondence

Version: 1.0 | Status: Target requirements, not implementation completion

## Purpose and boundary

Own controlled file storage, revision identity, transmittals, correspondence and distribution evidence.

Backend package: `engineering_documents`. Read [Shared foundation](00_shared_foundation.md), [Roles](00_roles_and_access.md), [Workflows and alerts](00_workflows_tasks_alerts.md) and [Integration ownership](00_integration_ownership.md) before implementation.

## Responsible roles

Document Controller manages registers/distribution. Originators own content. Domain reviewers own technical/commercial decisions. Recipients access only granted project/company/document scope.

Apply backend project/company/discipline scope. Managerial escalation does not grant domain approval authority.

## Core records and fields

- Document: number/title/type, originator, project/company/discipline/location, confidentiality and retention.
- Revision/file: revision sequence, hash, scan status, storage reference, metadata, supersession and owner.
- Transmittal: sender/recipients, purpose, exact revision list, issue date, delivery/acknowledgment and review deadline.
- Correspondence: subject/reference, parties, category/RFI link, due date, response chain and controlled attachments.

All records also use shared IDs, organization/project scope, owner, version, timestamps and audit links. Attachments reference controlled files; no duplicate file storage.

## Functional requirements

- M17-001: Provide shared private file upload/download service for every module.
- M17-002: Validate type/size/hash and scan status; quarantine unverified files under configured policy.
- M17-003: Maintain immutable revisions and unique project-scoped document references.
- M17-004: Issue transmittals that pin revision IDs and exact recipients/purpose.
- M17-005: Track dispatch, acknowledgment and response without treating receipt as technical approval.
- M17-006: Maintain superseded/withdrawn status and notify subscribed affected consumers.
- M17-007: Support controlled correspondence, RFIs, letters and response chains.
- M17-008: Apply confidentiality, company/discipline scope and separate external distribution authority.
- M17-009: Use short-lived authorized download links where implemented; authorization checks remain server-side.
- M17-010: Support metadata search; full-text/OCR indexing is optional and must respect access controls.
- M17-011: Define retention/legal hold/archive rules; prevent deletion of referenced approval evidence.
- M17-012: Maintain file storage reconciliation, failed-upload cleanup and accessible operational errors.
- M17-013: Generate dossier manifests and published report packages from pinned revisions.
- M17-014: Engineering/Wrench import uses this service; Doc Control never overrides engineering release.

## Workflow and controls

File: Uploaded → Scanning → Available / Quarantined / Rejected. Document: Draft → Registered → Issued → Superseded / Withdrawn → Archived. Transmittal: Draft → Authorized → Issued → Acknowledged → Closed.

Validate every transition server-side against current scope, previous state, approval evidence and version. Preserve submitted revisions and decisions. Never allow an unrestricted status dropdown to bypass gates.

## Internal and optional external integrations

- Every module links controlled file IDs; technical states remain with domain owners.
- Engineering owns drawing reviews; Contracts owns notice meaning and deadlines.
- Progress/Commissioning consumes report/dossier manifests.
- Shared alerts notify review/acknowledgment deadlines.

Cross-module writes use owning-domain application interfaces. Use durable events for reporting/alerts, idempotent consumption and reconciliation. External connectors require verified specifications and remain visibly disabled until configured.

## Alerts, escalation and responsibility

- Failed/quarantined upload → uploader and document administrator.
- Overdue acknowledgment/response → recipient owner then document/functional lead.
- Revision withdrawal affecting work → Engineering/site/QA owners.
- Unauthorized external distribution attempt → audit and configured document authority.

Each alert rule defines trigger, priority, authorized recipients, SLA/calendar, deduplication and resolution. Apply shared escalation policy; overdue review never auto-approves a record.

## Screens and monitoring

- Document/revision register, transmittal and correspondence queues.
- Outstanding responses, latest issued revision and distribution history.
- Restricted file operations/audit view.

Registers support scoped search/filter/sort/pagination and authorized exports. Details show linked source records, evidence, review history, available actions and audit history. Metrics declare source, denominator, unit/currency and refresh time.

## API and implementation contract

Implement scoped list/detail/create/edit endpoints for the records above plus explicit commands for the defined transitions. Define typed input/output schemas, writable-field allowlists, version conflicts and idempotency for postings/handoffs. Add PostgreSQL migrations and permission seeds without granting future capabilities automatically to existing users.

## Acceptance criteria

- AC-17-01: Cross-project file IDs cannot be downloaded.
- AC-17-02: Transmittal remains pinned when a newer revision exists.
- AC-17-03: Quarantined evidence cannot satisfy approval prerequisite.
- AC-17-04: Dispatch acknowledgment does not mark drawing accepted.

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
