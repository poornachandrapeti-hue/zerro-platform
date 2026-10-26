"""Phase 5: read-only, source-linked Construction progress evidence for Stores issues.

Progress quantities are construction activity measurements, not material consumption.
No inferred material consumption, installation, earnings, or inventory mutation.
"""
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.construction.models import ConstructionActivity, ProgressLine, ProgressReport
from .material_handovers import _scope
from .return_work_package_trace import construction_return_trace

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Construction Evidence'])


def match_approved_progress_evidence(trace_records, lines, reports, activities):
    """Match only approved source progress linked to the exact issue posting and WP.

    Never sum progress-line quantity as material consumed: different units and
    activities make such an inference invalid. Preserve ambiguous evidence.
    """
    report_map = {r.id: r for r in reports}
    activity_map = {a.id: a for a in activities}
    indexed = defaultdict(list)
    for line in lines:
        report = report_map.get(line.report_id)
        activity = activity_map.get(line.activity_id)
        if not report or not activity or report.status != 'Approved':
            continue
        if line.stock_posting_id is None:
            continue
        indexed[(line.stock_posting_id, activity.package_id)].append({
            'progress_report_id': report.id,
            'progress_line_id': line.id,
            'construction_activity_id': activity.id,
            'report_status': report.status,
            'activity_quantity': str(line.quantity) if line.quantity is not None else None,
            'activity_unit': line.unit,
            'material_quantity_verified': False,
        })
    output = []
    for record in trace_records:
        copy = dict(record)
        matches = indexed.get((record['issue_posting_id'], record['work_package_id']), [])
        copy['approved_construction_evidence'] = matches
        copy['approved_construction_evidence_count'] = len(matches)
        copy['construction_evidence_state'] = 'Approved Progress Linked' if matches else 'No Approved Linked Progress'
        copy['construction_consumption_verified'] = False
        copy['installation_verified'] = False
        output.append(copy)
    return output


@router.get('/phase5/construction-consumption-evidence')
def construction_consumption_evidence(pid: int, work_package_id: int | None = None,
    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Read-only evidence, never a physical consumption or installation certificate."""
    _scope(db, u, pid, 'stores.requests.view')
    if work_package_id is not None and work_package_id <= 0:
        raise HTTPException(422, 'work_package_id must be positive')
    traced = construction_return_trace(pid, work_package_id=work_package_id, u=u, db=db)
    records = traced['records']
    if not records:
        return {'records': [], 'coverage': traced['coverage'], 'construction_consumption_verified': False,
                'inventory_verified': False}
    posting_ids = {r['issue_posting_id'] for r in records}
    package_ids = {r['work_package_id'] for r in records}
    activities = db.execute(select(ConstructionActivity).where(
        ConstructionActivity.organization_id == u.organization_id,
        ConstructionActivity.project_id == pid,
        ConstructionActivity.package_id.in_(package_ids))).scalars().all()
    activity_ids = {a.id for a in activities}
    lines = db.execute(select(ProgressLine).where(
        ProgressLine.stock_posting_id.in_(posting_ids),
        ProgressLine.activity_id.in_(activity_ids))).scalars().all() if activity_ids else []
    reports = db.execute(select(ProgressReport).where(
        ProgressReport.id.in_({line.report_id for line in lines}),
        ProgressReport.organization_id == u.organization_id,
        ProgressReport.project_id == pid,
        ProgressReport.status == 'Approved')).scalars().all() if lines else []
    return {'records': match_approved_progress_evidence(records, lines, reports, activities),
        'coverage': traced['coverage'] + '; approved construction progress explicitly linked by issue posting and work package',
        'construction_consumption_verified': False, 'inventory_verified': False,
        'note': 'Approved construction progress is supporting evidence only. Its activity quantity is NOT an established material consumed or installed quantity.'}
