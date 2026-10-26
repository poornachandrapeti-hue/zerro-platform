# Visible login-background fix

Root cause: `frontend/src/main.tsx` imports `src/home/design.css` AFTER `src/style.css`. The later CSS kept `construction-scene.png` as a home pseudo-element and placed opaque background gradients over the main content. Hence earlier `style.css` updates did not visibly change the Home canvas.

Changes:
- `frontend/src/home/design.css`: Home shell uses the existing `/hero-plant.jpg` from login, removes the competing image, makes main transparent, keeps sidebar contrast.
- `frontend/src/style.css`: Module-page shell and main use the same login background without changing functional components.

No backend, database, import workflow, or RBAC edits.

Verification: inspect in browser, including Home, Partner and an inner module, after building the frontend image and ensuring the correct site is served. No live browser build was run in this environment.

Run from `siteforge`: `docker compose build --no-cache frontend && docker compose up -d --force-recreate frontend`. Check `docker compose ps` and port / reverse-proxy routing; then hard-refresh.
