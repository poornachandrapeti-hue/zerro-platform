# Engineering drawing import changes

This patch modifies the existing ZerroBuild application, not a new service.

## Changes

- `backend/app/domains/engineering_documents/workflow.py`: project-scoped location ID mappings, precise unsupported field errors, per-row source column values, same-file duplicate detection, validation counts and active location choices. Existing `drawings.edit` permission guard remains enforced.
- `backend/app/domains/engineering_documents/router.py`: accepts location mappings in the multipart request; download XLSX template with the project's **current** active areas (permission guarded). Persisted results remain committed by the original endpoint and previews rolled back.
- `frontend/src/engineering.tsx`: project XLSX template download, location dropdown mapping/revalidate using original local file, full uploaded field preview with horizontal scrolling, sort/filter/column visibility, counts and downloadable CSV error report. Import remains an explicit confirmation after validation.
- `frontend/src/style.css`: grid and mapping styles.
- `backend/tests/test_drawing_import_mapping.py`: integration regression tests.

## Unsupported fields, by design

The existing Drawing register import supports number, title, type, discipline, company, responsible, location, planned_date, planned_submission, planned_approval, priority, work_reference and remarks. It does **not** support document type, description, approval status or revision. When these values are present, rows are explicitly rejected instead of silently dropping metadata or claiming a revision was approved. Revisions require the established file-backed controlled revision API.

No schema migration is required; no project areas are auto-created. No sample locations are hardcoded. Partial imports use the existing API behavior.

## Test results and limits

Backend integration suite: `pytest -q tests/test_drawing_import_mapping.py tests/test_engineering.py tests/test_engineering_dashboard.py` passed 10/10. Frontend build could not be run: `npm ci --offline` failed due to missing cached `yallist@3.1.1` dependency. Full Docker/browser verification is therefore **not completed**. Error report is CSV, not XLSX. Confirm compilation and test deployment in a staging environment before production use.

For security, project areas and mapping targets are validated afresh on every request; clients cannot map to an area from another project. Excel approval statuses never authorize release. Original authorization and audit commit flow remain in place. Ensure your existing production permissions and CSRF configuration are enabled.
