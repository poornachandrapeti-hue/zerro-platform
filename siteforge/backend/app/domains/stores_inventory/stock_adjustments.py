"""Phase 7 stock adjustment requests: evidence and independent review only.

No book variance or stock posting is authorized here. A verified cycle count does
not imply a point-in-time lot-level book balance exists.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.router import audit, commit
from .material_handovers import _scope
from .cycle_counts import _find as find_count
from .models import StoresStockAdjustmentRequest

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Adjustment Reviews'])

class AdjustmentRequestIn(BaseModel):
    reference: str = Field(min_length=2, max_length=120)
    count_id: int = Field(gt=0)
    reason: str = Field(min_length=5, max_length=4000)
    evidence: str = Field(min_length=3, max_length=4000)

class AdjustmentReviewIn(BaseModel):
    version: int = Field(ge=1)
    decision: str
    evidence: str = Field(min_length=3, max_length=4000)


def adjustment_posting_readiness(status: str, count_status: str) -> dict:
    # No trustworthy lot-level book snapshot exists yet, regardless of count status.
    return {'authorized_for_posting': False, 'stock_adjustment_posted': False,
        'readiness': 'Blocked', 'blockers': [
            'Authoritative point-in-time lot-level book variance not available.',
            'GRN and transfer-derived lot coverage and concurrent movement cutoff not validated.',
            'Stock-adjustment ledger posting is not implemented or enabled.',
        ], 'count_status': count_status, 'review_status': status}


def serialize(a, count_status):
    return dict(id=a.id, reference=a.reference, count_id=a.count_id,
        status=a.status, version=a.version, reason=a.reason, evidence=a.evidence,
        created_by=a.created_by, reviewed_by=a.reviewed_by,
        review_evidence=a.review_evidence,
        **adjustment_posting_readiness(a.status, count_status))


def find_adjustment(db, pid, org, rid, *, lock=False):
    q=select(StoresStockAdjustmentRequest).where(
        StoresStockAdjustmentRequest.id==rid,
        StoresStockAdjustmentRequest.project_id==pid,
        StoresStockAdjustmentRequest.organization_id==org)
    return db.execute(q.with_for_update() if lock else q).scalar_one_or_none()

@router.post('/stock-adjustment-requests',status_code=201)
def create_adjustment(pid:int,data:AdjustmentRequestIn,u:User=Depends(authenticated),db:Session=Depends(get_db)):
    _scope(db,u,pid,'procurement.stock.edit')
    count=find_count(db,pid,u.organization_id,data.count_id,lock=True)
    if count is None: raise HTTPException(404,'Cycle count not found')
    if count.status!='Verified': raise HTTPException(409,'Independent cycle count verification required')
    exists=db.execute(select(StoresStockAdjustmentRequest.id).where(
        StoresStockAdjustmentRequest.project_id==pid,
        StoresStockAdjustmentRequest.reference==data.reference)).scalar_one_or_none()
    if exists: raise HTTPException(409,'Adjustment reference already exists')
    a=StoresStockAdjustmentRequest(organization_id=u.organization_id,project_id=pid,
        count_id=count.id,reference=data.reference,reason=data.reason,evidence=data.evidence,
        status='PendingReconciliation',created_by=u.id)
    db.add(a);db.flush()
    audit(db,u,'stores.adjustment.request.create','stores_stock_adjustment_request',a.id,
        {'count_id':count.id,'posting_ready':False},project_id=pid)
    commit(db)
    return serialize(a,count.status)

@router.get('/stock-adjustment-requests')
def list_adjustments(pid:int,u:User=Depends(authenticated),db:Session=Depends(get_db)):
    _scope(db,u,pid,'procurement.stock.view')
    rows=db.execute(select(StoresStockAdjustmentRequest).where(
        StoresStockAdjustmentRequest.project_id==pid,
        StoresStockAdjustmentRequest.organization_id==u.organization_id
    ).order_by(StoresStockAdjustmentRequest.id.desc()).limit(200)).scalars().all()
    return {'items':[{'id':a.id,'reference':a.reference,'count_id':a.count_id,
        'status':a.status,'version':a.version,'authorized_for_posting':False} for a in rows],
        'scope':'latest 200','stock_adjustment_posted':False}

@router.get('/stock-adjustment-requests/{rid}')
def adjustment_details(pid:int,rid:int,u:User=Depends(authenticated),db:Session=Depends(get_db)):
    _scope(db,u,pid,'procurement.stock.view')
    a=find_adjustment(db,pid,u.organization_id,rid)
    if a is None: raise HTTPException(404,'Adjustment request not found')
    count=find_count(db,pid,u.organization_id,a.count_id)
    return serialize(a,count.status if count else 'Missing')

@router.post('/stock-adjustment-requests/{rid}/review')
def review_adjustment(pid:int,rid:int,data:AdjustmentReviewIn,u:User=Depends(authenticated),db:Session=Depends(get_db)):
    _scope(db,u,pid,'procurement.stock.edit')
    if data.decision not in ('Reject','RequestRecount','RecordReview'):
        raise HTTPException(422,'Approval is blocked until authoritative variance is established')
    a=find_adjustment(db,pid,u.organization_id,rid,lock=True)
    if a is None: raise HTTPException(404,'Adjustment request not found')
    if a.version!=data.version or a.status not in ('PendingReconciliation','ReviewedBlocked'):
        raise HTTPException(409,'Stale adjustment review or terminal status')
    count=find_count(db,pid,u.organization_id,a.count_id,lock=True)
    if count is None: raise HTTPException(409,'Referenced cycle count missing')
    if u.id in (a.created_by,count.created_by,count.submitted_by,count.verified_by):
        raise HTTPException(403,'Independent adjustment reviewer required')
    a.status={'Reject':'Rejected','RequestRecount':'RecountRequested',
              'RecordReview':'ReviewedBlocked'}[data.decision]
    a.reviewed_by=u.id;a.review_evidence=data.evidence;a.version+=1
    audit(db,u,'stores.adjustment.request.review','stores_stock_adjustment_request',a.id,
          {'decision':data.decision,'posting_ready':False},project_id=pid)
    commit(db)
    return serialize(a,count.status)
