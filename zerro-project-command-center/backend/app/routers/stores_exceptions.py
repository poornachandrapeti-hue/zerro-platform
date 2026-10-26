"""Read-only Stores monitoring, scoped to live ZerroBuild viewer grants.

No browser service key, stock posting, billing or QA certification is possible here.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user
from ..authoritative_projects import fetch_project_master
from ..config import get_settings
from ..database import get_db
from ..models import Project
from ..project_identity import load_project_mapping, to_siteforge_code

router = APIRouter(prefix="/api/projects", tags=["Stores monitoring"])


def source_identity(project: Project, user: CurrentUser, settings, master: dict) -> tuple[int, int]:
    """Resolve canonical source IDs only from authenticated source project master."""
    if user.project_code != project.code or not user.discipline_codes:
        raise HTTPException(403, "Current project scope required")
    try:
        mapping = load_project_mapping(settings.command_center_project_map)
    except (ValueError, TypeError):
        raise HTTPException(503, "Project mapping unavailable")
    code = to_siteforge_code(project.code, mapping).upper()
    authority = master.get(code)
    if not isinstance(authority, dict):
        raise HTTPException(404, "Authorized source project not found")
    project_id = authority.get("id")
    try:
        org_id = int(settings.command_center_expected_org)
    except (ValueError, TypeError):
        raise HTTPException(503, "Source organization mapping unavailable")
    if type(project_id) is not int or project_id <= 0 or org_id <= 0:
        raise HTTPException(503, "Invalid authoritative project identity")
    return org_id, project_id


def validate_snapshot(payload: dict, org_id: int, project_id: int) -> dict:
    """Validate untrusted upstream data before forwarding to the browser."""
    from datetime import datetime, timezone
    if not isinstance(payload, dict) or payload.get('source') != 'zerrobuild.stores.phase8_cross_module_audit' or payload.get('schema_version') != 1:
        raise ValueError('Invalid snapshot schema')
    if (type(payload.get('organization_id')) is not int or payload['organization_id'] != org_id
            or type(payload.get('project_id')) is not int or payload['project_id'] != project_id):
        raise ValueError('Scope mismatch')
    if (payload.get('read_only') is not True or payload.get('complete_history') is not False
            or payload.get('billing_certified') is not False
            or payload.get('financials_authority_verified') is not False
            or payload.get('external_inspection_verified') is not False
            or payload.get('delivery_mode') != 'poll_snapshot'):
        raise ValueError('Unverified source authority')
    ts = datetime.fromisoformat(payload['as_of'].replace('Z', '+00:00'))
    if ts.tzinfo is None or not -60 <= (datetime.now(timezone.utc) - ts).total_seconds() <= 300:
        raise ValueError('Stale timestamp')
    count, counts, records = payload['record_count'], payload['exception_counts'], payload['exception_records']
    if (type(count) is not int or not 0 <= count <= 500 or not isinstance(counts, dict)
            or not isinstance(records, list) or len(records) > count):
        raise ValueError('Invalid counts')
    if any(not isinstance(k, str) or not k or type(v) is not int or not 0 <= v <= count for k,v in counts.items()):
        raise ValueError('Invalid categories')
    for row in records:
        if not isinstance(row, dict) or set(row) != {'material_request_id','work_package_id','exception_codes','review_state'}:
            raise ValueError('Invalid exception record')
        if type(row['material_request_id']) is not int or row['material_request_id'] <= 0:
            raise ValueError('Invalid request reference')
        wp = row['work_package_id']
        if wp is not None and (type(wp) is not int or wp <= 0):
            raise ValueError('Invalid work package')
        codes = row['exception_codes']
        if not isinstance(codes, list) or not codes or len(codes) != len(set(codes)) or not all(isinstance(c,str) and c in counts for c in codes):
            raise ValueError('Invalid exception codes')
        if not isinstance(row['review_state'], str):
            raise ValueError('Invalid review status')
    if any(sum(code in row['exception_codes'] for row in records) != num for code,num in counts.items()):
        raise ValueError('Snapshot totals mismatch')
    return {'source':payload['source'],'organization_id':org_id,'project_id':project_id,
            'as_of':ts.isoformat(),'stale':False,'record_count':count,
            'coverage':str(payload.get('coverage',''))[:300],
            'exception_counts':counts,'exception_records':records,
            'complete_history':False,'external_inspection_verified':False,
            'financials_authority_verified':False,'billing_certified':False}


@router.get('/{project_id}/stores-phase8-exceptions')
def stores_phase8_exceptions(project_id: int, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = get_settings()
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, 'Project not found')
    if user.project_code != project.code:
        raise HTTPException(403, 'Project not authorized')
    # Current session grants were refreshed by get_current_user; source ID resolved live.
    master = fetch_project_master(settings.command_center_expected_org, settings)
    org_id, source_pid = source_identity(project, user, settings, master)
    base = settings.command_center_identity_url.rstrip('/')
    key = settings.command_center_identity_service_key
    if not base or not key:
        raise HTTPException(503, 'Stores source not configured')
    try:
        with httpx.Client(timeout=8.0, follow_redirects=False, trust_env=False) as client:
            result = client.get(
                f'{base}/api/projects/{source_pid}/stores/internal-command-center/phase8-exception-snapshot',
                params={'limit':200},
                headers={'X-ZerroR-Service-Key':key, 'Accept':'application/json'},
            )
            result.raise_for_status()
            if len(result.content) > 512 * 1024:
                raise ValueError('Oversized snapshot')
            payload = validate_snapshot(result.json(), org_id, source_pid)
    except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise HTTPException(503, 'Stores exception monitoring unavailable')
    # The browser-facing project ID is the authorized Command Center ID.
    payload['project_id'] = project_id
    from fastapi.responses import JSONResponse
    return JSONResponse(payload, headers={'Cache-Control':'no-store'})
