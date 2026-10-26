"""P3B read-only, scoped canonical source projection for a Construction line.

Do not infer independent quantity verification, approved Planning baseline, earned
progress or billing from supervisor approval, QA quantity or a WBS code match.
"""
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.domains.construction.models import ConstructionActivity, ProgressReport, ProgressLine
from app.domains.quality.models import ConstructionRequest
from .p2c2_link_models import ProgressEvidenceLink
from .p2c_source_readback import allowed
from .router import progress_scope


def _dec(value):
    return Decimal(str(value))


def read_line_evidence(db: Session, user, project_id: int, line_id: int):
    """Read one line and its active approved QA allocations with a scoped identity.

    Return source provenance only. Caller supplies independent verified quantity
    and approved Planning baseline when the separate P3A calculator is integrated.
    """
    scope = progress_scope(db, user, project_id)
    line = db.get(ProgressLine, line_id)
    if line is None:
        raise HTTPException(404, 'Construction progress line not found')
    report = db.query(ProgressReport).filter_by(
        id=line.report_id, organization_id=user.organization_id, project_id=project_id).first()
    if report is None or not allowed(report.company_id, report.discipline_id, scope):
        raise HTTPException(404, 'Construction progress line not found')
    activity = db.query(ConstructionActivity).filter_by(
        id=line.activity_id, organization_id=user.organization_id, project_id=project_id).first()
    if activity is None or activity.company_id != report.company_id or activity.discipline_id != report.discipline_id:
        raise HTTPException(409, 'Construction activity scope mismatch')
    if line.unit != activity.unit:
        raise HTTPException(409, 'Construction measurement unit mismatch')
    links = db.query(ProgressEvidenceLink).filter_by(
        organization_id=user.organization_id, project_id=project_id,
        report_id=report.id, progress_line_id=line.id, status='Approved').all()
    seen = set()
    allocations = []
    accepted = Decimal('0')
    for link in links:
        if link.inspection_request_id in seen:
            raise HTTPException(409, 'Duplicate approved QA inspection allocation')
        seen.add(link.inspection_request_id)
        if link.created_by == link.reviewed_by or not link.reviewed_by:
            raise HTTPException(409, 'QA link lacks independent review')
        qa = db.query(ConstructionRequest).filter_by(
            id=link.inspection_request_id, organization_id=user.organization_id, project_id=project_id).first()
        if qa is None or qa.activity_id != line.activity_id or qa.company_id != activity.company_id:
            raise HTTPException(409, 'QA source missing or scope changed')
        if qa.status != 'Approved' or qa.outcome not in ('Accepted', 'Partially Accepted'):
            raise HTTPException(409, 'QA source no longer accepted')
        qty = _dec(link.accepted_quantity)
        if qty <= 0 or qa.accepted_quantity is None or qty > _dec(qa.accepted_quantity):
            raise HTTPException(409, 'QA link exceeds currently accepted inspection quantity')
        accepted += qty
        allocations.append({
            'link_id': link.id, 'inspection_request_id': qa.id,
            'accepted_quantity': str(qty), 'link_version': link.version,
            'reviewer_user_id': link.reviewed_by,
        })
    if line.quantity is None or _dec(line.quantity) < 0:
        raise HTTPException(409, 'Construction line lacks a valid reported quantity')
    if accepted > _dec(line.quantity):
        raise HTTPException(409, 'QA allocations exceed reported Construction quantity')
    return {
        'organization_id': user.organization_id, 'project_id': project_id,
        'activity_id': activity.id, 'report_id': report.id,
        'construction_line_id': line.id, 'report_status': report.status,
        'unit': activity.unit, 'reported_quantity': str(_dec(line.quantity)),
        'qa_accepted_quantity': str(accepted), 'qa_allocations': allocations,
        'construction_verified_quantity': None,
        'approved_planning_quantity': None,
        'measurement': None, 'earned_percent': None,
        'billing_eligible_quantity': None,
        'status': 'SOURCE_READBACK_ONLY',
        'limitations': [
            'Approved Construction report is not independent quantity verification',
            'Construction activity baseline is not proof of approved Planning baseline',
            'No progress, billing or Finance write performed',
        ],
    }
