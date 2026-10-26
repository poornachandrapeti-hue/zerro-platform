"""Phase 4 foundational material request lifecycle. Never posts/reserves stock."""
from datetime import date, datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated, permitted
from app.domains.identity_projects.router import audit, commit
from app.domains.supply_chain.models import ProcurementItem, MaterialRequirement, RequirementLine, RequisitionLine, PurchaseRequisition, RfqLine, RequestForQuotation, PurchaseOrder
from app.domains.supply_chain import service
from app.domains.construction.models import WorkPackage, WorkPackageRequirement
from .models import StoresMaterialRequest, StoresLotReservation
from .reservation_work_scope import validate_scope
from app.domains.coordination.models import Task, ReminderPolicy
from app.domains.coordination.service import _task, _close_tasks

router = APIRouter(prefix="/api/projects/{pid}/stores", tags=["Stores Material Requests"])

class RequestIn(BaseModel):
    request_key: str = Field(min_length=1, max_length=120)
    requirement_line_id: int = Field(gt=0)
    item_id: int
    quantity: Decimal = Field(gt=0)
    required_date: date
    work_package_id: int | None = None
    planning_wbs_id: int | None = None
    reason: str = Field(default="", max_length=2000)

class ReviewIn(BaseModel):
    version: int = Field(ge=1)
    decision: str
    reason: str = Field(min_length=3, max_length=2000)

def shortage(demand, allocated):
    """Unallocated approved demand, NOT warehouse stock shortage."""
    return max(Decimal('0'), Decimal(str(demand)) - Decimal(str(allocated)))

def payload(r):
    return dict(id=r.id, request_key=r.request_key, requirement_line_id=r.requirement_line_id, requester_company_id=r.requester_company_id, origin=("Partner" if r.requester_company_id is not None else "Internal"), item_id=r.item_id,
        quantity=str(r.requested_quantity), unit=r.base_unit, required_date=str(r.required_date),
        work_package_id=r.work_package_id, planning_wbs_id=r.planning_wbs_id,
        status=r.status, version=r.version, created_by=r.created_by, reviewed_by=r.reviewed_by,
        review_reason=r.review_reason)

def _project(db, user, pid, action='stores.requests.view'):
    project = service._project(db, user, pid, action=None)
    permitted(db, user, project, action)
    return project

@router.post('/material-requests', status_code=201)
def create_request(pid: int, data: RequestIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid, action="stores.requests.create")
    validate_scope(db, project, work_package_id=data.work_package_id, planning_wbs_id=data.planning_wbs_id)
    # Lock the canonical requirement line to prevent parallel requests from exceeding its approved demand.
    line = db.execute(select(RequirementLine).where(RequirementLine.id == data.requirement_line_id).with_for_update()).scalar_one_or_none()
    parent = db.get(MaterialRequirement, line.requirement_id) if line else None
    if not line or not parent or parent.project_id != pid or parent.organization_id != u.organization_id:
        raise HTTPException(422, 'Approved material requirement line not found in this project')
    if parent.status != 'Approved' or parent.impact_state == 'Review required':
        raise HTTPException(409, 'Requirement must be approved and have no unresolved drawing impact')
    chosen_item = db.get(ProcurementItem, data.item_id)
    if not chosen_item or line.item_id != data.item_id or line.unit != chosen_item.base_unit:
        raise HTTPException(422, 'Requirement item or stock unit differs; approved conversion is required')
    prior = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.requirement_line_id == line.id,
        StoresMaterialRequest.status.in_(['Draft','Pending Approval','Approved'])
    )).scalars().all()
    remaining = Decimal(str(line.quantity)) - sum((Decimal(str(r.requested_quantity)) for r in prior), Decimal('0'))
    if data.quantity > remaining:
        raise HTTPException(409, 'Issue requests exceed the approved requirement-line quantity')
    if data.required_date < date.today():
        raise HTTPException(422, 'Required date cannot be in the past')
    item = db.get(ProcurementItem, data.item_id)
    if not item or item.organization_id != u.organization_id or not item.active:
        raise HTTPException(422, 'Active material master not found')
    key = data.request_key.strip()
    if not key: raise HTTPException(422, 'Request key must not be blank')
    existing = db.execute(select(StoresMaterialRequest).where(StoresMaterialRequest.project_id == pid, StoresMaterialRequest.request_key == key)).scalar_one_or_none()
    if existing: raise HTTPException(409, 'Request number already exists')
    row = StoresMaterialRequest(organization_id=u.organization_id, project_id=pid, request_key=key, requirement_line_id=line.id,
        item_id=item.id, requested_quantity=data.quantity, base_unit=item.base_unit,
        required_date=data.required_date, work_package_id=data.work_package_id,
        planning_wbs_id=data.planning_wbs_id, reason=data.reason.strip(), created_by=u.id)
    db.add(row); db.flush(); audit(db, u, 'create', 'stores_material_requests', row.id, project_id=pid); commit(db)
    return payload(row)

@router.get('/material-requests')
def list_requests(pid: int, status: str | None = None, limit: int = 100,
                  u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _project(db, u, pid, action="stores.requests.view")
    if limit < 1 or limit > 200: raise HTTPException(422, 'Limit must be 1–200')
    query = select(StoresMaterialRequest).where(StoresMaterialRequest.project_id == pid, StoresMaterialRequest.organization_id == u.organization_id)
    if status: query = query.where(StoresMaterialRequest.status == status)
    return [payload(r) for r in db.execute(query.order_by(StoresMaterialRequest.id.desc()).limit(limit)).scalars().all()]

@router.post('/material-requests/{request_id}/submit')
def submit_request(pid: int, request_id: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _project(db, u, pid, action="stores.requests.create")
    row = db.execute(select(StoresMaterialRequest).where(StoresMaterialRequest.id == request_id, StoresMaterialRequest.project_id == pid, StoresMaterialRequest.organization_id == u.organization_id).with_for_update()).scalar_one_or_none()
    if not row: raise HTTPException(404, 'Request not found')
    if row.status != 'Draft': raise HTTPException(409, 'Only draft requests may be submitted')
    line = db.get(RequirementLine, row.requirement_line_id)
    parent = db.get(MaterialRequirement, line.requirement_id) if line else None
    if not parent or parent.status != 'Approved' or parent.impact_state == 'Review required':
        raise HTTPException(409, 'Source requirement approval was revoked or changed')
    if row.created_by != u.id: raise HTTPException(403, 'Only the request creator may submit')
    row.status = 'Pending Approval'; row.version += 1
    audit(db,u,'submit','stores_material_requests',row.id,project_id=pid); commit(db)
    return payload(row)

@router.get('/material-requests/review-queue')
def review_queue(pid: int, limit: int = 100,
                 u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Internal-only queue; no partner route or inventory side effects."""
    project = _project(db, u, pid, action="stores.requests.review")
    if not 1 <= limit <= 200:
        raise HTTPException(422, 'Limit must be 1–200')
    rows = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.organization_id == u.organization_id,
        StoresMaterialRequest.status == 'Pending Approval'
    ).order_by(StoresMaterialRequest.id.asc()).limit(limit)).scalars().all()
    return [payload(r) for r in rows]


def validate_partner_review_scope(db, row, parent):
    """Fail closed when a contractor's work assignment was revoked after submission."""
    if row.requester_company_id is None:
        return
    if parent.company_id != row.requester_company_id or not row.work_package_id:
        raise HTTPException(409, 'Contractor requirement ownership/work package changed')
    wp = db.execute(select(WorkPackage).where(
        WorkPackage.id == row.work_package_id,
        WorkPackage.project_id == row.project_id,
        WorkPackage.organization_id == row.organization_id,
        WorkPackage.company_id == row.requester_company_id
    )).scalar_one_or_none()
    if not wp or wp.release_state != 'Released' or wp.status in ('Cancelled', 'On Hold'):
        raise HTTPException(409, 'Contractor work package is no longer released')
    linked = db.execute(select(WorkPackageRequirement.id).where(
        WorkPackageRequirement.package_id == wp.id,
        WorkPackageRequirement.requirement_id == parent.id
    )).first()
    if not linked:
        raise HTTPException(409, 'Approved requirement no longer belongs to the contractor work package')


@router.post('/material-requests/{request_id}/review')
def review_request(pid: int, request_id: int, data: ReviewIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db,u,pid,action="stores.requests.review")
    row = db.execute(select(StoresMaterialRequest).where(StoresMaterialRequest.id == request_id, StoresMaterialRequest.project_id == pid, StoresMaterialRequest.organization_id == u.organization_id).with_for_update()).scalar_one_or_none()
    if not row: raise HTTPException(404,'Request not found')
    if row.status != 'Pending Approval' or row.version != data.version: raise HTTPException(409,'Request status/version changed')
    if row.created_by == u.id: raise HTTPException(403,'Maker cannot approve/reject own request')
    line = db.get(RequirementLine, row.requirement_line_id)
    parent = db.get(MaterialRequirement, line.requirement_id) if line else None
    if not parent or parent.status != 'Approved' or parent.impact_state == 'Review required':
        raise HTTPException(409, 'Source requirement is no longer approved')
    if data.decision not in ('Approved','Rejected'): raise HTTPException(422,'Decision must be Approved or Rejected')
    if data.decision == 'Approved':
        if row.requirement_line_id is None:
            raise HTTPException(409, 'Unlinked legacy requests cannot be approved')
        validate_partner_review_scope(db, row, parent)
    if not data.reason.strip(): raise HTTPException(422,'Review reason required')
    row.status=data.decision; row.reviewed_by=u.id; row.review_reason=data.reason.strip(); row.version+=1
    # Complete the canonical My Tasks assignment as part of the SAME database transaction.
    # Rejecting a request ends the review task too; it does not authorize stock movement.
    _close_tasks(db, pid, 'stores.material_request.approval', row.id, 'Completed',
                 f'Stores request {data.decision} by reviewer {u.id}: {row.review_reason}')
    audit(db,u,data.decision.lower(),'stores_material_requests',row.id,project_id=pid); commit(db)
    return payload(row)

@router.get('/material-requests/shortfalls')
def request_shortfalls(pid:int, u:User=Depends(authenticated), db:Session=Depends(get_db)):
    _project(db,u,pid,action="stores.requests.view")
    rows=db.execute(select(StoresMaterialRequest).where(StoresMaterialRequest.project_id==pid,
        StoresMaterialRequest.organization_id==u.organization_id, StoresMaterialRequest.status=='Approved')).scalars().all()
    from .allocation_lifecycle import request_summary
    results = []
    for r in rows:
        summary = request_summary(db, r)
        results.append(dict(request_id=r.id, item_id=r.item_id, unit=r.base_unit,
            approved_demand=summary['approved_quantity'],
            active_reserved=summary['active_reserved_quantity'],
            issued_against_reservations=summary['consumed_by_issue'],
            unallocated_demand=summary['unallocated_quantity'],
            overcommitted=summary['overcommitted'],
            note='Unallocated issue request, not additional procurement demand or physical stock shortage'))
    return results


@router.get('/material-requests/work-package-allocation')
def work_package_allocation(pid: int, work_package_id: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Read-only request lifecycle by work package; NOT an available-stock claim."""
    project = _project(db, u, pid, action='stores.requests.view')
    if work_package_id <= 0:
        raise HTTPException(422, 'Work package ID must be positive')
    validate_scope(db, project, work_package_id=work_package_id, planning_wbs_id=None)
    requests = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.organization_id == u.organization_id,
        StoresMaterialRequest.work_package_id == work_package_id,
        StoresMaterialRequest.status == 'Approved'
    ).order_by(StoresMaterialRequest.id)).scalars().all()
    from .allocation_lifecycle import request_summary
    lines = []
    for request in requests:
        summary = request_summary(db, request)
        lines.append(dict(request_id=request.id, requirement_line_id=request.requirement_line_id,
            item_id=request.item_id, unit=request.base_unit, required_date=str(request.required_date),
            **summary))
    return dict(project_id=pid, work_package_id=work_package_id, items=lines,
        note='Approved issue-request allocation lifecycle only. Not verified eligible stock, procurement shortage, or construction progress.')


class AllocateIssueRequestIn(BaseModel):
    lot_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    allocation_key: str = Field(min_length=1, max_length=120)


@router.post('/material-requests/{request_id}/allocate-lot', status_code=201)
def allocate_issue_request(pid: int, request_id: int, data: AllocateIssueRequestIn,
                           u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid, action="stores.requests.allocate")
    from .request_allocation import allocate_request
    result = allocate_request(db, u, project, request_id=request_id,
        lot_id=data.lot_id, quantity=data.quantity, request_key=data.allocation_key)
    if not result['replayed']:
        audit(db, u, 'allocate_lot', 'stores_material_requests', request_id, project_id=pid)
        commit(db)
    return result


@router.get('/material-requests/{request_id}/allocations')
def list_issue_request_allocations(pid: int, request_id: int,
                                  u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _project(db, u, pid, action="stores.requests.view")
    request = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.id == request_id,
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.organization_id == u.organization_id)).scalar_one_or_none()
    if request is None:
        raise HTTPException(404, 'Material request not found')
    from .allocation_lifecycle import request_summary
    return dict(request_id=request_id, **request_summary(db, request))


# Upstream procurement context is traced through canonical foreign keys. PO promised dates
# are supplier commitments, not confirmed arrivals or QA-cleared warehouse stock.
def linked_procurement_commitments(db, project_id, organization_id, requirement_line_id):
    result = db.execute(
        select(PurchaseOrder.id, PurchaseOrder.number, PurchaseOrder.status,
               PurchaseOrder.promised_date, PurchaseRequisition.id)
        .join(RequestForQuotation, RequestForQuotation.id == PurchaseOrder.rfq_id)
        .join(PurchaseRequisition, PurchaseRequisition.id == RequestForQuotation.requisition_id)
        .join(RequisitionLine, RequisitionLine.requisition_id == PurchaseRequisition.id)
        .where(RequisitionLine.requirement_line_id == requirement_line_id,
               PurchaseRequisition.project_id == project_id,
               PurchaseRequisition.organization_id == organization_id,
               PurchaseOrder.project_id == project_id,
               PurchaseOrder.organization_id == organization_id)
        .distinct()
        .order_by(PurchaseOrder.id)
    ).all()
    return [dict(purchase_order_id=r[0], purchase_order_number=r[1],
                 purchase_order_status=r[2], promised_date=r[3].isoformat() if r[3] else None,
                 purchase_requisition_id=r[4],
                 eta_verified=False, received_quantity_verified=False)
            for r in result]


def schedule_alignment(required_date, planned_start, planned_finish):
    if planned_start is None:
        return 'Planning Start Unavailable'
    if required_date > planned_start:
        return 'Required After Planned Start'
    return 'Required By Planned Start'


# Phase 4: advisory workfront demand readiness. Never equate an allocation with QA release.
def readiness_classification(approved, reserved, issued):
    """Classify only the allocation lifecycle; this is NOT material availability."""
    need = Decimal(str(approved))
    held = Decimal(str(reserved))
    handed = Decimal(str(issued))
    if need <= 0 or held < 0 or handed < 0 or held + handed > need:
        return 'Review Required'
    if held + handed == 0:
        return 'Not Allocated'
    if held + handed < need:
        return 'Partially Allocated'
    return 'Allocation Covered'


def material_readiness_blockers(*, demand_quantity, active_reserved, issued_quantity,
                                required_date, po_commitments, qa_verified=False, stock_verified=False):
    """Read-only evidence flags: never infer physical availability from procurement or allocation."""
    demand = Decimal(str(demand_quantity))
    reserved = Decimal(str(active_reserved))
    issued = Decimal(str(issued_quantity))
    flags = []
    if demand <= 0 or reserved < 0 or issued < 0 or reserved + issued > demand:
        flags.append('ALLOCATION_DATA_REVIEW_REQUIRED')
    if not qa_verified:
        flags.append('QA_CLEARANCE_NOT_VERIFIED')
    if not stock_verified:
        flags.append('LOT_STOCK_BALANCE_NOT_VERIFIED')
    if max(Decimal('0'), demand - reserved - issued) > 0:
        flags.append('APPROVED_REQUEST_NOT_FULLY_ALLOCATED')
    if required_date < date.today():
        flags.append('MATERIAL_REQUIRED_DATE_PASSED')
    if not po_commitments:
        flags.append('NO_LINKED_PO_COMMITMENT')
    else:
        dates = [x.get('promised_date') for x in po_commitments if x.get('promised_date')]
        if not dates:
            flags.append('PO_PROMISED_DATE_UNAVAILABLE')
        elif all(x > required_date.isoformat() for x in dates):
            flags.append('PO_PROMISES_AFTER_MATERIAL_REQUIRED_DATE')
        flags.append('PO_DELIVERY_NOT_VERIFIED')
    return flags


@router.get('/material-requests/work-package-readiness')
def work_package_readiness(pid: int, work_package_id: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Advisory demand coverage, with explicit upstream verification gaps."""
    project = _project(db, u, pid, action='stores.requests.view')
    validate_scope(db, project, work_package_id=work_package_id, planning_wbs_id=None)
    from .allocation_lifecycle import request_summary
    work_package = db.get(WorkPackage, work_package_id)
    requests = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.organization_id == u.organization_id,
        StoresMaterialRequest.work_package_id == work_package_id,
        StoresMaterialRequest.status == 'Approved'
    ).order_by(StoresMaterialRequest.required_date, StoresMaterialRequest.id)).scalars().all()
    items = []
    for request in requests:
        summary = request_summary(db, request)
        label = readiness_classification(summary['approved_quantity'], summary['active_reserved_quantity'], summary['consumed_by_issue'])
        commitments = linked_procurement_commitments(db, pid, u.organization_id, request.requirement_line_id) if request.requirement_line_id else []
        blockers = material_readiness_blockers(demand_quantity=summary['approved_quantity'],
            active_reserved=summary['active_reserved_quantity'], issued_quantity=summary['consumed_by_issue'],
            required_date=request.required_date, po_commitments=commitments)
        items.append(dict(
            readiness_blockers=blockers, readiness_exception_count=len(blockers),
            request_id=request.id, requirement_line_id=request.requirement_line_id,
            item_id=request.item_id, unit=request.base_unit, required_date=str(request.required_date),
            demand_quantity=summary['approved_quantity'], active_reserved=summary['active_reserved_quantity'],
            issued_quantity=summary['consumed_by_issue'], unallocated_quantity=summary['unallocated_quantity'],
            allocation_status=label, required_date_passed=request.required_date < date.today(),
            schedule_alignment=schedule_alignment(request.required_date, work_package.planned_start if work_package else None, work_package.planned_finish if work_package else None),
            linked_purchase_orders=commitments, procurement_commitment_count=len(commitments),
            qa_eligible_stock_verified=False, procurement_delivery_eta_verified=False,
            physical_workfront_readiness='Unverified',
            construction_progress_credited=False
        ))
    return dict(project_id=pid, work_package_id=work_package_id, lines=items,
        work_package_planned_start=str(work_package.planned_start) if work_package and work_package.planned_start else None,
        work_package_planned_finish=str(work_package.planned_finish) if work_package and work_package.planned_finish else None,
        overall_readiness='Unverified',
        note='Allocation coverage only. Live QA-cleared stock, purchase-order ETA, and planning schedule dependencies are not yet verified. Never authorize issue or work start from this report.')


@router.get('/material-requests/readiness-exceptions')
def readiness_exceptions(pid: int, work_package_id: int, u: User = Depends(authenticated),
                         db: Session = Depends(get_db)):
    """Project-scoped advisory exceptions; no automated tasks or unverified shortage claims."""
    report = work_package_readiness(pid=pid, work_package_id=work_package_id, u=u, db=db)
    return dict(project_id=pid, work_package_id=work_package_id,
        exceptions=[dict(request_id=r['request_id'], requirement_line_id=r['requirement_line_id'],
            item_id=r['item_id'], required_date=r['required_date'],
            blockers=r['readiness_blockers'], severity='Review Required',
            physical_shortage_confirmed=False, issue_authorized=False)
            for r in report['lines'] if r['readiness_blockers']],
        generated_from='Existing request, Planning, Procurement and reservation read models',
        note='Advisory report only. QA-cleared available stock and physically verified delivery are not established; no Tasks or Command Center notifications have been sent.')


@router.get('/material-requests/approval-aging')
def material_request_approval_aging(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Read-only reviewer queue for notification integration; no messages are sent."""
    _project(db, u, pid, action='stores.requests.review')
    rows = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.organization_id == u.organization_id,
        StoresMaterialRequest.status == 'Pending Approval'
    ).order_by(StoresMaterialRequest.required_date, StoresMaterialRequest.id).limit(200)).scalars().all()
    return dict(project_id=pid, pending_count=len(rows), requests=[dict(
        id=r.id, request_key=r.request_key, required_date=str(r.required_date),
        days_until_required=(r.required_date - date.today()).days,
        work_package_id=r.work_package_id, request_origin=('Partner' if r.requester_company_id is not None else 'Internal'),
        priority='Past Required Date' if r.required_date < date.today() else 'Pending Review'
    ) for r in rows], note='Reviewer queue only; delivery notifications and SLA escalation are not yet connected.')


class ApprovalTaskIn(BaseModel):
    reviewer_user_id: int = Field(gt=0)


@router.post('/material-requests/{request_id}/approval-task')
def ensure_material_approval_task(pid: int, request_id: int, data: ApprovalTaskIn,
                                  u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Explicit assignment to a permitted reviewer; shares My Tasks and its notification service.

    Never creates a physical shortage alert or modifies material availability.
    The pending request row lock serializes duplicate assignment attempts.
    """
    project = _project(db, u, pid, action='stores.requests.review')
    request = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.id == request_id,
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.organization_id == u.organization_id,
    ).with_for_update()).scalar_one_or_none()
    if request is None:
        raise HTTPException(404, 'Stores issue request not found')
    if request.status != 'Pending Approval':
        raise HTTPException(409, 'Only pending requests can receive approval tasks')
    if request.created_by == data.reviewer_user_id:
        raise HTTPException(403, 'Request creator cannot be assigned as independent reviewer')
    reviewer = db.get(User, data.reviewer_user_id)
    if not reviewer or not reviewer.active or reviewer.organization_id != u.organization_id:
        raise HTTPException(422, 'Reviewer does not belong to this organization')
    # Cross-check permissions using the same project RBAC system as the review endpoint.
    permitted(db, reviewer, project, 'stores.requests.review')
    # Reuse the shared reminder policy, but do not route sensitive Stores approvals
    # to recipients who lack the current project's independent approval permission.
    policy = db.execute(select(ReminderPolicy).where(
        ReminderPolicy.project_id == pid,
        ReminderPolicy.record_type == 'stores.material_request.approval',
    )).scalar_one_or_none()
    if policy:
        for recipient_id in set(policy.recipient_ids or []):
            recipient = db.get(User, recipient_id)
            if not recipient or not recipient.active or recipient.organization_id != u.organization_id:
                raise HTTPException(409, 'Stores escalation policy contains an inactive or invalid recipient')
            if recipient.id == request.created_by:
                raise HTTPException(409, 'Stores escalation recipient cannot be the request creator')
            try:
                permitted(db, recipient, project, 'stores.requests.review')
            except HTTPException:
                raise HTTPException(409, 'Stores escalation recipient lacks current project approval access')
    existing = db.execute(select(Task).where(
        Task.organization_id == u.organization_id,
        Task.project_id == pid,
        Task.source_type == 'stores.material_request.approval',
        Task.source_id == request.id,
        Task.status.in_(['Open', 'In Progress', 'Blocked']),
    ).with_for_update()).scalars().first()
    if existing:
        if existing.owner_id != reviewer.id:
            raise HTTPException(409, 'Approval task is already assigned; use shared task reassignment')
        return dict(task_id=existing.id, created=False, request_id=request.id, owner_id=existing.owner_id)
    task = _task(db, u, project, reviewer.id,
                 f'Review Stores issue request {request.request_key}',
                 'stores.material_request.approval', request.id, 'High', request.required_date)
    audit(db, u, 'assign_approval_task', 'stores_material_requests', request.id, project_id=pid)
    commit(db)
    return dict(task_id=task.id, created=True, request_id=request.id, owner_id=reviewer.id)


@router.get('/material-requests/approval-escalation-policy')
def material_approval_escalation_policy(pid: int, u: User = Depends(authenticated),
                                        db: Session = Depends(get_db)):
    """Show Stores approval reminder configuration without creating notifications.

    The shared job worker runs reminders only after a task is assigned and a policy
    exists. Policy recipients are not exposed to ordinary request viewers.
    """
    project = _project(db, u, pid, action='stores.requests.review')
    policy = db.execute(select(ReminderPolicy).where(
        ReminderPolicy.project_id == project.id,
        ReminderPolicy.record_type == 'stores.material_request.approval',
    )).scalar_one_or_none()
    return dict(project_id=pid, record_type='stores.material_request.approval',
                configured=policy is not None,
                reminder_hours=policy.reminder_hours if policy else None,
                escalate_after_hours=policy.escalate_after_hours if policy else None,
                escalation_recipient_count=len(set(policy.recipient_ids or [])) if policy else 0,
                enabled_for_new_tasks=bool(policy),
                note=('Shared reminder worker delivers scheduled jobs; active job execution is not verified by this endpoint.'
                      if policy else 'Configure the existing project reminder policy; no automatic escalation is scheduled without it.'))


@router.get('/material-requests/command-center-approval-summary')
def material_approval_summary(pid: int, u: User = Depends(authenticated),
                              db: Session = Depends(get_db)):
    """Minimal project-scoped read model; not a physical inventory or shortage KPI."""
    _project(db, u, pid, action='stores.requests.view')
    pending = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.organization_id == u.organization_id,
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.status == 'Pending Approval',
    )).scalars().all()
    today = date.today()
    return dict(project_id=pid, pending_approval_count=len(pending),
                past_required_date_count=sum(row.required_date < today for row in pending),
                partner_request_count=sum(row.requester_company_id is not None for row in pending),
                as_of_date=today.isoformat(),
                physical_stock_readiness='Unverified',
                source='stores_material_requests',
                note='Authorization-scoped approval workload only. Does not confirm shortages, QA release, or earned progress.')


@router.get('/material-requests/approval-task-status')
def material_request_task_status(pid: int, u: User = Depends(authenticated),
                                 db: Session = Depends(get_db)):
    """Project-scoped task lifecycle read model, not a stock readiness signal.

    Intended for Internal Portal and a separately authorized Command Center consumer.
    Command Center must independently enforce service identity and project scope.
    """
    _project(db, u, pid, action='stores.requests.view')
    rows = db.execute(select(Task).where(
        Task.organization_id == u.organization_id,
        Task.project_id == pid,
        Task.source_type == 'stores.material_request.approval',
    ).order_by(Task.id.desc()).limit(500)).scalars().all()
    ids = {t.source_id for t in rows}
    requests = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.organization_id == u.organization_id,
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.id.in_(ids),
    )).scalars().all() if ids else []
    by_id = {r.id: r for r in requests}
    today = date.today()
    details = [dict(task_id=t.id, request_id=t.source_id, task_status=t.status,
                    reviewer_user_id=t.owner_id, due_date=str(t.due_date) if t.due_date else None,
                    overdue=bool(t.due_date and t.due_date < today and t.status in ('Open', 'In Progress', 'Blocked')),
                    request_status=by_id[t.source_id].status if t.source_id in by_id else 'Unavailable')
               for t in rows if t.source_id in by_id]
    return dict(project_id=pid, as_of_date=today.isoformat(),
                open_task_count=sum(t['task_status'] in ('Open','In Progress','Blocked') for t in details),
                overdue_task_count=sum(t['overdue'] for t in details),
                completed_task_count=sum(t['task_status'] == 'Completed' for t in details),
                tasks=details, truncated=len(rows) == 500,
                physical_stock_readiness='Unverified',
                note='Approval task lifecycle only; no physical inventory or confirmed shortage metric.')


# Command Center source feed; service identity only, no partner or browser access.
@router.get('/internal-command-center/approval-workload')
def internal_stores_approval_workload(pid: int, request: __import__('fastapi').Request,
                                     db: Session = Depends(get_db)):
    """Read-only Stores approval-workload feed for the separately deployed Command Center.

    The consuming service MUST recheck live user/project grants before displaying these
    data. This endpoint never authorizes viewers directly or calculates stock readiness.
    """
    import hmac
    from app.config import settings
    from app.domains.identity_projects.models import Project
    expected = settings.command_center_identity_service_key
    provided = request.headers.get('X-ZerroR-Service-Key', '')
    if not expected or not hmac.compare_digest(provided, expected):
        raise HTTPException(403, 'Command Center service authentication required')
    project = db.get(Project, pid)
    if not project:
        raise HTTPException(404, 'Project not found')
    rows = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.organization_id == project.organization_id,
        StoresMaterialRequest.status == 'Pending Approval',
    )).scalars().all()
    pending_ids = [r.id for r in rows]
    tasks = db.execute(select(Task).where(
        Task.organization_id == project.organization_id,
        Task.project_id == pid,
        Task.source_type == 'stores.material_request.approval',
        Task.source_id.in_(pending_ids or [-1]),
        Task.status.in_(['Open', 'In Progress', 'Blocked']),
    )).scalars().all()
    today = date.today()
    active_request_ids = {t.source_id for t in tasks}
    return {
        'organization_id': project.organization_id,
        'project_id': pid,
        'source': 'zerrobuild.stores.material_requests',
        'read_only': True,
        'as_of': datetime.now(timezone.utc).isoformat(),
        'pending_approval_count': len(rows),
        'past_required_date_count': sum(r.required_date < today for r in rows),
        'partner_origin_pending_count': sum(r.requester_company_id is not None for r in rows),
        'pending_without_active_task_count': sum(r.id not in active_request_ids for r in rows),
        'overdue_active_task_count': sum(bool(t.due_date and t.due_date < today) for t in tasks),
        'physical_stock_readiness': 'Unverified',
        'inventory_available_quantity': None,
        'verified_shortage_quantity': None,
        'notice': 'Approval-workload evidence only. Consumer must validate live project grants; no stock or progress assertion.',
    }
