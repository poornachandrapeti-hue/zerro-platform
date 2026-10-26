# Reference UI corrections — 2026-10-15

This revision changes the actual App.tsx route contents, not just CSS.

- Logged-out users load the reference-style login (industrial picture, company login/SSO tabs; SSO is intentionally nonfunctional until configured).
- Authenticated users receive the two-card role selection.
- Internal Home now renders `frontend/src/ReferenceHome.tsx`, rather than the legacy lifecycle poster `HomePage`.
- Sidebar navigation is changed to the reference module list. Existing backend permission checks still apply.
- Partner Home is reorganized into reference-style hero, metrics, activity, deadlines and actions, retaining authorized project data and existing backend APIs.
- Placeholder statistics are displayed as em dashes, rather than presenting screenshot demo figures as real values.
- Some modules and integrations remain unfinished and their links still go to notices. This is not a backend completion claim.

## Deploy the correct copy

1. Extract this ZIP into a NEW directory. Do not merge into old source folders.
2. Run `docker compose --env-file .env -f compose.yaml down` (only when safe for the old deployment). **Do not delete volumes.**
3. Set `POSTGRES_PASSWORD` in `.env`. Use the SAME database credentials as your existing deployment when preserving its data.
4. Run `docker compose --env-file .env -f compose.yaml build --no-cache frontend` then `docker compose --env-file .env -f compose.yaml up -d`.
5. Hard-refresh browser with Ctrl+Shift+R, or use an incognito window. Confirm the changed files are the ones deployed.

Build cannot be fully confirmed here because offline npm installation fails due to missing cached dependencies; use Docker's network-enabled `npm ci` build to test locally.
