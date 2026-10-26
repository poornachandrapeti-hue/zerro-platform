# ZerroBuild V11 — Approved Login + Partner Layout

## Updated UI
- Retained approved V10 login screen using `/login-sunrise.png` and the actual application authentication API.
- Added `frontend/src/partner-layout-v11.css` imported last in `frontend/src/main.tsx`.
- Fixed partner project dropdown, search, notifications, and user profile alignment.
- Kept partner hero, role selector, KPIs, activity, deadlines, and quick actions in separate grid rows/columns.
- Quick Actions switches beneath panels for mid-width desktop instead of overlapping.
- Preserved existing Internal Workspace UI, backend, database, auth API, and permission checks.

## Testing limitation
Frontend live render/build was not verified in this environment. Test at 1648x928 and smaller viewport after deployment.
