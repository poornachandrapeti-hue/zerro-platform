# Daylight theme deployment verification

The daylight styles are loaded last from `frontend/src/daylight-final.css`. A small fixed label `Daylight UI · 2026-10-15 B` is visible at the lower-right of authenticated application screens. This marker is temporary and can be removed when deployment is confirmed.

1. Extract this ZIP into a new folder and preserve your existing `.env`. Do not overwrite the production database.
2. In `siteforge`, execute `docker compose build --no-cache frontend`.
3. Run `docker compose up -d --no-deps --force-recreate frontend` if the backend is already running.
4. Run `sh scripts/verify_frontend_deployment.sh`.
5. Refresh the live site. Confirm the visible release marker.

If the marker is absent, the live site is using an old build, a different deployment, or cached content. Check your website reverse proxy and the frontend container shown by `docker compose ps frontend`.

Only frontend theme and the visible release marker changed. No backend or RBAC alterations. Frontend production build has not been executed in this environment.
