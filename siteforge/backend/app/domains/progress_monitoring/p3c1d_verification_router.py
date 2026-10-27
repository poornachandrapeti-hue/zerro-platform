"""P3C1D: scoped quantity-verification proposal, decision, audit and readback.

Requires P3C1C migration. No earned progress, publication, QA acceptance,
finance or billing writes. Uses P3C1 approved Planning baseline and P3B
Construction readback; client-submitted quantities are never source authority.
"""
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.models import User
from app.domains.construction.models import ProgressLine
from .p2c2_link_router import _rights
from .p2c_source_readback import allowed
from .p3b_source_projection import read_line_evidence
from .p3c1_baseline_authority import read_authoritative_baseline
from .p3c1c_verification_models import (
    ProgressQuantityVerification as Verification,
    ProgressQuantityVerificationEvent as VerificationEvent,
)

router = APIRouter(
    prefix='/api/projects/{pid}/progress/quantity-verifications',
    tags=['Progress Quantity Verification'],
)


class Proposal(BaseModel):
    progress_line_id: int = Field(gt=0)
    planning_activity_id: int = Field(gt=0)
    source_revision: str = Field(min_length=1, max_length=100)
    verification_reference: str = Field(min_length=1, max_length=240)
    verified_quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class Decision(BaseModel):
    version: int = Field(gt=0)
    note: str = Field(min_length=3, max_length=2000)


def _qty(value):
    try:
        result = Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        raise HTTPException(409, 'Source quantity invalid')
    if not result.is_finite() or result < 0:
        raise HTTPException(409, 'Source quantity invalid')
    return result


def _source(db, user, pid, scope, line_id, planning_activity_id):
    """Re-read both canonical source records, never trusting submitted IDs as proof."""
    construction = read_line_evidence(db, user, pid, line_id)
    line = db.get(ProgressLine, line_id)
    if line is None or line.rework or line.reverses_line_id is not None:
        raise HTTPException(409, 'Rework/reversal line cannot be independently verified')
    if construction['report_status'] != 'Approved':
        raise HTTPException(409, 'Construction report must be approved')
    # _rights checks project permission; do not let wider Progress scope override it.
    from app.domains.construction.models import ProgressReport
    report = db.query(ProgressReport).filter_by(
        id=construction['report_id'], organization_id=user.organization_id,
        project_id=pid,
    ).first()
    if report is None or not allowed(report.company_id, report.discipline_id, scope):
        raise HTTPException(404, 'Construction line not visible')
    baseline = read_authoritative_baseline(
        db, user, pid, planning_activity_id=planning_activity_id,
        construction_activity_id=construction['activity_id'],
        unit=construction['unit'],
    )
    if baseline.get('status') != 'APPROVED_QUANTITY_FOUND':
        raise HTTPException(409, 'Approved mapped Planning quantity unavailable')
    planned = _qty(baseline['approved_planning_quantity'])
    reported = _qty(construction['reported_quantity'])
    qa_accepted = _qty(construction['qa_accepted_quantity'])
    if planned <= 0 or reported > planned or qa_accepted > reported:
        raise HTTPException(409, 'Source quantities inconsistent with approved baseline')
    return construction, baseline, planned, reported, qa_accepted


def _event(db, record, action, actor, note=''):
    db.add(VerificationEvent(
        verification_id=record.id, organization_id=record.organization_id,
        project_id=record.project_id, action=action,
        actor_user_id=actor, note=note,
    ))


def _view(record):
    return {
        'id': record.id, 'project_id': record.project_id,
        'progress_line_id': record.progress_line_id,
        'baseline_revision_id': record.baseline_revision_id,
        'verified_quantity': str(record.verified_quantity), 'unit': record.unit,
        'status': record.status, 'version': record.version,
        'proposer_user_id': record.proposer_user_id,
        'reviewer_user_id': record.reviewer_user_id,
        'verification_reference': record.verification_reference,
        'published': False, 'earned_progress': False, 'billing_certified': False,
    }


def _visible(db, user, pid, record, scope):
    from app.domains.construction.models import ProgressReport
    report = db.query(ProgressReport).filter_by(
        id=record.report_id, organization_id=user.organization_id, project_id=pid,
    ).first()
    if report is None or not allowed(report.company_id, report.discipline_id, scope):
        raise HTTPException(404, 'Verification not found')


@router.post('')
def propose(pid: int, body: Proposal, user: User = Depends(authenticated), db: Session = Depends(get_db)):
    scope = _rights(db, user, pid, 'progress.quantity.propose')
    c, b, planned, reported, accepted = _source(
        db, user, pid, scope, body.progress_line_id, body.planning_activity_id,
    )
    qty = _qty(body.verified_quantity)
    if qty <= 0 or qty > min(planned, reported) or accepted > qty:
        raise HTTPException(409, 'Proposed verification quantity inconsistent with source')
    if not body.source_revision.strip() or not body.verification_reference.strip():
        raise HTTPException(422, 'Verification references must not be blank')
    record = Verification(
        organization_id=user.organization_id, project_id=pid,
        report_id=c['report_id'], progress_line_id=body.progress_line_id,
        activity_id=c['activity_id'], baseline_revision_id=b['baseline_revision_id'],
        source_revision=body.source_revision.strip(),
        verification_reference=body.verification_reference.strip(),
        unit=c['unit'], verified_quantity=qty, status='Proposed',
        proposer_user_id=user.id, version=1,
    )
    try:
        db.add(record)
        db.flush()
        _event(db, record, 'Proposed', user.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Duplicate verification revision or invalid source')
    return _view(record)


@router.post('/{verification_id}/decisions/{action}')
def decide(pid: int, verification_id: int, action: str, body: Decision,
           user: User = Depends(authenticated), db: Session = Depends(get_db)):
    if action not in ('approve', 'reject', 'revoke'):
        raise HTTPException(404, 'Unsupported decision')
    scope = _rights(db, user, pid, 'progress.quantity.revoke' if action == 'revoke' else 'progress.quantity.review')
    record = db.query(Verification).filter_by(
        id=verification_id, organization_id=user.organization_id, project_id=pid,
    ).with_for_update().first()
    if record is None:
        raise HTTPException(404, 'Verification not found')
    _visible(db, user, pid, record, scope)
    if record.proposer_user_id == user.id:
        raise HTTPException(403, 'Independent reviewer required')
    if record.version != body.version:
        raise HTTPException(409, 'Verification version changed; refresh and retry')
    if (action in ('approve', 'reject') and record.status != 'Proposed') or (action == 'revoke' and record.status != 'Approved'):
        raise HTTPException(409, 'Invalid verification state transition')
    if action == 'approve':
        # Serialize concurrent approvals for the same project before quantity checks.
        db.execute(text('SELECT pg_advisory_xact_lock(:namespace, :project)'),
                   {'namespace': 931143, 'project': pid})
        # Exact Planning mapping is NOT persisted in P3C1C. Resolve the uniquely
        # approved revision's activity mapping back to this line, fail closed.
        from app.domains.planning_reporting.models import PlanningBaseline
        baseline_row = db.query(PlanningBaseline).filter_by(
            id=record.baseline_revision_id, organization_id=user.organization_id,
            project_id=pid, status='approved',
        ).first()
        if baseline_row is None or not isinstance(baseline_row.document, dict):
            raise HTTPException(409, 'Planning baseline changed or unavailable')
        activities = baseline_row.document.get('activities', [])
        matches = [a for a in activities if isinstance(a, dict) and
                   str(a.get('construction_activity_id')) == str(record.activity_id) and
                   a.get('unit') == record.unit and a.get('planning_activity_id') is not None]
        if len(matches) != 1:
            raise HTTPException(409, 'Planning activity mapping is ambiguous')
        planning_activity_id = matches[0]['planning_activity_id']
        c, b, planned, reported, accepted = _source(
            db, user, pid, scope, record.progress_line_id, planning_activity_id,
        )
        if (record.report_id != c['report_id'] or record.activity_id != c['activity_id'] or
            record.baseline_revision_id != b['baseline_revision_id'] or record.unit != c['unit']):
            raise HTTPException(409, 'Source changed since verification proposal')
        qty = _qty(record.verified_quantity)
        if qty <= 0 or qty > min(planned, reported) or accepted > qty:
            raise HTTPException(409, 'Verification quantity no longer valid')
        # Unique source revision guards duplicates. Fail closed on any existing
        # Approved revision for this construction line to avoid double counting.
        competing = db.query(Verification.id).filter(
            Verification.organization_id == user.organization_id,
            Verification.project_id == pid,
            Verification.progress_line_id == record.progress_line_id,
            Verification.status == 'Approved',
            Verification.id != record.id,
        ).first()
        if competing:
            raise HTTPException(409, 'Another approved verification already exists for this line')
    new_status = {'approve': 'Approved', 'reject': 'Rejected', 'revoke': 'Revoked'}[action]
    record.status = new_status
    record.reviewer_user_id = user.id
    record.review_note = body.note.strip()
    if not record.review_note:
        raise HTTPException(422, 'Review note required')
    if action == 'approve':
        record.verified_at = datetime.now(timezone.utc)
    record.version += 1
    _event(db, record, new_status, user.id, record.review_note)
    db.commit()
    return _view(record)


@router.get('/{verification_id}')
def read_verification(pid: int, verification_id: int,
                      user: User = Depends(authenticated), db: Session = Depends(get_db)):
    scope = _rights(db, user, pid, 'progress.quantity.view')
    record = db.query(Verification).filter_by(
        id=verification_id, organization_id=user.organization_id, project_id=pid,
    ).first()
    if record is None:
        raise HTTPException(404, 'Verification not found')
    _visible(db, user, pid, record, scope)
    return _view(record)
