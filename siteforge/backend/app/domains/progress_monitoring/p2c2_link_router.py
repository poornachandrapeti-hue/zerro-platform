"""P2C2B: audited Construction/QA evidence binding decisions.

No progress rollup or billing write. Requires P2C2A migration at deployment.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.models import User, Membership, Role
from app.domains.construction.models import ProgressReport, ProgressLine, ConstructionActivity
from app.domains.quality.models import ConstructionRequest
from .router import progress_scope
from .p2c_source_readback import allowed
from .p2c2_link_models import ProgressEvidenceLink as Link, ProgressEvidenceLinkEvent as Event

router = APIRouter(prefix="/api/projects/{pid}/progress/evidence-links", tags=["Progress Evidence Links"])


class Proposal(BaseModel):
    report_id: int = Field(gt=0)
    progress_line_id: int = Field(gt=0)
    inspection_request_id: int = Field(gt=0)
    accepted_quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    binding_evidence_ref: str = Field(min_length=1, max_length=240)


class Decision(BaseModel):
    version: int = Field(gt=0)
    note: str = Field(min_length=3, max_length=2000)


def _rights(db, user, pid, permission):
    # Explicit per-project grants only. An organization administrator has full scope,
    # but still cannot review a proposal they authored.
    if not user.active:
        raise HTTPException(403, 'Inactive user')
    progress_scope(db, user, pid)  # project/internal visibility precondition
    if user.organization_admin:
        return {'all': True, 'pairs': []}
    memberships = db.query(Membership).filter_by(project_id=pid, user_id=user.id, active=True).all()
    eligible = []
    for m in memberships:
        role = db.get(Role, m.role_id)
        perms = set(role.permissions or []) if role else set()
        if permission in perms and 'planning.partner.view' not in perms:
            eligible.append(m)
    if not eligible:
        raise HTTPException(403, f'Missing project permission: {permission}')
    if any(m.scope == 'ALL' for m in eligible):
        return {'all': True, 'pairs': []}
    return {'all': False, 'pairs': [
        (m.company_id, {int(d) for d in (m.discipline_ids or [])}) for m in eligible
    ]}


def _source(db, user, pid, scope, report_id, line_id, inspection_id):
    report = db.query(ProgressReport).filter_by(id=report_id, organization_id=user.organization_id, project_id=pid).first()
    line = db.get(ProgressLine, line_id)
    inspection = db.query(ConstructionRequest).filter_by(id=inspection_id, organization_id=user.organization_id, project_id=pid).first()
    if not report or not line or not inspection or line.report_id != report.id:
        raise HTTPException(404, 'Construction/QA source not found')
    activity = db.query(ConstructionActivity).filter_by(id=line.activity_id, organization_id=user.organization_id, project_id=pid).first()
    if not activity or inspection.activity_id != activity.id or activity.company_id != report.company_id or activity.discipline_id != report.discipline_id or inspection.company_id != report.company_id or inspection.package_id != activity.package_id:
        raise HTTPException(409, 'Source scope, activity or package mismatch')
    if not allowed(report.company_id, report.discipline_id, scope):
        raise HTTPException(404, 'Construction/QA source not found')
    if report.status != 'Approved' or inspection.status != 'Approved' or inspection.outcome not in ('Accepted', 'Partially Accepted'):
        raise HTTPException(409, 'Construction and QA approvals required')
    if line.rework or line.reverses_line_id is not None:
        raise HTTPException(409, 'Rework or reversal requires reconciliation')
    try:
        capacity = Decimal(str(line.quantity))
        qa_capacity = Decimal(str(inspection.accepted_quantity))
        if not all(x.is_finite() and x > 0 for x in (capacity, qa_capacity)):
            raise ValueError()
    except (InvalidOperation, ValueError, TypeError):
        raise HTTPException(409, 'Invalid source quantities')
    return capacity, qa_capacity


def _event(db, link, action, actor, note=''):
    db.add(Event(link_id=link.id, organization_id=link.organization_id, project_id=link.project_id, action=action, actor_id=actor, note=note))


def _view(link):
    return {'id': link.id, 'organization_id': link.organization_id, 'project_id': link.project_id,
            'report_id': link.report_id, 'progress_line_id': link.progress_line_id,
            'inspection_request_id': link.inspection_request_id, 'accepted_quantity': str(link.accepted_quantity),
            'status': link.status, 'version': link.version, 'created_by': link.created_by,
            'reviewed_by': link.reviewed_by, 'earned_progress': False, 'billing_certified': False}


@router.post('')
def propose(pid: int, body: Proposal, user: User = Depends(authenticated), db: Session = Depends(get_db)):
    scope = _rights(db, user, pid, 'progress.evidence.propose')
    capacity, qa_capacity = _source(db, user, pid, scope, body.report_id, body.progress_line_id, body.inspection_request_id)
    if body.accepted_quantity > min(capacity, qa_capacity):
        raise HTTPException(409, 'Proposed quantity exceeds source capacity')
    if not body.binding_evidence_ref.strip():
        raise HTTPException(422, 'Binding evidence reference required')
    link = Link(organization_id=user.organization_id, project_id=pid, report_id=body.report_id,
                progress_line_id=body.progress_line_id, inspection_request_id=body.inspection_request_id,
                accepted_quantity=body.accepted_quantity, binding_evidence_ref=body.binding_evidence_ref.strip(),
                status='Proposed', created_by=user.id, version=1)
    try:
        db.add(link)
        db.flush()
        _event(db, link, 'Proposed', user.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Duplicate evidence link or invalid source reference')
    return _view(link)


@router.post('/{link_id}/decisions/{action}')
def decide(pid: int, link_id: int, action: str, body: Decision, user: User = Depends(authenticated), db: Session = Depends(get_db)):
    if action not in ('approve', 'reject', 'revoke'):
        raise HTTPException(404, 'Unsupported decision')
    permission = 'progress.evidence.revoke' if action == 'revoke' else 'progress.evidence.review'
    scope = _rights(db, user, pid, permission)
    link = db.query(Link).filter_by(id=link_id, organization_id=user.organization_id, project_id=pid).with_for_update().first()
    if link is None:
        raise HTTPException(404, 'Evidence link not found')
    report = db.query(ProgressReport).filter_by(id=link.report_id, organization_id=user.organization_id, project_id=pid).first()
    if not report or not allowed(report.company_id, report.discipline_id, scope):
        raise HTTPException(404, 'Evidence link not found')
    if link.created_by == user.id:
        raise HTTPException(403, 'Independent reviewer required')
    if link.version != body.version:
        raise HTTPException(409, 'Evidence link was modified; refresh and retry')
    if (action in ('approve', 'reject') and link.status != 'Proposed') or (action == 'revoke' and link.status != 'Approved'):
        raise HTTPException(409, 'Invalid state transition')
    if action == 'approve':
        capacity, qa_capacity = _source(db, user, pid, scope, link.report_id, link.progress_line_id, link.inspection_request_id)
        if link.accepted_quantity > min(capacity, qa_capacity):
            raise HTTPException(409, 'Source quantity changed since proposal')
        # Serialize approvals for the same project to avoid concurrent over-allocation.
        # The advisory lock is transaction-scoped and only serializes P2C2B writers.
        db.execute(text('SELECT pg_advisory_xact_lock(:ns, :project)'),
                   {'ns': 931142, 'project': pid})
        # A QA request can be split across lines, and a construction line across
        # inspections; independently cap both cumulative Approved allocations.
        others = db.query(Link).filter(Link.organization_id == user.organization_id,
              Link.project_id == pid, Link.status == 'Approved', Link.id != link.id).with_for_update().all()
        line_total = sum((Decimal(str(x.accepted_quantity)) for x in others if x.progress_line_id == link.progress_line_id), Decimal(0))
        inspection_total = sum((Decimal(str(x.accepted_quantity)) for x in others if x.inspection_request_id == link.inspection_request_id), Decimal(0))
        if line_total + link.accepted_quantity > capacity or inspection_total + link.accepted_quantity > qa_capacity:
            raise HTTPException(409, 'Previously approved links exhaust source quantity')
    elif action == 'revoke':
        # Revocation must stay possible after source rejection/cancellation.
        report = db.query(ProgressReport).filter_by(id=link.report_id, organization_id=user.organization_id, project_id=pid).first()
        if not report or not allowed(report.company_id, report.discipline_id, scope):
            raise HTTPException(404, 'Evidence link not found')
    status = {'approve': 'Approved', 'reject': 'Rejected', 'revoke': 'Revoked'}[action]
    link.status = status
    link.reviewed_by = user.id
    link.reviewed_at = datetime.now(timezone.utc)
    link.review_note = body.note.strip()
    link.version += 1
    _event(db, link, status, user.id, link.review_note)
    db.commit()
    return _view(link)


@router.get('/{link_id}')
def read_link(pid: int, link_id: int, user: User = Depends(authenticated), db: Session = Depends(get_db)):
    scope = _rights(db, user, pid, 'progress.evidence.view')
    link = db.query(Link).filter_by(id=link_id, organization_id=user.organization_id, project_id=pid).first()
    if not link:
        raise HTTPException(404, 'Evidence link not found')
    # Readback still checks the source-level company/discipline boundary.
    report = db.query(ProgressReport).filter_by(id=link.report_id, organization_id=user.organization_id, project_id=pid).first()
    if not report or not allowed(report.company_id, report.discipline_id, scope):
        raise HTTPException(404, 'Evidence link not found')
    return _view(link)
