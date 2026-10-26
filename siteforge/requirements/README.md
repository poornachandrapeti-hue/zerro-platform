# ZerroBuild — complete module requirements pack

Version 1.0, 2026-10-05. Contains one Markdown file for every agreed business module plus shared implementation rules. This is an actionable requirements baseline compiled from the product scope discussed; detailed workflows and controls here are proposed design decisions, not a verbatim transcript and not a claim of completed code.

## Use in Cursor

1. Extract this folder.
2. Copy it to `siteforge/requirements/modules/` in your existing source project. Keep the existing foundation/docs files.
3. Read `00_cursor_implementation_prompt.md` and paste its prompt into Cursor Agent.
4. Implement dependency-ready slices using `00_delivery_roadmap.md`. Track verified requirements in `00_coverage_tracker.md`.

The source ZIP contains Phase 1 only. This requirements ZIP does not add executable code or make the remaining modules implemented.

## Shared files

- [Shared foundation](00_shared_foundation.md)
- [Roles and access](00_roles_and_access.md)
- [Workflows, tasks and alerts](00_workflows_tasks_alerts.md)
- [Integration ownership](00_integration_ownership.md)
- [Delivery roadmap](00_delivery_roadmap.md)
- [Cursor prompt](00_cursor_implementation_prompt.md)
- [Coverage tracker](00_coverage_tracker.md)

## Modules

- [01. Project Details](01_project_details.md)
- [02. Engineering & Drawing Management](02_engineering.md)
- [03. Procurement](03_procurement.md)
- [04. Construction](04_construction.md)
- [05. Financials](05_financials.md)
- [06. Quality / QAQC](06_quality.md)
- [07. Safety / HSE](07_safety.md)
- [08. HR](08_hr.md)
- [09. Contracts](09_contracts.md)
- [10. Planning](10_planning.md)
- [11. Progress](11_progress.md)
- [12. Stores & Inventory](12_stores.md)
- [13. Requirements & Requests](13_requirements_requests.md)
- [14. Manpower](14_manpower.md)
- [15. Equipment & Tools](15_equipment_tools.md)
- [16. Commissioning, Completion & Handover](16_commissioning_handover.md)
- [17. Document Control & Correspondence](17_document_control.md)
- [18. Project Risks & Issues](18_risks_issues.md)
- [19. Change Management](19_change_management.md)
- [20. Meetings & Actions](20_meetings_actions.md)
- [21. Site Logistics](21_site_logistics.md)

## What every module file contains

Purpose/boundary; responsible roles; records/fields; numbered functional requirements; workflow and gates; integrations and ownership; alerts/escalation; screens/monitoring; API guidance; acceptance criteria; staged delivery suggestions.

Organization administration is defined in the shared foundation/roles files and in `00_administration.md`. All functional requirements inherit those shared security and integration rules.
