"""Bounded, service-authenticated Finance proposal visibility for Command Center.

A proposal is neither inventory valuation evidence nor an accounting journal posting.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hmac
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.domains.identity_projects.models import Project
from .models import FinanceMovementJournalProposal

router = APIRouter(prefix='/api/projects/{pid}/financials/internal-command-center', tags=['Financials'])


def build_finance_proposal_snapshot(*, organization_id: int, project_id: int, rows: list,
                                    as_of: datetime | None = None) -> dict:
    """Report a bounded sample, never whole-project financial totals."""
    if type(organization_id) is not int or organization_id <= 0 or type(project_id) is not int or project_id <= 0:
        raise ValueError('Invalid project scope')
    if len(rows) > 200:
        raise ValueError('Unbounded proposal snapshot')
    counts = Counter()
    records = []
    for row in rows:
        if row.organization_id != organization_id or row.project_id != project_id:
            raise ValueError('Cross-project proposal')
        if type(row.id) is not int or row.id <= 0 or type(row.source_movement_line_id) is not int or row.source_movement_line_id <= 0:
            raise ValueError('Invalid proposal reference')
        if row.status not in {'Draft', 'Pending Review', 'Approved', 'Rejected'}:
            raise ValueError('Unexpected proposal state')
        if row.status == 'Approved' and (row.approved_by is None or row.approved_at is None):
            raise ValueError('Invalid approval evidence')
        counts[row.status] += 1
        records.append({'proposal_id': row.id, 'source_movement_line_id': row.source_movement_line_id,
                        'status': row.status, 'proposal_revision': row.proposal_revision})
    timestamp = as_of or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError('Timestamp must be timezone-aware')
    return {'source': 'zerrobuild.financials.phase9_proposal_monitor', 'schema_version': 1,
            'organization_id': organization_id, 'project_id': project_id, 'as_of': timestamp.isoformat(),
            'read_only': True, 'delivery_mode': 'poll_snapshot', 'complete_history': False,
            'coverage': 'Latest 200 proposal rows; sampled counts, not project-wide totals',
            'record_count': len(records), 'status_counts': dict(counts), 'proposal_records': records,
            'gl_posted_verified': False, 'inventory_valuation_certified': False,
            'billing_certified': False}


@router.get('/phase9-finance-proposals')
def finance_proposals_for_command_center(pid: int, request: Request, db: Session = Depends(get_db)):
    expected = settings.command_center_identity_service_key
    supplied = request.headers.get('X-ZerroR-Service-Key', '')
    if not expected or not hmac.compare_digest(expected, supplied):
        raise HTTPException(403, 'Command Center service authentication required')
    project = db.get(Project, pid)
    if project is None:
        raise HTTPException(404, 'Project not found')
    rows = (db.query(FinanceMovementJournalProposal)
            .filter_by(project_id=pid, organization_id=project.organization_id)
            .order_by(FinanceMovementJournalProposal.id.desc()).limit(200).all())
    return build_finance_proposal_snapshot(organization_id=project.organization_id, project_id=pid, rows=rows)
