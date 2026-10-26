# Connected execution workflow

Checked against the code on 2026-10-09. This is the standing path for execution work:

Released drawing → material readiness → eligible crew → safety permit → execution → QA acceptance → billing.

The product follows this path in pieces. It does not yet enforce it as one chain. A later module implements only the step whose owning records exist. A missing owner stays documented here. It is not filled with a typed note, a dashboard count, or a status that means the work may start.

Each module keeps its own records and its own decision. Construction, Quality, Safety, Stores, and Financials read another module by its id. They do not copy stock balances, attendance, approval decisions, or quantities into a second ledger.

## Coverage

| Step | State | What the code does now | Still open |
| --- | --- | --- | --- |
| Released drawing | Partial | A work package stores `drawing_revisions.id` on `work_package_drawings`. Release and start refuse a linked revision that is not still Released. A newer release marks the previous revision Superseded and notifies the responsible engineer and the lead PM. Supersede or withdrawal sets `work_packages.impact_state` to Review required on every Draft, Ready, In Progress, or On Hold package linked to that revision (package link or activity link), and sends a task and a notice to the responsible engineer and supervisor. Daily progress is refused until the responsible engineer relinks to a released revision of the same drawing or accepts with a reason. | No drawing is required when the package has no Drawing check. |
| Material readiness | Partial | A package stores `material_requirements.id`. Release and start call `material_gate`. Each item must be covered by stock reserved for this package (`stock_postings.package_id`) plus stock already issued from that reservation. Project stock with no package is not counted. A quality hold on the item blocks the check. A Material issue check, when added, needs the full quantity issued. A typed note cannot mark the check Satisfied. No linked requirement stays Pending. | Material rejection after start does not reopen a package. Stock expiry is not stored. |
| Eligible crew | Partial | When the package has a Manpower check, it is Ready only when every activity due on the date has a confirmed Manpower assignment that still passes the allocation check (availability, eligibility, overlap). Release uses the later of today and planned start; start uses today. With a Mandatory Manpower check, a daily labour line needs a confirmed assignment for that person, activity, and date. A daily line can store crew text. HSE eligibility can block start when a saved rule says the named evidence is missing or expired. A missing rule does not block. | HR has a personnel register, project deployments with owner-verified onboarding checks and approval, workforce requests with allocation and shortfall, project crews with dated members, reviewed attendance with corrections and period locks, approved leave that lowers availability and flags crews and allocations, and approved overtime kept apart from attended and payable. HR keeps qualifications verified by their owner (HR, HSE, or QA/QC) and project requirements by project, package, or activity. Construction does not assign HR crews to activities. Daily lines can carry per-person labour hours for mobilized HR personnel, are blocked when the person lacks a required qualification for the activity, and HR reconciles them to approved attendance. Demobilization needs a completed checklist and an approval, and HR raises workforce alerts that escalate. A crew line is not attendance. |
| Equipment | Missing | A daily line can store equipment hours. An HSE equipment hold does not stop a package. | The equipment register is closed. There is no allocation, operational status, inspection, or calibration certificate from Equipment. Quality calibration is a Quality record and is not that register. |
| Safety permit | Partial | Permit, isolation, field rule, and safety hold are rechecked on release, start, resume, and daily progress. An expired, suspended, or authorized-but-not-active permit blocks the work it covers. An activity permit does not cover the rest of the package. A formal safety hold blocks the work it names. A concern does not. | The Permit readiness row is read live: Ready needs an active package-level permit and no permit, field-rule, or safety-hold block. An activity permit alone leaves the package row Pending. |
| Execution | Partial | Start requires the package to be Ready and Released, then rechecks the saved readiness rows and the live quality, permit, field, and safety-hold blocks. Daily progress stores reported quantity. Approval of the report stores verified quantity. A correction keeps the original line and posts a reversal. | Release is for the whole package. There is no partial release by quantity, location, or activity. Planning activity and BOQ item are not ids. `planning_reference` is text. |
| QA acceptance | Partial | An inspection offer and a construction inspection request store accepted quantity for the verified quantity still waiting. An approved ITP revision is required before that form is used. A quality hold blocks the action it names: material issue, construction work, or handover. Accepted quantity is kept apart from certified quantity. | Prerequisite inspections are not a live package gate unless a hold or an inspection request says so. QA acceptance does not make the quantity billable. |
| Billing | Missing | Verified and accepted quantities are shown. `certified_quantity` is always null. Vendor invoices record amounts against a purchase-order line and refuse a quantity already invoiced on that line. | Contracts and Financials are closed. There is no contract-eligible quantity, certified amount, or paid amount for executed work. Invoice matching and payment are closed. |

## 1. Common linking

A work package already stores project, company, discipline, and location as ids: `project_id`, `company_id`, `discipline_id`, `area_id`. Cross-project ids are rejected on the commands that exist.

| Link | Authoritative id | State |
| --- | --- | --- |
| Planning activity | Planning owns it. Not built. | Missing. `planning_reference` is text. |
| Contractual scope / BOQ item | Contracts owns it. Not built. | Missing. |
| Drawing revision | `drawing_revisions.id` | Partial. Optional. Live release state is checked when a revision is linked. Supersede or withdrawal opens a package impact review. |
| Material requirement | `material_requirements.id` | Partial. Release and start recheck stock reserved for and issued to the package. The check does not reserve or issue stock. |
| Reservation and issue | `stock_postings.package_id`, `stock_postings.source_posting_id` | Partial. A reservation can name a work package. An issue can draw from a reservation, which lowers reserved and on-hand together. A drawn reservation cannot be cancelled; cancelling the issue restores the reservation. A daily line can still name a posting; the posting quantity is not the installed quantity. |
| Crew assignment | Manpower `mp_assignments` | Partial. A Manpower readiness check reads confirmed assignments on the package activities. Crew text stays on the daily line. |
| Equipment assignment | Equipment. Not built. | Missing. Hours text on the daily line. |
| Safety permit | `hse_permits.id`, matched to the package or activity | Partial. Enforced at start and progress for the work the permit covers. |
| Quality inspection requirement | Quality ITP and inspection request ids | Partial. Used when an inspection is raised. Not required before every start. |
| Execution measurement | `progress_lines.id` | Present for reported and verified quantity. |
| QA outcome | Inspection offer and inspection request ids | Present for accepted quantity. |
| Billing allocation | Financials. Not built. | Missing. |

## 2. Work readiness

Construction has a readiness panel. Each row shows a live result of Ready, Blocked, Pending, or Not Applicable, with the reason and the owning module. Drawing, Material, Material issue, Manpower, Permit, and Quality hold are computed from the owning module on every read and at release and start; they cannot be marked Satisfied unless the live result is Ready, and they can never be Not Applicable. Every other row is manual evidence, can be Not Applicable with a reason of at least 10 characters, and keeps the sentence: “Manual evidence only. No inspection, permit, or schedule record was created.”

The target panel, once the owner exists, shows each check as Ready, Blocked, Pending, or Not Applicable, with the reason, the responsible owner, and a link to the source record.

| Check | Current result | Owner when the source exists |
| --- | --- | --- |
| Drawing released for construction | Live when a revision is linked. Superseded or withdrawn fails the drawing gate and opens a package impact review. | Engineering |
| Materials accepted, available, and reserved | Live from the requirement lines and the package's own reservation. Pending when nothing is linked. | Stores, with Procurement for the requirement |
| Issues completed before the activity | Live when a Material issue check is added: the full quantity must be issued from the package reservation. | Stores |
| Quarantined, expired, or held stock excluded | On-hand accepts only quality-accepted receipt quantity. Issue refuses a quality hold on the item. The package panel does not show this. | Stores / QAQC |
| Crew deployed, assigned, and eligible | Live from confirmed Manpower assignments on the activities due. An HSE eligibility rule can also block. | HR / Manpower, with HSE for induction evidence |
| Equipment allocated and operational | No equipment id. | Equipment Coordinator |
| Permit approved and inside validity | Live block on start, resume, and daily progress. | HSE |
| Controls and isolation evidence | Isolation removal is refused while a dependent permit is in force, unless the saved procedure allows it. | HSE |
| No active safety hold | Live block. A concern is excluded. An equipment-scoped hold does not stop the package. | HSE |
| Approved ITP or procedure | Required when a construction inspection form is used. Not required to start. | QAQC |
| Prerequisite inspections accepted | Not a start gate. | QAQC |
| No blocking quality hold | Live block for the action named on the hold. | QAQC |

Not Applicable is allowed only after an authorized person records that determination on the source, with the actor and the revision. A closed module, a missing id, or an empty rule is Pending or Blocked. It is never Ready and never Not Applicable.

## 3. Gates

These commands recheck the source rows in the same request. A dashboard payload is not an authorization.

| Command | Rechecked now |
| --- | --- |
| Work-package release approval | Saved readiness rows, linked drawing still Released, quality hold on work release |
| Start | Quality hold, permit, HSE field rule, safety hold, package Ready and Released, saved readiness rows, linked drawing |
| Resume | Same live quality, permit, field, and safety-hold checks. The saved release reviewer approves resume. |
| Daily progress | Package not on hold, quality hold, permit, field rule, safety hold, package In Progress and Released |

Permit expiry and a new safety or quality hold already stop start, resume, and further daily progress. Lines already approved stay in history. A reversal is a new line. The original line stays.

Drawing supersede and withdrawal open a package impact review with a task to the responsible engineer. These invalidations are not built: material rejection clearing a package that already started, and a notification to each responsible owner from one readiness result. In-app notices exist inside Engineering, Quality, and HSE for their own records. Email and SMS stay off.

Partial release is not built. A released package is the whole package. A later slice may release a named quantity, location, or activity only when that slice’s own prerequisites are satisfied. The rest of the package stays unreleased.

## 4. Quantity and billing

These figures stay in separate fields. One number is not copied into the next.

| Figure | Where it lives now |
| --- | --- |
| Reported quantity | Daily line before the report is approved. Rework is excluded from verified progress. |
| Verified executed quantity | Approved daily report. A correction reverses through a new line. |
| QA-accepted quantity | Accepted inspection offer or construction inspection outcome. |
| Contract-eligible billable quantity | Not stored. Contracts is closed. |
| Certified quantity / amount | Stored as null. |
| Invoiced amount | Vendor invoice quantity against a purchase-order line. This is not construction billing. |
| Paid amount | Not stored. Payment is closed. |

QA acceptance stores accepted quantity and leaves certified quantity null. Financials, when opened, has to read the contract measurement rule, the effective rate, the required approval, and earlier allocations. An accepted installation quantity does not become a claim by itself.

Duplicate protection that exists today: one open quality hold per scope, one invoice quantity remaining on a purchase-order line, progress corrections by reversal, and a version check that rejects a stale submit. A construction billing claim does not exist, so it cannot yet be duplicated.

## 5. Responsibilities and alerts

Blockers stay with the module that can clear them. A notification does not approve, release, or certify.

| Blocker | Owner | What is notified now |
| --- | --- | --- |
| Drawing | Engineering | Responsible engineer, then discipline heads with review authority, then the lead PM, for overdue preparation, review, and comment response. Supersession notifies the engineer and the lead PM. |
| Materials | Stores / Procurement | No package-level material blocker is raised. |
| Crew eligibility | HR / Manpower | No HR record. HSE can notify watchers for its own eligibility and induction records. |
| Equipment | Equipment Coordinator | No equipment register. |
| Permit or safety hold | HSE | In-app notice to the people the HSE record already watches. |
| Inspection or quality hold | QAQC | In-app notice for expired qualifications, calibrations, and overdue NCRs when the quality dashboard is opened. |
| Execution verification | Discipline Head | The saved construction reviewer verifies the daily report. That verifies quantity only. |
| Billing eligibility | Contracts / Financials | Not built. |

Planning and the package supervisor are not on a shared escalation chain. The shared job runner can escalate a task by adding a notification. That escalation does not bypass a technical, QA, HSE, or financial decision.

## 6. Boundaries

- Engineering decides construction release of a drawing. Construction reads `release_state`.
- Stores decides on-hand, reserved, and issued quantity. Construction may cite the posting id.
- Quality decides material acceptance, inspection outcome, and quality-hold release.
- HSE decides permit activation and safety-hold release. An organization administrator or project manager does not release a safety hold by role.
- Construction decides verified quantity. Approval of a handover dossier marks the package Handed Over and does not accept quality or certify billing.
- Financials will decide certified and paid amounts. Those commands are not open.
- Domain code calls the owner’s function in process, as `permit_block`, `work_blocked`, and `hold_block` already do. The caller rechecks at the command.
- Notifications use the existing notification source key so a repeated event stays one row. A durable outbox for cross-module reporting is still a remaining job, not a second approval path.

## 7. Acceptance tests

The tests below are the target for this chain. A row is covered only when the named test asserts that behavior. Untested rows stay open.

| Test | Evidence now |
| --- | --- |
| All required gates satisfied and work can start | Partial. `test_release_follows_saved_reviewer_and_readiness` starts after the saved checks and a released drawing. Crew, equipment, reserved material, and an approved ITP are not required. |
| Any required gate fails and work is blocked with a reason | Partial. Drawing, quality hold, permit, field rule, and safety hold each return a reason. Material, crew, and equipment do not. |
| Permit expiry or a new hold stops further progress | Covered for the permit and the holds that name the package or activity. Recorded lines stay. |
| Wrong project, company, or discipline is rejected | Covered on the commands that take those ids. There is no single chain test. |
| Partial readiness cannot release the entire package | Open. Release is already entire, and partial release does not exist. |
| Executed quantity rejected by QA cannot pass billing eligibility | Open. Accepted quantity is stored and certified quantity stays null. Billing eligibility is not implemented. |
| Repeated submits cannot duplicate quantities or claims | Partial. Progress reversal and purchase-order invoice remaining quantity are tested. Construction claims are not. |
| Every decision names the actor and the source revision | Partial. Reviews, release snapshots, and progress lines store actor and version. A readiness Not Applicable decision does not exist. |

## Rule for the next module

When a slice adds a real link or a real gate, update this document and `requirements/00_coverage_tracker.md` in the same change. Name the owner, the id, the command that rechecks it, and the test. Leave the status Missing until that evidence exists.
