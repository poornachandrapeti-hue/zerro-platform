# Progress Phase 17 — RBAC and policy supersession

## Implemented
- Dedicated action checks: `progress.view`, `progress.prepare`, `progress.review`, `progress.approve`, `progress.publish`, `progress.policy.approve`.
- Compatible with existing unrestricted internal Planning members during migration: `planning.manage` retains review/approval/publishing capabilities. This compatibility must be removed after roles are explicitly configured.
- Existing project/company/discipline scoping enforced server-side.
- Reviewer, approver, and publisher action checks revalidated at decision time.
- Approved stage schemes and milestone policies can be superseded by a newer draft on independent approval; earlier approved versions stay in place as `Superseded`.
- Existing policies and reporting snapshots are not overwritten.

## Not complete
- Full configurable multi-step role routing and delegation UI.
- RBAC migration that seeds dedicated permissions for every existing organization/role.
- Audit event table for stage/policy supersession and concurrency protection on version creation.
- PostgreSQL, browser and role-by-role end-to-end checks.

## Deployment considerations
- No database DDL changes introduced in this phase (status is an existing VARCHAR).
- Check existing custom roles before disabling Planning permission compatibility.
- Staging deployment and integration verification required.
