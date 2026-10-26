"""Phase 23 organization equipment registry and controlled reservation decisions."""
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from .workspace_router import access
from app.domains.identity_projects.models import Membership, Role
from .workspace_models import PlanningEquipmentAsset, PlanningResourceAllocation
from .equipment_rules import can_confirm
from .allocation_rules import conflict_ids

router=APIRouter(prefix='/api/projects/{pid}/planning',tags=['Equipment Management Foundation'])

class AssetInput(BaseModel):
    asset_code: str=Field(min_length=1,max_length=100)
    name: str=Field(min_length=1,max_length=200)
    equipment_type: str=Field(min_length=1,max_length=100)
    inspection_valid_through: date|None=None
    inspection_evidence_ref: str|None=Field(default=None,max_length=240)

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
