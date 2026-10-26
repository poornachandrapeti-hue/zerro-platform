"""Drop-in FastAPI router for the *separate* Zerro Command Center backend.

Integration MUST inject resolve_viewer_scope using its authenticated request/session
and LIVE project grant lookup. Never pass a service key from frontend or accept
org / authorization flags from request arguments. No inventory writes occur here.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

try:
    from .stores_approval_feed import StoresFeedError, fetch_stores_workload
except ImportError:  # copy both files into a flat command-backend integration package
    from stores_approval_feed import StoresFeedError, fetch_stores_workload


# Should raise HTTPException(401 / 403 / 404) on invalid auth, missing grant or mapping.
# Must return canonical ZerroBuild org id, not an unvalidated browser-supplied number.
ResolveViewerScope = Callable[[Request, int], int]


def create_stores_workload_router(*, resolve_viewer_scope: ResolveViewerScope,
                                  zerrobuild_base_url: str,
                                  service_key: str,
                                  max_age_seconds: int = 300,
                                  fetcher: Callable = fetch_stores_workload) -> APIRouter:
    if not callable(resolve_viewer_scope):
        raise ValueError('Live viewer authorization callback is required')
    if not service_key or not zerrobuild_base_url.startswith('https://'):
        raise ValueError('HTTPS ZerroBuild URL and internal service credential required')
    if max_age_seconds <= 0:
        raise ValueError('Positive freshness threshold required')

    router = APIRouter(tags=['Command Center - Stores'])

    @router.get('/api/projects/{project_id}/stores-approval-workload')
    def stores_approval_workload(project_id: int, request: Request):
        if project_id <= 0:
            raise HTTPException(status_code=404, detail='Project not found')
        # Required live auth check. Do not catch the callback's 401/403/404 errors.
        org_id = resolve_viewer_scope(request, project_id)
        if type(org_id) is not int or org_id <= 0:
            raise HTTPException(status_code=403, detail='Project access denied')
        try:
            result = fetcher(base_url=zerrobuild_base_url, service_key=service_key,
                             organization_id=org_id, project_id=project_id,
                             viewer_authorized=True, max_age_seconds=max_age_seconds)
        except StoresFeedError:
            # Do not disclose upstream URL, service key or cross-project feed contents.
            return JSONResponse(status_code=503, content={'detail': 'Stores workload unavailable or stale'}, headers={'Cache-Control': 'private, no-store'})
        if result.stale:
            return JSONResponse(status_code=503, content={'detail': 'Stores workload unavailable or stale'}, headers={'Cache-Control': 'private, no-store'})
        payload = asdict(result)
        payload.pop('age_seconds', None)
        return JSONResponse(content=payload, headers={'Cache-Control': 'private, no-store'})

    return router
