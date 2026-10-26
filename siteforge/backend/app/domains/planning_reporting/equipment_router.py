"""Phase 23 organization equipment registry and controlled reservation decisions."""
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from .workspace_router import access
from app.domains.identity_projects.models import Membership, Role
from .workspace_models import PlanningEquipmentAsset, PlanningResourceAllocation, PlanningEquipmentMasterChange
from .equipment_rules import can_confirm
from .allocation_rules import conflict_ids

router=APIRouter(prefix='/api/projects/{pid}/planning',tags=['Equipment Management Foundation'])

class AssetInput(BaseModel):
    asset_code: str=Field(min_length=1,max_length=100)
    name: str=Field(min_length=1,max_length=200)
    equipment_type: str=Field(min_length=1,max_length=100)
    inspection_valid_through: date|None=None
    inspection_evidence_ref: str|None=Field(default=None,max_length=240)

# E2 metadata is separate from asset identity and inspection approval.
# Existing register/booking consumers continue using the same asset ID.
class MasterUpdate(BaseModel):
    make: str|None=Field(default=None,max_length=120)
    model: str|None=Field(default=None,max_length=120)
    serial_number: str|None=Field(default=None,max_length=160)
    owner_company: str|None=Field(default=None,max_length=200)
    ownership_type: str=Field(pattern='^(Owned|Hired|Subcontractor)$')
    location: str|None=Field(default=None,max_length=200)
    operating_condition: str=Field(pattern='^(Unknown|Serviceable|Restricted|UnderRepair|Unserviceable)$')
    capacity: str|None=Field(default=None,max_length=160)
    operating_specs: dict|None=None
    mobilized_on: date|None=None
    demobilized_on: date|None=None
    hire_contract_ref: str|None=Field(default=None,max_length=160)
    maintenance_requirements: str|None=Field(default=None,max_length=2000)
    tracking_mode: str=Field(pattern='^(Individual|QuantityManaged)$')
    quantity: int=Field(ge=1,le=1000000)
    reason: str=Field(min_length=5,max_length=1000)

    @model_validator(mode='after')
    def check(self):
        if self.demobilized_on and not self.mobilized_on:
            raise ValueError('Mobilization date required before demobilization')
        if self.demobilized_on and self.demobilized_on < self.mobilized_on:
            raise ValueError('Demobilization cannot precede mobilization')
        if self.ownership_type=='Hired' and not self.hire_contract_ref:
            raise ValueError('Hired assets require a hire contract reference')
        if self.tracking_mode=='Individual' and self.quantity != 1:
            raise ValueError('Individual assets must have quantity 1')
        if self.tracking_mode=='QuantityManaged' and self.serial_number:
            raise ValueError('Quantity-managed tools cannot carry a single serial number')
        return self

MASTER_FIELDS=('make','model','serial_number','owner_company','ownership_type','location',
               'operating_condition','capacity','operating_specs','mobilized_on',
               'demobilized_on','hire_contract_ref','maintenance_requirements','tracking_mode','quantity')

def master_view(a):
    from .equipment_master_rules import master_view as as_master_view
    return as_master_view(a)

@router.get('/equipment-assets/{asset_id}/master')
def read_master(pid:int,asset_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    a=db.query(PlanningEquipmentAsset).filter_by(id=asset_id,organization_id=user.organization_id).one_or_none()
    if not a or (a.project_id is not None and a.project_id != pid):
        raise HTTPException(404,'Equipment not found')
    return master_view(a)

@router.put('/equipment-assets/{asset_id}/master')
def update_master(pid:int,asset_id:int,body:MasterUpdate,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    equipment_access(db,user,pid)
    a=db.query(PlanningEquipmentAsset).filter_by(id=asset_id,organization_id=user.organization_id).with_for_update().one_or_none()
    if not a:raise HTTPException(404,'Equipment not found')
    # Prevent unauthorized re-assignment of the same organization-wide asset to another project.
    if a.project_id is not None and a.project_id != pid:
        raise HTTPException(409,'Asset is assigned to a different project')
    from .equipment_master_rules import validate_master_transition
    before=master_view(a)
    if a.project_id is None:
        a.project_id=pid
    changes=body.model_dump(exclude={'reason'})
    validate_master_transition(a,changes,db,user.organization_id)
    if changes.get('operating_condition') == 'Serviceable':
        from .workspace_models import PlanningEquipmentMaintenanceOrder
        from .equipment_maintenance_rules import OPEN_STATES
        open_orders=db.query(PlanningEquipmentMaintenanceOrder).filter_by(
            organization_id=user.organization_id,asset_id=a.id).all()
        if any(o.status in OPEN_STATES for o in open_orders):
            raise HTTPException(409,'Open maintenance order prevents serviceable state')
    for key,val in changes.items():setattr(a,key,val)
    after=master_view(a)
    if before==after:raise HTTPException(409,'No master-data changes to record')
    db.add(PlanningEquipmentMasterChange(organization_id=user.organization_id,asset_id=a.id,
        project_id=pid,changed_by=user.id,action='Updated',reason=body.reason.strip(),
        before_state=before,after_state=after))
    db.commit()
    return after

class InspectionUpdate(BaseModel):
    valid_through:date
    evidence_ref:str=Field(min_length=3,max_length=240)

class InspectionDecision(BaseModel):
    decision:str
    note:str=Field(min_length=5,max_length=1000)

class Decision(BaseModel):
    reason:str=Field(min_length=5,max_length=1000)

def equipment_access(db,user,pid):
    access(db,user,pid,False)
    if user.organization_admin: return
    memberships=db.query(Membership).filter_by(project_id=pid,user_id=user.id,active=True).all()
    granted=set()
    for m in memberships:
        role=db.get(Role,m.role_id)
        if role: granted.update(role.permissions or [])
    if "equipment.manage" not in granted:
        raise HTTPException(403,"equipment.manage permission required")

def asset_dict(a):
    return {k:getattr(a,k) for k in ('id','asset_code','name','equipment_type','status','inspection_valid_through','inspection_evidence_ref','inspection_review_status','inspection_reviewed_by','inspection_reviewed_at','created_at')}

@router.get('/equipment-assets')
def list_assets(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    rows=db.query(PlanningEquipmentAsset).filter_by(organization_id=user.organization_id).order_by(PlanningEquipmentAsset.asset_code).all()
    return {'items':[asset_dict(a) for a in rows], 'basis':'Organization equipment register; inspection evidence requires external verification'}

@router.post('/equipment-assets',status_code=201)
def create_asset(pid:int,body:AssetInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    equipment_access(db,user,pid)
    existing=db.query(PlanningEquipmentAsset).filter_by(organization_id=user.organization_id,asset_code=body.asset_code.strip()).first()
    if existing:raise HTTPException(409,'Equipment code already registered')
    if bool(body.inspection_valid_through)!=bool(body.inspection_evidence_ref):raise HTTPException(422,'Inspection date and evidence reference must be supplied together')
    a=PlanningEquipmentAsset(organization_id=user.organization_id,created_by=user.id,asset_code=body.asset_code.strip(),name=body.name.strip(),equipment_type=body.equipment_type.strip(),inspection_valid_through=body.inspection_valid_through,inspection_evidence_ref=body.inspection_evidence_ref)
    db.add(a);db.commit();db.refresh(a);return asset_dict(a)

@router.post('/equipment-assets/{asset_id}/inspection')
def update_inspection(pid:int,asset_id:int,body:InspectionUpdate,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    equipment_access(db,user,pid)
    a=db.query(PlanningEquipmentAsset).filter_by(id=asset_id,organization_id=user.organization_id).one_or_none()
    if not a:raise HTTPException(404,'Equipment not found')
    if a.created_by==user.id:raise HTTPException(403,'Independent inspection evidence reviewer required')
    a.inspection_valid_through=body.valid_through;a.inspection_evidence_ref=body.evidence_ref
    a.inspection_review_status='Pending';a.inspection_reviewed_by=None;a.inspection_reviewed_at=None
    db.commit();return asset_dict(a)

@router.post('/equipment-assets/{asset_id}/inspection-review')
def review_inspection(pid:int,asset_id:int,body:InspectionDecision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    equipment_access(db,user,pid)
    if body.decision not in ('Verified','Rejected'):raise HTTPException(422,'Decision must be Verified or Rejected')
    a=db.query(PlanningEquipmentAsset).filter_by(id=asset_id,organization_id=user.organization_id).with_for_update().one_or_none()
    if not a:raise HTTPException(404,'Equipment not found')
    if not a.inspection_evidence_ref or not a.inspection_valid_through:raise HTTPException(409,'Inspection evidence missing')
    if a.created_by==user.id:raise HTTPException(403,'Asset creator cannot verify inspection')
    if a.inspection_review_status != 'Pending':raise HTTPException(409,'Inspection is not pending review')
    a.inspection_review_status=body.decision;a.inspection_reviewed_by=user.id;a.inspection_reviewed_at=datetime.now(timezone.utc)
    from .workspace_models import PlanningEquipmentInspectionDecision
    db.add(PlanningEquipmentInspectionDecision(asset_id=a.id,organization_id=user.organization_id,reviewer_id=user.id,decision=body.decision,note=body.note,evidence_ref=a.inspection_evidence_ref,valid_through=a.inspection_valid_through))
    db.commit();return asset_dict(a)

@router.post('/allocations/{allocation_id}/equipment-confirm')
def confirm_equipment(pid:int,allocation_id:int,body:Decision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    equipment_access(db,user,pid)
    a=db.query(PlanningResourceAllocation).filter_by(id=allocation_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if not a:raise HTTPException(404,'Allocation not found')
    if not a.resource_ref.startswith('equipment:') or not a.resource_ref.split(':',1)[1].isdigit():raise HTTPException(422,'Registered equipment reference required')
    asset=db.query(PlanningEquipmentAsset).filter_by(id=int(a.resource_ref.split(':')[1]),organization_id=user.organization_id).one_or_none()
    if not asset:raise HTTPException(422,'Equipment identity not found')
    if asset.inspection_review_status != 'Verified':raise HTTPException(409,'Independently reviewed inspection evidence required')
    if asset.inspection_reviewed_by==user.id:raise HTTPException(403,'Inspector reviewer cannot confirm own equipment reservation')
    if a.created_by==user.id or a.reviewed_by==user.id or asset.created_by==user.id:raise HTTPException(403,'Independent equipment confirmation required')
    ok,reason=can_confirm(asset,a)
    if not ok:raise HTTPException(409,reason)
    # Recheck organization-wide overlapping bookings while holding a PostgreSQL transaction lock.
    from sqlalchemy import text
    if db.bind and db.bind.dialect.name=='postgresql':
        import hashlib
        key=int.from_bytes(hashlib.sha256(f'{user.organization_id}:Equipment:{a.resource_ref}'.encode()).digest()[:8],'big',signed=True)
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':key})
    other=db.query(PlanningResourceAllocation).filter_by(organization_id=user.organization_id,resource_type='Equipment',resource_ref=a.resource_ref).all()
    if conflict_ids(a,[x for x in other if x.id!=a.id]):raise HTTPException(409,'Cross-project equipment booking overlap')
    a.status='EquipmentConfirmed';a.review_note=body.reason
    db.commit();return {'id':a.id,'status':a.status,'basis':'Internal equipment booking confirmation using recorded inspection evidence; external certificate validity not independently verified'}

@router.post('/allocations/{allocation_id}/equipment-release')
def release_equipment(pid:int,allocation_id:int,body:Decision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    equipment_access(db,user,pid)
    a=db.query(PlanningResourceAllocation).filter_by(id=allocation_id,project_id=pid,organization_id=user.organization_id,resource_type='Equipment').one_or_none()
    if not a:raise HTTPException(404,'Equipment allocation not found')
    if a.status!='EquipmentConfirmed':raise HTTPException(409,'Only confirmed bookings can be released')
    a.status='Released';a.review_note=body.reason
    db.commit();return {'id':a.id,'status':a.status}


# E3: separate append-only custody events; Planning remains authority for allocations.
class CustodyIssueInput(BaseModel):
    request_key: str=Field(min_length=8,max_length=100)
    quantity: int=Field(ge=1)
    custodian_user_id: int=Field(gt=0)
    location: str=Field(min_length=1,max_length=200)
    evidence_ref: str=Field(min_length=3,max_length=240)
    reason: str=Field(min_length=5,max_length=1000)
    allocation_id: int|None=None

class CustodyReturnInput(BaseModel):
    request_key: str=Field(min_length=8,max_length=100)
    issue_id: int=Field(gt=0)
    quantity: int=Field(ge=1)
    location: str=Field(min_length=1,max_length=200)
    evidence_ref: str=Field(min_length=3,max_length=240)
    reason: str=Field(min_length=5,max_length=1000)


def custody_view(row):
    return {key:getattr(row,key) for key in (
        'id','project_id','asset_id','allocation_id','parent_issue_id','action',
        'quantity','custodian_user_id','location','reason','evidence_ref',
        'request_key','recorded_by','recorded_at')}

@router.get('/equipment-assets/{asset_id}/custody')
def custody_history(pid:int,asset_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    from .workspace_models import PlanningEquipmentCustodyMovement
    asset=db.query(PlanningEquipmentAsset).filter_by(id=asset_id,organization_id=user.organization_id).one_or_none()
    if not asset or asset.project_id!=pid:raise HTTPException(404,'Project equipment not found')
    rows=db.query(PlanningEquipmentCustodyMovement).filter_by(organization_id=user.organization_id,project_id=pid,asset_id=asset_id).order_by(PlanningEquipmentCustodyMovement.id).all()
    from .equipment_custody_rules import available_quantity
    return {'items':[custody_view(r) for r in rows], 'available_quantity':available_quantity(asset.quantity,rows),
            'basis':'Equipment operational custody events; not Stores inventory or Finance posting'}

@router.post('/equipment-assets/{asset_id}/custody-issue',status_code=201)
def issue_custody(pid:int,asset_id:int,body:CustodyIssueInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    equipment_access(db,user,pid)
    from .workspace_models import PlanningEquipmentCustodyMovement
    from .equipment_custody_rules import validate_issue,available_quantity
    asset=db.query(PlanningEquipmentAsset).filter_by(id=asset_id,organization_id=user.organization_id).with_for_update().one_or_none()
    if not asset or (asset.project_id is not None and asset.project_id!=pid):raise HTTPException(404,'Project equipment not found')
    existing=db.query(PlanningEquipmentCustodyMovement).filter_by(organization_id=user.organization_id,request_key=body.request_key).one_or_none()
    if existing:raise HTTPException(409,'Custody request key already used')
    if asset.project_id is None:asset.project_id=pid
    allocation=None
    if body.allocation_id is not None:
        allocation=db.query(PlanningResourceAllocation).filter_by(id=body.allocation_id,organization_id=user.organization_id,project_id=pid).one_or_none()
        if allocation is None:raise HTTPException(409,'Planning allocation not found')
    validate_issue(asset,body.quantity,allocation)
    if allocation is not None and allocation.status!='EquipmentConfirmed':
        raise HTTPException(409,'Equipment allocation not confirmed')
    rows=db.query(PlanningEquipmentCustodyMovement).filter_by(organization_id=user.organization_id,asset_id=asset_id).all()
    if body.quantity>available_quantity(asset.quantity,rows):raise HTTPException(409,'Insufficient available tool quantity')
    if asset.tracking_mode=='Individual' and any(m.action=='Issue' for m in rows) and available_quantity(asset.quantity,rows)!=1:
        raise HTTPException(409,'Individual asset already issued')
    event=PlanningEquipmentCustodyMovement(organization_id=user.organization_id,project_id=pid,asset_id=asset_id,
        allocation_id=body.allocation_id,action='Issue',quantity=body.quantity,custodian_user_id=body.custodian_user_id,
        location=body.location.strip(),reason=body.reason.strip(),evidence_ref=body.evidence_ref.strip(),
        request_key=body.request_key.strip(),recorded_by=user.id)
    db.add(event)
    if asset.tracking_mode=='Individual':asset.custodian_user_id=body.custodian_user_id;asset.location=body.location.strip()
    db.commit();db.refresh(event)
    return custody_view(event)

@router.post('/equipment-assets/{asset_id}/custody-return',status_code=201)
def return_custody(pid:int,asset_id:int,body:CustodyReturnInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    equipment_access(db,user,pid)
    from .workspace_models import PlanningEquipmentCustodyMovement
    from .equipment_custody_rules import validate_return
    asset=db.query(PlanningEquipmentAsset).filter_by(id=asset_id,organization_id=user.organization_id,project_id=pid).with_for_update().one_or_none()
    if not asset:raise HTTPException(404,'Project equipment not found')
    existing=db.query(PlanningEquipmentCustodyMovement).filter_by(organization_id=user.organization_id,request_key=body.request_key).one_or_none()
    if existing:raise HTTPException(409,'Custody request key already used')
    issue=db.query(PlanningEquipmentCustodyMovement).filter_by(id=body.issue_id,organization_id=user.organization_id,project_id=pid,asset_id=asset_id,action='Issue').one_or_none()
    if not issue:raise HTTPException(404,'Original custody issue not found')
    rows=db.query(PlanningEquipmentCustodyMovement).filter_by(organization_id=user.organization_id,asset_id=asset_id,project_id=pid).all()
    outstanding=validate_return(issue,rows,body.quantity,asset_id,pid)
    event=PlanningEquipmentCustodyMovement(organization_id=user.organization_id,project_id=pid,asset_id=asset_id,
        allocation_id=issue.allocation_id,parent_issue_id=issue.id,action='Return',quantity=body.quantity,
        custodian_user_id=issue.custodian_user_id,location=body.location.strip(),reason=body.reason.strip(),
        evidence_ref=body.evidence_ref.strip(),request_key=body.request_key.strip(),recorded_by=user.id)
    db.add(event)
    if asset.tracking_mode=='Individual' and outstanding==0:
        asset.custodian_user_id=None;asset.location=body.location.strip()
    db.commit();db.refresh(event)
    return custody_view(event)


# E4 maintenance controls; same equipment identity and project RBAC as E2/E3.
class MaintenanceCreate(BaseModel):
    request_key: str = Field(min_length=8, max_length=100)
    kind: str = Field(pattern='^(Preventive|Breakdown)$')
    title: str = Field(min_length=3, max_length=200)
    reason: str = Field(min_length=5, max_length=1000)
    evidence_ref: str = Field(min_length=3, max_length=240)
    due_on: date | None = None

class MaintenanceTransition(BaseModel):
    status: str = Field(pattern='^(InRepair|RepairComplete|Released)$')
    evidence_ref: str = Field(min_length=3, max_length=240)

@router.post('/equipment-assets/{asset_id}/maintenance', status_code=201)
def create_maintenance(pid:int, asset_id:int, body:MaintenanceCreate, user:User=Depends(authenticated), db:Session=Depends(get_db)):
    equipment_access(db,user,pid)
    from .workspace_models import PlanningEquipmentMaintenanceOrder, PlanningEquipmentMaintenanceEvent
    from .equipment_maintenance_rules import start_work_order, OPEN_STATES
    asset=db.query(PlanningEquipmentAsset).filter_by(id=asset_id,organization_id=user.organization_id,project_id=pid).with_for_update().one_or_none()
    if asset is None:raise HTTPException(404,'Project equipment not found')
    duplicate=db.query(PlanningEquipmentMaintenanceOrder).filter_by(organization_id=user.organization_id,request_key=body.request_key).one_or_none()
    if duplicate:raise HTTPException(409,'Maintenance request key already used')
    active=db.query(PlanningEquipmentMaintenanceOrder).filter_by(organization_id=user.organization_id,asset_id=asset_id).all()
    if any(w.status in OPEN_STATES for w in active):raise HTTPException(409,'Equipment already has an open maintenance order')
    start_work_order(asset,body.kind,body.due_on)
    order=PlanningEquipmentMaintenanceOrder(organization_id=user.organization_id,project_id=pid,asset_id=asset_id,
        request_key=body.request_key,kind=body.kind,status='Reported',title=body.title.strip(),
        reported_reason=body.reason.strip(),due_on=body.due_on,created_by=user.id)
    db.add(order); db.flush()
    db.add(PlanningEquipmentMaintenanceEvent(organization_id=user.organization_id,order_id=order.id,
        old_status=None,new_status='Reported',evidence_ref=body.evidence_ref.strip(),actor_id=user.id))
    asset.operating_condition='UnderRepair'
    db.commit()
    return {'id':order.id,'status':'Reported','asset_id':asset_id,'equipment_condition':asset.operating_condition}

@router.post('/equipment-assets/{asset_id}/maintenance/{order_id}/transition')
def transition_maintenance(pid:int,asset_id:int,order_id:int,body:MaintenanceTransition,
                           user:User=Depends(authenticated),db:Session=Depends(get_db)):
    equipment_access(db,user,pid)
    from .workspace_models import PlanningEquipmentMaintenanceOrder, PlanningEquipmentMaintenanceEvent
    from .equipment_maintenance_rules import advance_work_order
    asset=db.query(PlanningEquipmentAsset).filter_by(id=asset_id,organization_id=user.organization_id,project_id=pid).with_for_update().one_or_none()
    if asset is None:raise HTTPException(404,'Project equipment not found')
    order=db.query(PlanningEquipmentMaintenanceOrder).filter_by(id=order_id,asset_id=asset_id,
        organization_id=user.organization_id,project_id=pid).with_for_update().one_or_none()
    if order is None:raise HTTPException(404,'Maintenance order not found')
    advance_work_order(order,body.status,user.id,body.evidence_ref)
    old=order.status;order.status=body.status
    if body.status=='RepairComplete':
        order.repair_completed_by=user.id
        order.repair_evidence_ref=body.evidence_ref.strip()
    if body.status=='Released':
        order.released_by=user.id;order.released_at=datetime.now(timezone.utc)
        # Release does not override HSE/inspection restrictions or independently certify inspections.
        asset.operating_condition='Restricted'
    db.add(PlanningEquipmentMaintenanceEvent(organization_id=user.organization_id,order_id=order.id,
        old_status=old,new_status=body.status,evidence_ref=body.evidence_ref.strip(),actor_id=user.id))
    db.commit()
    return {'id':order.id,'status':order.status,'asset_condition':asset.operating_condition,
            'note':'Release removes maintenance hold only; separate authorized HSE/inspection clearance required'}

@router.get('/equipment-assets/{asset_id}/maintenance')
def maintenance_history(pid:int,asset_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    from .workspace_models import PlanningEquipmentMaintenanceOrder
    asset=db.query(PlanningEquipmentAsset).filter_by(id=asset_id,organization_id=user.organization_id,project_id=pid).one_or_none()
    if asset is None:raise HTTPException(404,'Project equipment not found')
    orders=db.query(PlanningEquipmentMaintenanceOrder).filter_by(asset_id=asset_id,organization_id=user.organization_id,project_id=pid).order_by(PlanningEquipmentMaintenanceOrder.id).all()
    return {'items':[{'id':o.id,'kind':o.kind,'status':o.status,'due_on':o.due_on,'title':o.title,
                      'created_by':o.created_by,'released_by':o.released_by} for o in orders]}
