"""Project-specific immutable milestone policy creation, approval and earned progress."""
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.models import User
from app.domains.planning_reporting.workspace_models import PlanningPublication
from app.domains.engineering_documents.models import Drawing,DrawingRevision
from app.domains.supply_chain.models import PurchaseOrder,PurchaseOrderLine,GoodsReceipt,GoodsReceiptLine
from app.domains.quality.models import MaterialInspection,MaterialDisposition
from .procurement_acceptance import allocation_errors,procurement_accepted_preview
from .reports_router import allowed
from .router import progress_scope
from .source_evidence import scoped
from .milestone_calculation import engineering_preview,procurement_preview
from .milestone_policy import ProgressMilestonePolicy,validate_policy,approved_result
router=APIRouter(prefix='/api/projects/{pid}/progress/milestone-policies',tags=['Progress Milestone Policies'])
class PolicyCreate(BaseModel):
    stage:str
    weights:dict[str,float]
    planning_publication_id:int=Field(gt=0)
    line_allocations:dict[str,float]|None=None
class PolicyApprove(BaseModel):
    approval_reference:str=Field(min_length=1,max_length=160)
def serial(p):
    return {'id':p.id,'stage':p.stage,'version':p.version,'status':p.status,'weights':p.milestone_weights,
            'planning_publication_id':p.planning_publication_id,'approval_reference':p.approval_reference,
            'created_by':p.created_by,'approved_by':p.approved_by,'approved_at':p.approved_at,'line_allocations':p.line_allocations}
@router.get('')
def list_policies(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    allowed(db,user,pid,'planning.view')
    return [serial(p) for p in db.query(ProgressMilestonePolicy).filter_by(project_id=pid,organization_id=user.organization_id).order_by(ProgressMilestonePolicy.stage,ProgressMilestonePolicy.version.desc()).limit(200)]
@router.post('',status_code=201)
def create_policy(pid:int,body:PolicyCreate,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    allowed(db,user,pid,'planning.manage')
    errors=validate_policy(body.stage,body.weights)
    if body.stage=='procurement':
        if not body.line_allocations:raise HTTPException(422,'Procurement line allocations are required')
        scope=progress_scope(db,user,pid)
        if not scope['all']:raise HTTPException(403,'Full project scope required for procurement allocation policy')
        orders=db.query(PurchaseOrder).filter_by(project_id=pid,organization_id=user.organization_id).all()
        lines=db.query(PurchaseOrderLine).filter(PurchaseOrderLine.purchase_order_id.in_([o.id for o in orders])).all() if orders else []
        errors+=allocation_errors(body.line_allocations,[l.id for l in lines])
    if errors:raise HTTPException(422,errors)
    pub=db.query(PlanningPublication).filter_by(id=body.planning_publication_id,project_id=pid,organization_id=user.organization_id,status='Approved',is_current=True).one_or_none()
    if pub is None:raise HTTPException(422,'Current approved Planning publication required')
    version=(db.query(func.max(ProgressMilestonePolicy.version)).filter_by(project_id=pid,stage=body.stage).scalar() or 0)+1
    p=ProgressMilestonePolicy(project_id=pid,organization_id=user.organization_id,stage=body.stage,version=version,status='Draft',milestone_weights=body.weights,line_allocations=body.line_allocations,planning_publication_id=pub.id,created_by=user.id)
    db.add(p);db.commit();db.refresh(p);return serial(p)
@router.post('/{policy_id}/approve')
def approve_policy(pid:int,policy_id:int,body:PolicyApprove,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    allowed(db,user,pid,'progress.policy.approve')
    p=db.query(ProgressMilestonePolicy).filter_by(id=policy_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if p is None:raise HTTPException(404,'Policy not found')
    if p.status!='Draft':raise HTTPException(409,'Only draft policies can be approved')
    if p.created_by==user.id:raise HTTPException(403,'Policy proposer cannot self-approve')
    predecessor=db.query(ProgressMilestonePolicy).filter_by(project_id=pid,organization_id=user.organization_id,stage=p.stage,status='Approved').with_for_update().first()
    if predecessor and p.version<=predecessor.version:
        raise HTTPException(409,'Replacement version must be newer than current approved policy')
    pub=db.query(PlanningPublication).filter_by(id=p.planning_publication_id,project_id=pid,organization_id=user.organization_id,status='Approved',is_current=True).one_or_none()
    if pub is None:raise HTTPException(409,'Approved Planning baseline has changed')
    errors=validate_policy(p.stage,p.milestone_weights)
    if p.stage=='procurement':
        scope=progress_scope(db,user,pid)
        if not scope['all']:raise HTTPException(403,'Full project scope required to approve procurement allocations')
        orders=db.query(PurchaseOrder).filter_by(project_id=pid,organization_id=user.organization_id).all()
        lines=db.query(PurchaseOrderLine).filter(PurchaseOrderLine.purchase_order_id.in_([o.id for o in orders])).all() if orders else []
        errors+=allocation_errors(p.line_allocations,[l.id for l in lines])
    if errors:raise HTTPException(422,errors)
    if predecessor:predecessor.status='Superseded'
    p.status='Approved';p.approved_by=user.id;p.approved_at=datetime.now(timezone.utc);p.approval_reference=body.approval_reference
    db.commit();return serial(p)
@router.get('/{stage}/earned')
def earned(pid:int,stage:str,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    scope=progress_scope(db,user,pid)
    if stage not in ('engineering','procurement'):raise HTTPException(404,'Unsupported stage')
    policy=db.query(ProgressMilestonePolicy).filter_by(project_id=pid,organization_id=user.organization_id,stage=stage,status='Approved').one_or_none()
    pub=db.query(PlanningPublication).filter_by(project_id=pid,organization_id=user.organization_id,status='Approved',is_current=True).first()
    if pub is None:return {'earned_percent':None,'policy_status':'UNAVAILABLE','errors':['Current approved Planning baseline unavailable']}
    weights=policy.milestone_weights if policy else ({'prepared':0,'released':100} if stage=='engineering' else {'ordered':0,'received':0,'accepted':100})
    if stage=='engineering':
        drawings=[d for d in db.query(Drawing).filter_by(organization_id=user.organization_id,project_id=pid).all() if scoped(d,scope)]
        ids=[d.id for d in drawings]
        revisions=db.query(DrawingRevision).filter(DrawingRevision.drawing_id.in_(ids)).all() if ids else []
        preview=engineering_preview(drawings,revisions,weights)
    else:
        orders=[o for o in db.query(PurchaseOrder).filter_by(organization_id=user.organization_id,project_id=pid).all() if scoped(o,scope)]
        ids=[o.id for o in orders]
        lines=db.query(PurchaseOrderLine).filter(PurchaseOrderLine.purchase_order_id.in_(ids)).all() if ids else []
        receipts=db.query(GoodsReceipt).filter_by(organization_id=user.organization_id,project_id=pid).filter(GoodsReceipt.purchase_order_id.in_(ids)).all() if ids else []
        rids=[r.id for r in receipts]
        rl=db.query(GoodsReceiptLine).filter(GoodsReceiptLine.goods_receipt_id.in_(rids)).all() if rids else []
        grn_ids=[r.id for r in receipts if r.status=='Posted']
        inspections=db.query(MaterialInspection).filter_by(project_id=pid,organization_id=user.organization_id).filter(MaterialInspection.goods_receipt_id.in_(grn_ids)).all() if grn_ids else []
        inspection_ids=[i.id for i in inspections]
        dispositions=db.query(MaterialDisposition).filter(MaterialDisposition.inspection_id.in_(inspection_ids)).all() if inspection_ids else []
        preview=procurement_accepted_preview(orders,lines,receipts,rl,inspections,dispositions,weights,policy.line_allocations if policy else None)
    return {'stage':stage,'planning_publication_id':pub.id,**approved_result(preview,policy,scope['all'],pub.id)}
