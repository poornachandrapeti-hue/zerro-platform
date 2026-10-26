# Top strip removal and header alignment

## Change
- Removed the dormant `ConstructionHero` import and JSX from `frontend/src/App.tsx`.
- Added a final, high-specificity responsive shell layout in `frontend/src/daylight-final.css`.
- Home and Partner now start at screen y=0 with their sidebar and header side-by-side.
- The redundant large industrial sunrise strip above the header is removed. The image remains in the daylight welcome banner.
- The project administrator text and ZerroBuild brand remain in the top header; welcome content sits directly beneath it.
- Partner uses the same shell and top alignment.

## Deployment verification
Rebuild the FRONTEND container and check the served build is the updated one. No backend, DB, or RBAC changes.

## Validation status
Structural checks completed; a live browser comparison on the user's deployment is still required.
