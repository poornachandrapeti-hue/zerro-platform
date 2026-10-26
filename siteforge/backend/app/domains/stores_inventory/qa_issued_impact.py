"""Read-only QA revocation exposure. Never implies that legacy outbound provenance is complete."""
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.router import audit
from app.domains.supply_chain.models import StockPosting, StockPostingLine
from .models import StoresInspectionCase, StoresReceiptLot, StoresOutboundLotAllocation
from .router import qa_access

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores & Inventory'])


def summarize_exposure(rows):
    """Only allocated, posted outbound movements are attributable to a receipt lot."""
    grouped = defaultdict(lambda: {'issued': Decimal('0'), 'returned': Decimal('0'), 'posting_ids': set(), 'work_package_ids': set()})
    for lot_id, kind, quantity, posting_id, package_id in rows:
        if kind not in ('Issue', 'Return'):
            continue
        group = grouped[lot_id]
        group['issued' if kind == 'Issue' else 'returned'] += Decimal(str(quantity))
        group['posting_ids'].add(posting_id)
        if package_id is not None:
            group['work_package_ids'].add(package_id)
    return {lot_id: {
        'attributed_issued': str(value['issued']),
        'attributed_returned': str(value['returned']),
        'posting_ids': sorted(value['posting_ids']),
        'work_package_ids': sorted(value['work_package_ids']),
    } for lot_id, value in grouped.items()}


@router.get('/inspection-cases/{case_id}/revocation-impact')
def revocation_impact(pid: int, case_id: int, u: User = Depends(authenticated),
                      db: Session = Depends(get_db)):
    """Conservative construction review queue, not proof of installed quantities."""
    qa_access(db, u, pid)
    case = db.query(StoresInspectionCase).filter_by(
        id=case_id, project_id=pid, organization_id=u.organization_id).first()
    if case is None:
        raise HTTPException(404, 'Inspection case not found')
    if case.status != 'Quality Revoked':
        raise HTTPException(409, 'Impact review applies only to revoked QA cases')
    lots = db.query(StoresReceiptLot).filter_by(
        goods_receipt_line_id=case.goods_receipt_line_id,
        project_id=pid, organization_id=u.organization_id).all()
    lot_ids = [lot.id for lot in lots]
    mapped = []
    if lot_ids:
        mapped = (db.query(StoresOutboundLotAllocation, StockPostingLine, StockPosting)
            .join(StockPostingLine, StockPostingLine.id == StoresOutboundLotAllocation.stock_posting_line_id)
            .join(StockPosting, StockPosting.id == StockPostingLine.posting_id)
            .filter(StoresOutboundLotAllocation.receipt_lot_id.in_(lot_ids),
                StoresOutboundLotAllocation.project_id == pid,
                StoresOutboundLotAllocation.organization_id == u.organization_id,
                StockPosting.project_id == pid,
                StockPosting.organization_id == u.organization_id,
                StockPosting.status == 'Posted',
                StockPosting.kind.in_(['Issue', 'Return'])).all())
    summary = summarize_exposure([
        (allocation.receipt_lot_id, posting.kind, allocation.quantity, posting.id, posting.package_id)
        for allocation, _line, posting in mapped])
    return {
        'project_id': pid, 'inspection_case_id': case.id,
        'goods_receipt_line_id': case.goods_receipt_line_id,
        'qa_status': case.status, 'qa_version': case.version,
        'requires_construction_impact_review': True,
        'lots': [{'receipt_lot_id': lot.id, 'lot_code': lot.lot_code,
                  **summary.get(lot.id, {'attributed_issued': '0', 'attributed_returned': '0',
                      'posting_ids': [], 'work_package_ids': []})} for lot in lots],
        'impact_scope_verified': False,
        'stock_available_to_issue': None,
        'warning': ('Listed work packages are supported by explicit posted outbound lot mappings only. '
            'Missing or legacy mappings mean additional affected construction work may exist. '
            'Do not treat absence of mapped issues as proof of no exposure; manual QA and construction review required.'),
    }


@router.post('/inspection-cases/{case_id}/construction-review-tasks')
def create_construction_review_tasks(pid: int, case_id: int,
                                     u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Assign review only to verified work packages; never auto-release, recall or post stock."""
    from app.domains.identity_projects.security import permitted
    from app.domains.construction.models import WorkPackage
    from app.domains.coordination.models import Task
    from app.domains.coordination.service import _task

    project = qa_access(db, u, pid, edit=True)
    permitted(db, u, project, 'construction.view')
    # Serialize concurrent callers across the same case, including duplicate-task checks.
    case = (db.query(StoresInspectionCase).filter_by(id=case_id, project_id=pid,
               organization_id=u.organization_id).with_for_update().first())
    if case is None:
        raise HTTPException(404, 'Inspection case not found')
    if case.status != 'Quality Revoked':
        raise HTTPException(409, 'Only revoked QA cases require construction review')
    exposure = revocation_impact(pid, case_id, u=u, db=db)
    package_ids = sorted({package_id for lot in exposure['lots']
                          for package_id in lot['work_package_ids']})
    created, existing, unassigned = [], [], []
    source_type = 'stores.qa_revocation.construction_review'
    for package_id in package_ids:
        package = db.query(WorkPackage).filter_by(id=package_id, project_id=pid,
                      organization_id=u.organization_id).first()
        if package is None:
            unassigned.append({'work_package_id': package_id, 'reason': 'Package unavailable'})
            continue
        title = f'QA revoked material: review work package {package.code}'
        prior = db.query(Task).filter_by(organization_id=u.organization_id, project_id=pid,
                source_type=source_type, source_id=case_id, title=title).first()
        if prior is not None:
            existing.append({'work_package_id': package_id, 'task_id': prior.id, 'status': prior.status})
            continue  # Even completed tasks are not reopened by repeated requests.
        owner_id = package.responsible_user_id
        owner = db.get(User, owner_id) if owner_id else None
        if owner is None or owner.organization_id != u.organization_id or not owner.active:
            unassigned.append({'work_package_id': package_id, 'reason': 'No active responsible owner'})
            continue
        # Do not delegate outside the project or to an unauthorized Construction viewer.
        from app.domains.identity_projects.security import holds
        if not holds(db, owner, project, 'construction.view', discipline_id=package.discipline_id):
            unassigned.append({'work_package_id': package_id, 'reason': 'Responsible owner lacks project scope'})
            continue
        task = _task(db, u, project, owner_id, title, source_type, case_id, priority='High')
        created.append({'work_package_id': package_id, 'task_id': task.id})
        audit(db, u, 'create_construction_impact_review', 'coordination_tasks', task.id,
              details={'inspection_case_id': case_id, 'work_package_id': package_id,
                       'assigned_owner_id': owner_id, 'impact_scope_verified': False}, project_id=pid)
    db.commit()
    return {'project_id': pid, 'inspection_case_id': case_id, 'created': created,
            'existing': existing, 'unassigned': unassigned,
            'impact_scope_verified': False,
            'manual_review_still_required': True,
            'note': 'Tasks cover only attributable outbound lot mappings; additional legacy exposure is possible.'}


from pydantic import BaseModel, Field


class ConstructionImpactReviewIn(BaseModel):
    task_version: int = Field(ge=1)
    evidence: str = Field(min_length=10, max_length=4000)


def _impact_task(db, user, pid, case_id, task_id):
    from app.domains.coordination.models import Task
    task = (db.query(Task).filter_by(
        id=task_id, organization_id=user.organization_id, project_id=pid,
        source_type='stores.qa_revocation.construction_review', source_id=case_id,
    ).with_for_update().first())
    if task is None:
        raise HTTPException(404, 'Construction review task not found')
    return task


@router.post('/inspection-cases/{case_id}/construction-review-tasks/{task_id}/acknowledge')
def acknowledge_construction_impact(pid: int, case_id: int, task_id: int,
                                    data: ConstructionImpactReviewIn,
                                    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Construction owner records an inspection acknowledgment, not QA clearance."""
    from app.domains.identity_projects.security import permitted
    # Construction owners need Construction scope, not QA permissions.
    from app.domains.supply_chain import service as supply_service
    project = supply_service._project(db, u, pid, action=None)
    permitted(db, u, project, 'construction.view')
    # Lock the QA case before the task, in the same order as QA verification.
    # This serializes acknowledgment with QA case state changes and fails closed
    # if a case is no longer revoked before writing construction evidence.
    case = (db.query(StoresInspectionCase).filter_by(
        id=case_id, organization_id=u.organization_id, project_id=pid
    ).with_for_update().first())
    if case is None:
        raise HTTPException(404, 'Inspection case not found')
    if case.status != 'Quality Revoked':
        raise HTTPException(409, 'Construction acknowledgment requires a revoked inspection case')
    task = _impact_task(db, u, pid, case_id, task_id)
    if task.owner_id != u.id:
        raise HTTPException(403, 'Only the assigned construction reviewer may acknowledge')
    if task.version != data.task_version:
        raise HTTPException(409, 'Task changed; reload and retry')
    if task.status != 'Open':
        raise HTTPException(409, 'Only open construction review tasks can be acknowledged')
    task.status = 'In Progress'
    task.evidence = 'Construction acknowledgment: ' + data.evidence.strip()
    task.version += 1
    audit(db, u, 'acknowledge_construction_impact', 'coordination_tasks', task.id,
          details={'inspection_case_id': case_id, 'task_version': task.version,
                   'qa_verified': False, 'impact_scope_verified': False}, project_id=pid)
    db.commit()
    return {'task_id': task.id, 'status': task.status, 'version': task.version,
            'qa_verified': False, 'impact_scope_verified': False}


@router.post('/inspection-cases/{case_id}/construction-review-tasks/{task_id}/qa-verify')
def verify_construction_impact(pid: int, case_id: int, task_id: int,
                               data: ConstructionImpactReviewIn,
                               u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """QA signs off a documented review; no stock release or installed-quantity certification."""
    from app.domains.identity_projects.security import permitted
    # QA verification requires quality.edit; it does not require Construction access.
    qa_access(db, u, pid, edit=True)
    case = db.query(StoresInspectionCase).filter_by(
        id=case_id, organization_id=u.organization_id, project_id=pid).with_for_update().first()
    if case is None:
        raise HTTPException(404, 'Inspection case not found')
    if case.status != 'Quality Revoked':
        raise HTTPException(409, 'QA revocation review requires a revoked inspection case')
    task = _impact_task(db, u, pid, case_id, task_id)
    if task.version != data.task_version:
        raise HTTPException(409, 'Task changed; reload and retry')
    if task.status != 'In Progress' or not task.evidence.startswith('Construction acknowledgment: '):
        raise HTTPException(409, 'Construction acknowledgment is required before QA verification')
    if task.owner_id == u.id:
        raise HTTPException(403, 'QA verification requires an independent reviewer')
    task.evidence += '\nQA verification by user ' + str(u.id) + ': ' + data.evidence.strip()
    task.status = 'Completed'
    task.version += 1
    audit(db, u, 'verify_construction_impact', 'coordination_tasks', task.id,
          details={'inspection_case_id': case_id, 'task_version': task.version,
                   'construction_owner_id': task.owner_id, 'qa_reviewer_id': u.id,
                   'impact_scope_verified': False}, project_id=pid)
    db.commit()
    return {'task_id': task.id, 'status': task.status, 'version': task.version,
            'qa_verified': True, 'impact_scope_verified': False,
            'note': 'Review completion does not reverse stock, authorize issue or prove all exposure mapped.'}
