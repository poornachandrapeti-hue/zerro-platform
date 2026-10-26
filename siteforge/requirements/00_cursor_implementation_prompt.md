# Cursor Agent instructions

Copy this prompt into Cursor after placing this folder at `siteforge/requirements/modules/`:

```text
Continue the existing ZerroBuild codebase. Read README.md and docs/architecture.md, module_ownership.md, implementation_status.md, connected_execution_workflow.md, next_cursor_prompt.md and validation.md. Read requirements/modules/README.md and all requirements/modules/00_*.md. Inspect current source and migrations before changing code. Follow docs/connected_execution_workflow.md. A missing owner stays missing. Do not invent a readiness result, an approval, or billing evidence.

These Markdown files describe the full target product; they are not proof of completed functionality. Keep React/TypeScript + FastAPI + PostgreSQL + Alembic + Docker Compose and the existing 10-package modular monolith. Preserve authentication, CSRF protection, organization/project/company/discipline access and existing data. Never remove database volumes to fix startup.

First get the current project running and verify login/project creation. Then finish Project Details and implement the shared approval/task/alert services. Use requirements/modules/00_delivery_roadmap.md for dependency order. Implement one delivery slice at a time; report the current module, requirement IDs covered, actual validation and remaining scope.

For the active module read its full requirement file and affected dependency files. Implement migrations, backend permissions/APIs/domain invariants, real frontend screens, internal integration, audit, alerts and meaningful tests. Each domain owns its data and final state changes. No fake statistics, placeholder approvals, unrestricted status edits or invented external vendor APIs.

Use PostgreSQL to verify migration/ledger/concurrency behavior where applicable. Run backend tests and frontend build. Update requirements/modules/00_coverage_tracker.md and docs/implementation_status.md only for verified features. Mark partial and unverified work honestly. Preserve prior decisions and referenced records.

When implementation depends on an unspecified business threshold, jurisdictional rule or vendor credential/interface, make it configurable or ask a focused question; continue independent work. Do not guess financial/legal rules or call a connector working without verification.
```

## Focus prompt for each following module

```text
Implement the next dependency-ready slice of MODULE_NAME using requirements/modules/NN_module_name.md and the shared 00_ files. Inspect existing coverage first. Complete real functionality, required authorization/approval/integration/alert paths and validation for that slice. Update coverage with actual evidence and give local run/demo steps. Do not start unrelated modules during this slice.
```
