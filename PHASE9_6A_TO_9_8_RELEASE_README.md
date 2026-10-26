# ZerroBuild Phase 9 — consolidated 9.6A + 9.6B, 9.7 verification and 9.8 release candidate

Baseline: user-uploaded `ZerroBuild_Phase9_Current(4).zip`, containing Phase 9 up through Checkpoint 9.5B. The included Checkpoint 9.6A backend patch is applied to that exact baseline. The remaining additions are the Command Center frontend monitoring UI, bounded proposal-status drill-down, and release validation instructions.

## Scope and limitations

- **9.6A**: Source service journal-proposal snapshot and Command Center authorized readback route; included in consolidated bundle.
- **9.6B**: Command Center *frontend* status monitor and source-movement/proposal reference table, role-/project-change reset, fail-closed polling; included.
- **9.7**: 105 Finance/Stores Python tests and 23 Command Center backend tests passed in the authoring environment. Frontend build NOT verified: offline environment lacks full `vite/client` npm type package; requires `npm ci && npm run build` on your machine. Docker/database/service-to-service/browser end-to-end verification remains outstanding.
- **9.8**: This is a **release candidate**, not a live deployment. No Docker stack was recreated, no migration was applied, and production readiness has **not** been established.
- Actual authoritative GL journal writing remains **unimplemented**. In the source, only proposal/approval/preview tracking and a nonposting adapter contract exist. Do not advertise GL posting or certified financial figures.
- The monitoring source provides at most 200 recent proposals; counts summarize the sample, not whole-project balances. Never display this as cost booking or inventory valuation.
- The frontend files changed under `zerro-project-command-center/frontend` are the Command Center frontend. The root `docker-compose.unified.staging.yml` builds **siteforge/frontend**, not the Command Center frontend. A separate deployment/build of the Command Center frontend is necessary to see the new UI. DO NOT change compose without deciding the app's intended serving domain and current volume/port mapping.

## Apply safely (ONE local repository; ONE push after all checks)

Extract the patch ZIP to Downloads, then paste this into PowerShell:

```powershell
$ErrorActionPreference = 'Stop'
$repo = "$env:USERPROFILE\Desktop\zerrobuild-store"
$archive = "$env:USERPROFILE\Downloads\ZerroBuild_Phase9_Consolidated_6A_to_9_8_RC.zip"
$unpack = "$env:USERPROFILE\Downloads\ZerroBuild_Phase9_Consolidated_RC"
Set-Location $repo
if ((git branch --show-current) -ne 'feature/stores-finance-phase9') { throw 'Wrong branch' }
if (git status --porcelain) { throw 'Uncommitted changes: review before applying' }
Expand-Archive -LiteralPath $archive -DestinationPath $unpack -Force
$files = @(
  'siteforge/backend/app/domains/commercial_financials/phase9_command_center_feed.py',
  'siteforge/backend/app/main.py',
  'siteforge/backend/tests/test_phase9_command_center_feed.py',
  'zerro-project-command-center/backend/app/routers/phase9_finance.py',
  'zerro-project-command-center/backend/app/main.py',
  'zerro-project-command-center/backend/tests/test_phase9_finance_bridge.py',
  'zerro-project-command-center/frontend/src/api.ts',
  'zerro-project-command-center/frontend/src/App.tsx'
)
foreach ($f in $files) {
  $source = Join-Path (Join-Path $unpack 'zerrobuild-store') ($f.Replace('/', '\'))
  $destination = Join-Path $repo ($f.Replace('/', '\'))
  if (!(Test-Path -LiteralPath $source)) { throw "Missing patch file: $f" }
  Copy-Item -LiteralPath $source -Destination $destination -Force
  Write-Host "Applied: $f"
}
Copy-Item -LiteralPath (Join-Path $unpack 'PHASE9_6A_TO_9_8_RELEASE_README.md') -Destination (Join-Path $repo 'PHASE9_6A_TO_9_8_RELEASE_README.md') -Force
```

If 9.6A was **already** applied separately, this patch overwrites the same 9.6A files with the bundled version; review `git diff` first if you have made local changes.

## Local release gates

```powershell
$sf = Join-Path $repo 'siteforge\backend'
$cc = Join-Path $repo 'zerro-project-command-center\backend'

docker run --rm --network none --entrypoint python --mount "type=bind,source=$sf,target=/app,readonly" -w /app zerror_functional_integration_stage5_source-siteforge_backend -m pytest -p no:cacheprovider 'tests/test_phase9_command_center_feed.py' 'tests/test_phase9_finance_adapter_contract.py' 'tests/test_phase9_gl_posting_gate.py' 'tests/test_phase9_handoff_integrity.py' 'tests/test_phase9_landed_cost_reconciliation.py' 'tests/test_phase9_return_cost_preview.py' 'tests/test_phase9_valuation_rollforward.py' 'tests/test_inventory_valuation_engine.py' 'tests/test_landed_cost_allocation.py' 'tests/test_gl_batch_reconciliation.py' 'tests/test_finance_movement_journal_proposals.py' -q
if ($LASTEXITCODE -ne 0) { throw 'Siteforge tests failed' }

docker run --rm --network none --entrypoint python --mount "type=bind,source=$cc,target=/app,readonly" -w /app zerror_functional_integration_stage5_source-command_backend -m pytest -p no:cacheprovider 'tests/test_phase9_finance_bridge.py' 'tests/test_stores_phase8_bridge.py' -q
if ($LASTEXITCODE -ne 0) { throw 'Command Center tests failed' }

Push-Location (Join-Path $repo 'zerro-project-command-center\frontend')
try {
  npm ci
  if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
  npm run build
  if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
} finally { Pop-Location }
```

## Do not push or deploy until release gates are reviewed

Integration smoke checklist (manual; requires your existing local stack and credentials):

1. Confirm an authorized user reaches the Command Center `GET /api/projects/{project_id}/phase9-finance-monitor` with the correct project map and service key. Verify an unauthorized project returns 403.
2. Verify the source endpoint only accepts valid `X-ZerroR-Service-Key` and uses the authoritative organization/project mapping.
3. Verify proposal details and sample counts reconcile; response headers `Cache-Control: no-store`; no amounts described as posted GL or certified valuation.
4. Test missing source, network failure, corrupt payload, expired snapshot, project-switch and role-switch — UI should clear old data and show an error, not stale numbers.
5. Check no migrations added and existing `siteforge` live tables/data and Docker volumes are unchanged.
6. Confirm the Command Center frontend is actually deployed by its intended service/domain; the root unified compose does not currently build that frontend.
7. Do not mark GL integration complete without a real authoritative Finance writer and independently verified posting readback.

When verification passes, make ONE commit/push:

```powershell
cd "$env:USERPROFILE\Desktop\zerrobuild-store"
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Whitespace validation failed' }
git status --short
git add -- $files 'PHASE9_6A_TO_9_8_RELEASE_README.md'
git commit -m 'Phase 9 consolidated Command Center monitor and release checks'
git push origin feature/stores-finance-phase9
```

**Deployment safety:** Do not execute `docker compose down -v`, prune volumes, run migrations against a live DB without a backup, or blindly overwrite the second compose file outside the canonical repo. An actual controlled 9.8 Docker rollout must be planned after tests, map/service auth smoke tests, and UI serving configuration have been checked.
