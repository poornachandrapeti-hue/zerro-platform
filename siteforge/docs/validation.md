# Validation — Foundation Release

## Passed

- 14 pytest tests on isolated SQLite with foreign-key enforcement.
- Login success/failure, HttpOnly cookie, logout token invalidation, expiry and inactive accounts.
- CSRF and trusted-origin checks; significant whitespace in passwords is preserved.
- Administrator enforcement, privileged-field rejection and organization isolation.
- Unassigned project denial, selected-discipline checks, membership administration restrictions.
- Project code uniqueness, activation/date validation and optimistic update conflicts.
- Lead-PM membership creation and deactivation guard.
- Last-active-administrator protection.
- Cross-project and invalid location-parent rejection.
- Login rate limiting and audit secret exclusion.
- TypeScript typecheck and Vite production build.
- Alembic initial migration applied on SQLite; `alembic check` reports no drift.
- PostgreSQL migration SQL generated in offline mode.
- Compose YAML parsed with expected services and dependencies.
- npm audit and pip-audit report zero known vulnerabilities for the final dependency resolution at generation time. This is not a complete security assessment.

## Not verified here

- Docker image build/Compose startup: Docker daemon unavailable.
- Live PostgreSQL behavior and concurrent multi-session transactions: no running PostgreSQL instance.
- Browser interaction/visual QA: browser binary download failed. Frontend compilation passed, but interactive/visual testing is still required.

The TestClient emits a dependency deprecation warning about future httpx2 adoption; tests still pass.

## Local acceptance checklist

1. Start Compose and verify db/backend health and migrate completion.
2. Bootstrap an administrator and sign in through the frontend.
3. Create companies and users.
4. Create a Draft project, enable disciplines, choose a lead PM, and activate after mandatory fields are complete.
5. Add participants, assignments and locations.
6. Sign in as a project user and verify administration is unavailable.
7. Verify no-project and inactive-account behavior.
8. Attempt simultaneous project edits and confirm stale updates are rejected.
9. Restart containers and verify PostgreSQL records persist.
10. Review desktop and mobile layouts and keyboard navigation.
