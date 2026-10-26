# Roles, hierarchy and access

Read 00_shared_foundation.md first. Role names describe responsibilities; explicit permissions and project assignments determine access. A user may have multiple project roles. An HR personnel record may exist without a login account.

| Role | Default operational responsibility | Access restrictions |
| --- | --- | --- |
| Organization Administrator | Users, companies, role assignments, configuration | No automatic financial, technical or safety approval rights |
| Project Manager (PM) | Project coordination, authorized project reviews, escalation resolution | Commercial/HR access requires explicit grants; cannot override QA/HSE holds |
| Planning Head / Planner | WBS, schedules, baselines, forecasting | Consumes execution facts; cannot rewrite executed quantities |
| Electrical Head | Electrical drawings, work readiness and discipline review | Assigned project/company/electrical scope |
| Mechanical Head | Mechanical/piping drawings and discipline review | Assigned project/company/mechanical scope |
| Instrumentation Head | Instrumentation drawings, loops and discipline review | Assigned project/company/instrumentation scope |
| Civil Head | Civil drawings and discipline review | Assigned project/company/civil scope |
| Site Engineer | Work packs, daily quantities, requests and inspection offers | Assigned discipline/company/location; cannot self-certify restricted records |
| Engineering Coordinator | Drawing register and review coordination | Technical approval requires relevant discipline authority |
| Procurement Head / Buyer | Requisitions, sourcing, orders and expediting | Monetary approval limits and supplier/company scope |
| Store Manager / Storekeeper | Receipts, custody, reservations, issues and counts | Cannot accept quarantined material or change contract rates |
| QA/QC Head / Inspector | Inspections, acceptance, NCRs and quality holds | Explicit inspection competence and release authority |
| HSE Head / Officer | Permits, safety controls, incidents and safety holds | Sensitive incident details restricted; release needs designated authority |
| HR Manager / Officer | Personnel, deployment and attendance | Salary, bank and medical fields separately restricted |
| Manpower Coordinator / Supervisor | Crew demand, assignments and utilization | Minimum HR eligibility/attendance data only |
| Finance Manager / Accountant | Budget, certification, invoices and settlement | Separate preparation, certification and payment authority |
| Contracts Manager / Engineer | Agreements, BOQ, terms, notices and claims | Commercial access grant required |
| Document Controller | Files, revisions, transmittals and correspondence | Can route documents; cannot grant technical acceptance |
| Equipment Coordinator | Equipment allocation, maintenance and utilization | Cannot bypass expired inspection or HSE restrictions |
| Commissioning Lead | System readiness, test coordination and handover | QA/HSE/client acceptance gates apply |
| Client / PMC Reviewer | Assigned submissions and review evidence | Explicit reviewer assignments; no broad internal commercial/HR visibility |
| Contractor / Subcontractor User | Assigned company deliverables and execution | Own-company scope unless separately granted |
| Auditor / Read-only Viewer | Authorized evidence and reports | No mutation or unrestricted sensitive-field access |

## Permission model

- Permission examples: engineering.drawings.create, engineering.drawings.submit, engineering.drawings.review, procurement.po.approve, stores.issue.post, quality.hold.release, safety.permit.issue, financials.payment.authorize.
- Scope is evaluated for each permission-bearing membership. Do not combine one role's permission with another membership's broader scope to create unauthorized access.
- Commercial, payroll/PII and confidential incident permissions are field-level as well as record-level. Mask or omit unauthorized fields from API responses and exports.
- Review delegation is explicit, time-bound, auditable and within the delegate's scope and approval limit. No reviewer can delegate greater authority than they have.
- Default separation of duties: restricted records cannot be approved by their creator; payment release must be independent from preparation. Configure documented exceptions per policy with audit evidence.
- Deactivating a user revokes sessions and routes open tasks to authorized replacements. Preserve historical signatures/decisions. Review former PM access explicitly after reassignment.

## Hierarchy

Use configurable project hierarchy: site engineer/supervisor → discipline head or function owner → PM → designated organization authority. Technical/client reviews are their own configured steps and cannot be replaced by managerial escalation. HR, finance, QA and HSE each have a function-specific hierarchy.

Missing reviewer configuration blocks submission with a clear setup task. Never route silently to an arbitrary administrator. Alert recipients must have permission to see the record; email/push notifications must avoid confidential content.

## Acceptance

Test same-project wrong-company access, wrong-discipline access, cross-project IDs, cross-organization IDs, export/file access, revoked membership, delegated approval expiry, monetary-limit rejection, field masking and creator self-approval prevention.
