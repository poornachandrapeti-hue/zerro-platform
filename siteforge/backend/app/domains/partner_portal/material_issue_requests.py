"""Scoped contractor material issue requests against already approved canonical demand.
No stock posting, reservation, procurement demand or approvals are made here.
"""
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.router import audit, commit
from app.domains.supply_chain.models import MaterialRequirement, RequirementLine, ProcurementItem
from app.domains.construction.models import WorkPackage, WorkPackageRequirement
from app.domains.stores_inventory.models import StoresMaterialRequest, StoresLotReservation
from app.domains.stores_inventory.material_requests import payload
from .transactions import _scope

router = APIRouter(prefix='/api/partner/projects/{pid}/stores', tags=['partner-stores-requests'])

class PartnerIssueRequestIn(BaseModel):
    request_key: str = Field(min_length=1, max_length=120)
    requirement_line_id: int = Field(gt=0)
    work_package_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    required_date: date
    reason: str = Field(default='', max_length=2000)

def _approved_source(db, pid, company_id, org_id, line_id, package_id):
    wp = db.execute(select(WorkPackage).where(WorkPackage.id == package_id,
        WorkPackage.project_id == pid, WorkPackage.organization_id == org_id,
        WorkPackage.company_id == company_id)).scalar_one_or_none()
    if not wp or wp.release_state != 'Released' or wp.status in ('Cancelled','On Hold'):
        raise HTTPException(403, 'Assigned released work package required')
    line = db.execute(select(RequirementLine).where(RequirementLine.id == line_id).with_for_update()).scalar_one_or_none()
    req = db.get(MaterialRequirement, line.requirement_id) if line else None
    if not req or req.project_id != pid or req.organization_id != org_id or req.company_id != company_id:
        raise HTTPException(403, 'Requirement is not assigned to this contractor and project')
    if req.status != 'Approved' or req.impact_state == 'Review required':
        raise HTTPException(409, 'Requirement is not currently approved for release')
    linked = db.execute(select(WorkPackageRequirement.id).where(
        WorkPackageRequirement.package_id == wp.id, WorkPackageRequirement.requirement_id == req.id)).first()
    if not linked:
        raise HTTPException(403, 'Requirement is not assigned to selected work package')
    item = db.get(ProcurementItem, line.item_id)
    if not item or item.organization_id != org_id or not item.active or item.base_unit != line.unit:
        raise HTTPException(409, 'Canonical material/unit mismatch; require approved conversion')
    return line, item, wp

@router.get('/issue-request-sources')
def issue_sources(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    company = _scope(db, u, pid)
    wps = db.execute(select(WorkPackage).where(WorkPackage.organization_id == u.organization_id,
        WorkPackage.project_id == pid, WorkPackage.company_id == company.id,
        WorkPackage.release_state == 'Released', WorkPackage.status.notin_(['Cancelled','On Hold']))).scalars().all()
    ids = [w.id for w in wps]
    associations = db.execute(select(WorkPackageRequirement).where(WorkPackageRequirement.package_id.in_(ids))).scalars().all() if ids else []
    req_ids = {a.requirement_id for a in associations}
    reqs = db.execute(select(MaterialRequirement).where(MaterialRequirement.id.in_(req_ids),
        MaterialRequirement.project_id == pid, MaterialRequirement.organization_id == u.organization_id,
        MaterialRequirement.company_id == company.id, MaterialRequirement.status == 'Approved',
        MaterialRequirement.impact_state != 'Review required')).scalars().all() if req_ids else []
    result=[]
    for req in reqs:
        lines=db.execute(select(RequirementLine).where(RequirementLine.requirement_id==req.id)).scalars().all()
        for line in lines:
            result.append(dict(requirement_line_id=line.id, requirement_id=req.id, requirement=req.number,
                item_id=line.item_id, quantity=str(line.quantity), unit=line.unit,
                work_package_ids=[a.package_id for a in associations if a.requirement_id==req.id]))
    return dict(work_packages=[dict(id=w.id,code=w.code,name=w.name) for w in wps], requirements=result)

@router.get('/material-requests')
def list_my_requests(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    company = _scope(db, u, pid)
    rows=db.execute(select(StoresMaterialRequest).where(StoresMaterialRequest.organization_id==u.organization_id,
        StoresMaterialRequest.project_id==pid, StoresMaterialRequest.requester_company_id==company.id)
        .order_by(StoresMaterialRequest.id.desc()).limit(100)).scalars().all()
    return [payload(r) for r in rows]

@router.post('/material-requests', status_code=201)
def create_partner_request(pid: int, data: PartnerIssueRequestIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    company = _scope(db, u, pid)
    if data.required_date < date.today():
        raise HTTPException(422, 'Required date cannot be in the past')
    line, item, wp = _approved_source(db,pid,company.id,u.organization_id,data.requirement_line_id,data.work_package_id)
    key=data.request_key.strip()
    if not key: raise HTTPException(422, 'Request number required')
    existing=db.execute(select(StoresMaterialRequest).where(StoresMaterialRequest.project_id==pid,
        StoresMaterialRequest.request_key==key)).scalar_one_or_none()
    if existing: raise HTTPException(409, 'Request number already exists')
    rows=db.execute(select(StoresMaterialRequest).where(StoresMaterialRequest.project_id==pid,
        StoresMaterialRequest.requirement_line_id==line.id,
        StoresMaterialRequest.status.in_(['Draft','Pending Approval','Approved']))).scalars().all()
    used=sum((Decimal(str(r.requested_quantity)) for r in rows),Decimal('0'))
    if used + data.quantity > Decimal(str(line.quantity)):
        raise HTTPException(409, 'Request exceeds remaining approved shared demand')
    row=StoresMaterialRequest(organization_id=u.organization_id,project_id=pid,requester_company_id=company.id,
        request_key=key,requirement_line_id=line.id,work_package_id=wp.id,item_id=item.id,
        requested_quantity=data.quantity,base_unit=item.base_unit,required_date=data.required_date,
        reason=data.reason.strip(),created_by=u.id,status='Draft')
    db.add(row);db.flush();audit(db,u,'partner_create','stores_material_requests',row.id,project_id=pid);commit(db)
    return payload(row)

@router.post('/material-requests/{request_id}/submit')
def submit_partner_request(pid:int,request_id:int,u:User=Depends(authenticated),db:Session=Depends(get_db)):
    company=_scope(db,u,pid)
    row=db.execute(select(StoresMaterialRequest).where(StoresMaterialRequest.id==request_id,
        StoresMaterialRequest.project_id==pid,StoresMaterialRequest.organization_id==u.organization_id,
        StoresMaterialRequest.requester_company_id==company.id).with_for_update()).scalar_one_or_none()
    if not row: raise HTTPException(404,'Issue request not found')
    if row.created_by!=u.id: raise HTTPException(403,'Only creator can submit')
    if row.status!='Draft': raise HTTPException(409,'Only draft issue requests can be submitted')
    _approved_source(db,pid,company.id,u.organization_id,row.requirement_line_id,row.work_package_id)
    row.status='Pending Approval';row.version+=1
    audit(db,u,'partner_submit','stores_material_requests',row.id,project_id=pid);commit(db)
    return payload(row)


@router.get('/material-requests/{request_id}/allocations')
def my_request_allocations(pid: int, request_id: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Company-scoped allocation status; never return other contractors' lots or warehouse stock."""
    company = _scope(db, u, pid)
    request = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.id == request_id,
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.organization_id == u.organization_id,
        StoresMaterialRequest.requester_company_id == company.id)).scalar_one_or_none()
    if request is None:
        raise HTTPException(404, 'Material issue request not found')
    from app.domains.stores_inventory.allocation_lifecycle import request_summary
    summary = request_summary(db, request)
    # Omit lot identifiers, warehouse details and other commercial data.
    return {'request_id': request.id, 'request_status': request.status,
            **summary}


@router.get('/material-handovers')
def partner_material_handovers(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Only company-owned handovers; no cross-contractor or warehouse information."""
    from app.domains.stores_inventory.models import StoresMaterialHandover
    from app.domains.stores_inventory.material_handovers import _payload
    company = _scope(db, u, pid)
    rows = db.execute(select(StoresMaterialHandover).join(StoresMaterialRequest,
        StoresMaterialRequest.id == StoresMaterialHandover.material_request_id).where(
        StoresMaterialHandover.organization_id == u.organization_id,
        StoresMaterialHandover.project_id == pid,
        StoresMaterialRequest.organization_id == u.organization_id,
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.requester_company_id == company.id,
        StoresMaterialRequest.created_by == u.id).order_by(StoresMaterialHandover.id.desc()).limit(200)).scalars().all()
    return {'records': [_payload(row) for row in rows]}

class PartnerAcknowledgeIn(BaseModel):
    version: int = Field(ge=1)
    received_quantity: Decimal = Field(ge=0, decimal_places=3)
    damaged_quantity: Decimal = Field(ge=0, decimal_places=3)
    evidence: str = Field(min_length=3, max_length=4000)
    discrepancy_note: str = Field(default='', max_length=4000)

@router.post('/material-handovers/{handover_id}/acknowledge')
def partner_acknowledge_handover(pid: int, handover_id: int, data: 'PartnerAcknowledgeIn',
    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    from app.domains.stores_inventory.models import StoresMaterialHandover
    from app.domains.stores_inventory.material_handovers import classify_discrepancy, _payload
    from datetime import datetime, timezone
    company = _scope(db, u, pid)
    record = db.execute(select(StoresMaterialHandover).where(
        StoresMaterialHandover.id == handover_id,
        StoresMaterialHandover.organization_id == u.organization_id,
        StoresMaterialHandover.project_id == pid).with_for_update()).scalar_one_or_none()
    if record is None: raise HTTPException(404, 'Handover not found')
    req = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.id == record.material_request_id,
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.organization_id == u.organization_id,
        StoresMaterialRequest.requester_company_id == company.id,
        StoresMaterialRequest.created_by == u.id)).scalar_one_or_none()
    if req is None: raise HTTPException(404, 'Handover not found')
    if record.dispatched_by == u.id: raise HTTPException(403, 'Dispatcher cannot acknowledge own handover')
    if record.status != 'Awaiting Acknowledgment' or record.version != data.version:
        raise HTTPException(409, 'Handover already handled or stale version')
    record.status = classify_discrepancy(record.dispatched_quantity, data.received_quantity, data.damaged_quantity, data.discrepancy_note)
    record.received_quantity = data.received_quantity
    record.damaged_quantity = data.damaged_quantity
    record.discrepancy_note = data.discrepancy_note.strip()
    record.acknowledgment_evidence = data.evidence.strip()
    record.acknowledged_by = u.id
    record.acknowledged_at = datetime.now(timezone.utc)
    record.version += 1
    audit(db,u,'partner_acknowledge_material_handover','stores_material_handovers',record.id,project_id=pid)
    commit(db)
    return _payload(record)

class PartnerMaterialReturnIn(BaseModel):
    handover_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    condition: str = Field(pattern='^(Unused|Damaged|Surplus)$')
    reason: str = Field(min_length=3, max_length=4000)

@router.get('/material-returns')
def partner_list_returns(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    from app.domains.stores_inventory.models import StoresMaterialReturn, StoresMaterialHandover
    from app.domains.stores_inventory.material_returns import payload
    company = _scope(db, u, pid)
    rows = db.execute(select(StoresMaterialReturn).join(StoresMaterialHandover,
        StoresMaterialHandover.id == StoresMaterialReturn.handover_id).join(StoresMaterialRequest,
        StoresMaterialRequest.id == StoresMaterialHandover.material_request_id).where(
        StoresMaterialReturn.organization_id == u.organization_id,
        StoresMaterialReturn.project_id == pid,
        StoresMaterialRequest.organization_id == u.organization_id,
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.requester_company_id == company.id,
        StoresMaterialRequest.created_by == u.id).order_by(StoresMaterialReturn.id.desc()).limit(200)).scalars().all()
    return {'records':[payload(r) for r in rows]}

@router.post('/material-returns', status_code=201)
def partner_submit_return(pid: int, data: PartnerMaterialReturnIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    from app.domains.stores_inventory.models import StoresMaterialHandover, StoresMaterialReturn
    from app.domains.stores_inventory.material_returns import validate_return_quantity, payload
    company = _scope(db, u, pid)
    h = db.execute(select(StoresMaterialHandover).where(
        StoresMaterialHandover.id == data.handover_id, StoresMaterialHandover.organization_id == u.organization_id,
        StoresMaterialHandover.project_id == pid).with_for_update()).scalar_one_or_none()
    if h is None: raise HTTPException(404, 'Handover not found')
    req = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.id == h.material_request_id,
        StoresMaterialRequest.organization_id == u.organization_id,
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.requester_company_id == company.id,
        StoresMaterialRequest.created_by == u.id)).scalar_one_or_none()
    if req is None: raise HTTPException(404, 'Handover not found')
    if h.status not in ('Acknowledged', 'Resolved') or h.received_quantity is None:
        raise HTTPException(409, 'Handover acknowledgment and discrepancy review must be complete')
    validate_return_quantity(h.received_quantity, data.quantity)
    if db.execute(select(StoresMaterialReturn.id).where(StoresMaterialReturn.handover_id == h.id)).first():
        raise HTTPException(409, 'Return already requested for this handover')
    row = StoresMaterialReturn(organization_id=u.organization_id, project_id=pid, handover_id=h.id,
        requested_quantity=data.quantity, condition=data.condition, reason=data.reason.strip(),
        submitted_by=u.id, status='Submitted')
    db.add(row); db.flush()
    audit(db,u,'partner_submit_material_return','stores_material_returns',row.id,project_id=pid)
    commit(db)
    return payload(row)
