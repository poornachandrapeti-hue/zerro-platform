# ZerroBuild Workspace Home V9

## Purpose
Use the user's approved sunrise-industrial image and screenshot layout for both Internal Workspace and Partner Portal homes.

## Files changed
- frontend/public/zerrobuild-approved-daylight.jpg: optimized copy of the user's uploaded sunrise industrial image.
- frontend/src/main.tsx: replaces the V8 style import with V9.
- frontend/src/workspace-reference-v9.css: shared responsive layout for both home screens.

## Design behavior
- Same 215–245px daylight hero across the entire width at desktop sizes.
- ZerroBuild branding in the hero, project/search/notifications/profile aligned at the right.
- Sidebar under the hero, scrolling independently if screen height is limited.
- Internal: four KPIs, 12 authorized module tiles, recent activity.
- Partner: four KPIs, recent activity, upcoming items, quick actions in separate columns.
- Partner role selector, project selection, navigation, notifications, permission behavior and live backend data retained.
- Unavailable transactions remain unavailable. No screenshot sample metrics are inserted.
- This is a frontend-only change. No backend, database migration, permissions or existing module behavior changed.

## Verification
- Static source assertions and archive integrity check completed.
- npm ci --offline fails because yallist-3.1.1 is not in the local npm cache.
- Browser rendering / frontend build NOT verified. Test in staging before production deployment.

## Run
From siteforge:
  docker compose build --no-cache frontend
  docker compose up -d --no-deps --force-recreate frontend
Refresh the browser with Ctrl+Shift+R.
