# Stores Phase 8 — Checkpoint 11: Deployment readiness (partial integration closure)

## Added
- Server-side CLI configuration preflight: HTTPS origin, explicit exact allowlist, credential minimum length; no secret logging.
- Read-only authenticated source smoke command that uses the existing bounded response, no-redirect transport and strict snapshot validator.
- Fail-closed tests for missing/unsafe configuration; explicit distinction between service-feed smoke and viewer RBAC verification.

## Run from siteforge root

```bash
export ZERROBUILD_FEED_ORIGIN=https://zerrobuild.flagestrator.com
export ZERROBUILD_FEED_ALLOWED_ORIGINS=https://zerrobuild.flagestrator.com
# Provide secret securely as ZERROR_INTERNAL_SERVICE_KEY; never commit credentials.
python -m integrations.command_center.phase8_deployment --preflight
python -m integrations.command_center.phase8_deployment --smoke --organization-id <ORG_ID> --project-id <PROJECT_ID>
python -m pytest integrations/tests/test_phase8_*.py -q
```

## External deployment blockers
- Separate Command Center backend code was not present in the supplied ZIP: register the authenticated route, resolve the viewer grant and canonical project map server-side, and call verify_project_mapping before fetch_phase8_exceptions.
- Preflight does **not** make a network call; smoke proves only server-to-server service authentication, scope and feed contract for the selected project. It does not prove browser RBAC, cross-organization isolation, UI, or QA/finance truth.
- Verify network egress/DNS policy, secrets, Docker/PostgreSQL services, frontend build, logs, and negative authorization with live services before phase closure.
- No inventory movement, accounting posting, QA approval or billing certification is created by this checkpoint.
