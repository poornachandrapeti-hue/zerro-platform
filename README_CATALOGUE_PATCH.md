# ZerroBuild Catalogue Specification Patch — checkpoint 1

This is an additive source patch for the supplied 2026-10-28 repository snapshot, NOT a replacement for the complete repository.

## Implemented
- Reuses existing procurement_items, authorization, item ID, and organization scoping.
- Adds built-in discipline/category specification template definitions (12 disciplines, 30+ categories).
- Adds structured specification_attributes JSON on procurement_items via Alembic migration.
- Adds authenticated GET /api/procurement/items/specification-templates.
- Extends existing ItemIn, save_item and item_payload to validate/store/return structured attributes.
- Adds dynamic text specification fields to the existing React Procurement Item creation form; UI label UOM (base unit).
- Adds 32 targeted unit tests. Run: cd siteforge/backend && python -m pytest -q tests/test_catalogue_specification_templates.py

## NOT implemented yet
- Admin-editable template definitions and UOM master CRUD.
- Dedicated catalogue approval, detailed specification change approvals/history, mass Excel template import, or QA inspection policy configuration.
- No live database migrations, Docker deployment, or full suite regression performed.
- Existing import flow doesn't yet populate structured specification_attributes.
- Frontend TypeScript build not validated (dependencies not available in extracted patch runtime).

## Apply carefully — PowerShell
cd C:\Users\NEELIMA\Desktop\zerrobuild-store
git status --short
# Backup or commit all local changes before applying this patch.
# Extract ZIP into the repository ROOT. The archive contains siteforge/ paths.
# Then inspect: git diff --check ; git diff --stat
# Run backup of database before any alembic migration.
# If repository already has a newer Alembic head, edit the migration down_revision and verify graph BEFORE upgrading.
# No automatic production deployment. Test in a staging clone first.

## Why migration safety matters
Migration down_revision points to eng_drawing_soft_delete, the single head discovered in the supplied snapshot. Your deployed instance could be ahead or on a different branch.
Existing catalogue item IDs and procurement references are unchanged. Backend item update actions without specification_attributes clear them, so future legacy UI or imports should preserve attributes on updates before production rollout.
