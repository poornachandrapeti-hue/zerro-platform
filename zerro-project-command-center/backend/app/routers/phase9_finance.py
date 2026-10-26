"""Project-authorized read-only Finance proposal dashboard bridge."""
from __future__ import annotations
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from ..auth import CurrentUser, get_current_user
from ..authoritative_projects import fetch_project_master
from ..config import get_settings
from ..database import get_db
from ..models import Project
from .stores_exceptions import source_identity

router = APIRouter(prefix='/api/projects', tags=['Finance monitoring'])


def validate_finance_snapshot(data: dict, org_id: int, pid: int, *, now=None) -> dict:
    if not isinstance(data, dict) or data.get('source') != 'zerrobuild.financials.phase9_proposal_monitor' or data.get('schema_version') != 1:
        raise ValueError('Unrecognized monitoring source')
    if type(data.get('organization_id')) is not int or data['organization_id'] != org_id or type(data.get('project_id')) is not int or data['project_id'] != pid:
        raise ValueError('Scope mismatch')
    if any(data.get(k) is not False for k in ('complete_history', 'gl_posted_verified', 'inventory_valuation_certified', 'billing_certified')):
        raise ValueError('Unsupported financial assurance')
    if data.get('read_only') is not True or data.get('delivery_mode') != 'poll_snapshot':
        raise ValueError('Unsupported snapshot type')
    stamp = datetime.fromisoformat(data['as_of'].replace('Z', '+00:00'))
    if stamp.tzinfo is None or not -60 <= ((now or datetime.now(timezone.utc)) - stamp).total_seconds() <= 300:
        raise ValueError('Stale or invalid timestamp')
    count, counts, records = data['record_count'], data['status_counts'], data['proposal_records']
    if type(count) is not int or not 0 <= count <= 200 or not isinstance(counts, dict) or not isinstance(records, list) or len(records) != count:
        raise ValueError('Invalid sample count')
    valid = {'Draft', 'Pending Review', 'Approved', 'Rejected'}
    if any(k not in valid or type(v) is not int or not 0 <= v <= count for k, v in counts.items()):
        raise ValueError('Invalid status counts')
    seen = set()
    for row in records:
        if not isinstance(row, dict) or set(row) != {'proposal_id', 'source_movement_line_id', 'status', 'proposal_revision'}:
            raise ValueError('Invalid record')
        if any(type(row[k]) is not int or row[k] <= 0 for k in ('proposal_id', 'source_movement_line_id', 'proposal_revision')) or row['status'] not in valid:
            raise ValueError('Invalid record references')
        if row['proposal_id'] in seen:
            raise ValueError('Duplicate proposal')
        seen.add(row['proposal_id'])
    if dict(__import__('collections').Counter(row['status'] for row in records)) != counts:
        raise ValueError('Non-reconciled sample')
    return {'source': data['source'], 'organization_id': org_id, 'project_id': pid,
            'as_of': stamp.isoformat(), 'read_only': True, 'complete_history': False,
            'gl_posted_verified': False, 'inventory_valuation_certified': False, 'billing_certified': False,
            'coverage': 'Latest 200 proposals; not a project-wide accounting balance',
            'record_count': count, 'status_counts': counts, 'proposal_records': records}


@router.get('/{project_id}/phase9-finance-monitor')
def finance_monitor(project_id: int, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, 'Project not found')
    if user.project_code != project.code:
        raise HTTPException(403, 'Project not authorized')
    settings = get_settings()
    master = fetch_project_master(settings.command_center_expected_org, settings)
    org_id, source_pid = source_identity(project, user, settings, master)
    base = settings.command_center_identity_url.rstrip('/')
    key = settings.command_center_identity_service_key
    if not base or not key:
        raise HTTPException(503, 'Finance source not configured')
    try:
        with httpx.Client(timeout=8.0, follow_redirects=False, trust_env=False) as client:
            response = client.get(
                f'{base}/api/projects/{source_pid}/financials/internal-command-center/phase9-finance-proposals',
                headers={'X-ZerroR-Service-Key': key, 'Accept': 'application/json'})
            response.raise_for_status()
            if len(response.content) > 512 * 1024:
                raise ValueError('Oversized response')
            payload = validate_finance_snapshot(response.json(), org_id, source_pid)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, OverflowError, AttributeError):
        raise HTTPException(503, 'Finance proposal monitoring unavailable')
    payload['project_id'] = project_id
    return JSONResponse(payload, headers={'Cache-Control': 'no-store'})
