# Stores Phase 4 — Command Center backend route handoff

## Delivered
- `integrations/command_center/stores_workload_router.py`: FastAPI router factory for deployment into the **separate** Command Center backend. Requires an injected **live authenticated viewer + project grant** resolver returning the canonical ZerroBuild organization ID.
- Reuses existing HTTPS-only server-to-server `stores_approval_feed.py` and internal secret; browser never receives service credentials.
- Rejects unauthorized viewers before fetching, rejects stale or invalid feeds, returns no-store responses and neutral unavailable errors.
- Existing embedded Command Center UI continues calling `GET /command-api/api/projects/{project_id}/stores-approval-workload`.
- Tests: `python -m pytest -q integrations/tests/test_stores_workload_router.py integrations/tests/test_stores_approval_feed.py`.

## Deployment integration (inside separate Command Center backend only)
```python
from integrations.command_center.stores_workload_router import create_stores_workload_router

# Must be implemented using Command Center's established auth and LIVE project-grant tables.
def resolve_viewer_scope(request, project_id: int) -> int:
    # Return the canonical ZerroBuild organization ID after verifying identity,
    # current project grant, project mapping and tenant membership.
    # Raise HTTPException(401/403/404) on failure. NEVER trust query fields.
    raise NotImplementedError('Wire to deployed identity/project services')

app.include_router(create_stores_workload_router(
    resolve_viewer_scope=resolve_viewer_scope,
    zerrobuild_base_url=settings.ZERROBUILD_API_URL,
    service_key=settings.COMMAND_CENTER_IDENTITY_SERVICE_KEY,
))
```
The route is **not auto-mounted** because this archive does not contain the separate Command Center backend. Deploy the two adapter files into that backend and implement the real `resolve_viewer_scope` callback; no placeholder auth should be deployed. Check that the `/command-api` reverse proxy strips the prefix as expected. Test with an allowed viewer, denied viewer, wrong tenant, source outage and stale result.

## Outstanding blockers
- Command Center's actual backend integration and live project-entitlement mapping.
- Runtime integration with PostgreSQL, Docker and actual source endpoint.
- Frontend TypeScript build and end-to-end verification.
- QA-cleared stock availability and operational issuing remain gated.
