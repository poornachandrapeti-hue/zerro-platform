# Workspace Layout V8

## Design
- Internal and Partner home share the same full-width daylight industrial hero using `/hero-plant.jpg`.
- Navigation sidebar starts below the 240px hero; scrollbar is inside the sidebar.
- Header controls are right-aligned; the full-width hero contains the welcome copy.
- Partner dashboard uses its own data and action components, with actions beneath the hero rather than overlaying it.
- Responsive rules cover narrow desktop and mobile screens.

## Changes
- `frontend/src/main.tsx`: removed three competing theme imports and loaded one definitive workspace stylesheet.
- `frontend/src/workspace-reference-v8.css`: new shared workspace layout and partner-specific content arrangements.
- Deleted unused superseded `daylight-final.css`, `viewport-v6.css`, and `partner-layout-v7.css` from the delivered source.
- No backend/RBAC/schema/functionality changes.

## Verification
- Confirmed the new CSS import is last.
- Confirmed old late theme imports are gone and source assets exist.
- Frontend compilation/browser rendering not verified: npm dependencies are not installed in this environment.

## Deploy
`docker compose build --no-cache frontend && docker compose up -d --no-deps --force-recreate frontend`
