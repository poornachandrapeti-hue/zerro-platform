"""Permission-protected E/P milestone calculation previews, not approved progress."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.models import User
from app.domains.engineering_documents.models import Drawing, DrawingRevision
from app.domains.supply_chain.models import PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine
from .router import progress_scope
from .source_evidence import scoped
from .milestone_calculation import engineering_preview, procurement_preview

router = APIRouter(prefix='/api/projects/{pid}/progress/milestone-preview', tags=['Progress Milestone Preview'])
class WeightPolicy(BaseModel):
    weights: dict[str, float]

@router.post('/engineering')
def engineering(pid:int, body:WeightPolicy, user:User=Depends(authenticated), db:Session=Depends(get_db)):
    scope=progress_scope(db,user,pid)
    drawings=[d for d in db.query(Drawing).filter_by(organization_id=user.organization_id,project_id=pid).all() if scoped(d,scope)]
    ids=[d.id for d in drawings]
    revs=db.query(DrawingRevision).filter(DrawingRevision.drawing_id.in_(ids)).all() if ids else []
    result=engineering_preview(drawings,revs,body.weights)
    if not scope['all']:
        result['preview_percent']=None
        result['errors'].append('Full project earned percentage unavailable for restricted scope')
    return result

@router.post('/procurement')
def procurement(pid:int, body:WeightPolicy,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    scope=progress_scope(db,user,pid)
    orders=[o for o in db.query(PurchaseOrder).filter_by(organization_id=user.organization_id,project_id=pid).all() if scoped(o,scope)]
    ids=[o.id for o in orders]
    lines=db.query(PurchaseOrderLine).filter(PurchaseOrderLine.purchase_order_id.in_(ids)).all() if ids else []
    receipts=db.query(GoodsReceipt).filter_by(organization_id=user.organization_id,project_id=pid).filter(GoodsReceipt.purchase_order_id.in_(ids)).all() if ids else []
    rids=[r.id for r in receipts]
    receipt_lines=db.query(GoodsReceiptLine).filter(GoodsReceiptLine.goods_receipt_id.in_(rids)).all() if rids else []
    result=procurement_preview(orders,lines,receipts,receipt_lines,body.weights)
    if not scope['all']:
        result['preview_percent']=None
        result['errors'].append('Full project earned percentage unavailable for restricted scope')
    return result
