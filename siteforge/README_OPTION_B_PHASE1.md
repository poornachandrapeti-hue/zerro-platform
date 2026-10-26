# ZerroBuild Consolidated Source — Option B Phase 1

This archive contains the original source plus the Phase 1 UI implementation of the redesigned internal homepage and partner workspace. It is **not** the completed three-differentiator platform.

## Applied
- Redesigned internal home and login presentation (existing authentication unchanged).
- Partner navigation and partner workspace preview. Role tabs are views, not external RBAC grants.
- Existing source modules, backend authentication and notifications retained.

## Not yet implemented
- Secure external company/partner onboarding and backend authorization isolation.
- Live partner-filtered RFQ/PO/construction/invoice endpoints and partner dashboard aggregates.
- Full revision-to-procurement-to-quality-to-billing impact graph.
- Complete billing/contract/payment services and traceability explorer.

## Run / verify
- Set environment variables using .env.example; no .env secret file is included.
- Frontend: `cd frontend && npm ci && npm run build && npm run dev`.
- Backend: follow the original deployment documentation and configure dependencies/database.
- Test all existing internal roles, approval flows, notifications and restricted routes before deployment.
- Do not onboard external companies until backend company-level data isolation has been implemented and penetration-tested.

## Build status
A frontend build was attempted in an incomplete local node_modules directory; type-definition packages were missing, so the build could not be verified. Run npm ci in your own environment first.
