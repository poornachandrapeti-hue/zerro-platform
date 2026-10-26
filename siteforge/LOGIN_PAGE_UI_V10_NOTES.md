# Login Page UI V10

This package updates the ZerroBuild login page to match the approved sunrise industrial login design.

## What changed
- Added the sunrise industrial image as the login page background (`frontend/public/login-sunrise.png`).
- Reworked the login page layout in `frontend/src/App.tsx`.
- Added final login-page styling overrides in `frontend/src/style.css`.
- Preserved the existing login API call and session behavior.
- Kept the rest of the application (internal workspace, partner portal, RBAC, backend, import workflows) unchanged.

## Files changed
- `frontend/src/App.tsx`
- `frontend/src/style.css`
- `frontend/public/login-sunrise.png`
