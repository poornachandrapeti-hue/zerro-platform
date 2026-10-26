# Internal and Partner Reference Home Layout v4

Baseline: ZerroBuild_No_Top_Strip_Aligned_Header.zip.

## Changes
- `frontend/src/daylight-final.css`: creates a continuous, full-width 240px daylight industrial header image at the top of Internal and Partner home pages; aligns menu under the hero; overlays brand, project selection, search and profile above the picture; positions welcome content within the hero and pushes KPI/cards beneath it. Keeps bright panels and role navigation.
- `frontend/src/App.tsx`: organizes partner left menu labels into vendor/supplier/contractor common portal items. Existing live destinations retained for procurement, drawings, quality and construction. Unsupported transactions intentionally use the application's existing `soon:` placeholder route and cannot execute writes. Removed earlier temporary version label.

## Verification / caveats
- ZIP integrity checked. Frontend build and browser pixel comparison have not been completed in this execution environment.
- The reference screenshot is a visual guide; actual project data remains dynamic and is never replaced with screenshot sample numbers.
- Auth, RBAC, database and backend were not modified. Existing authorization checks remain responsible for protection of partner data. Frontend navigation is not a security boundary.
