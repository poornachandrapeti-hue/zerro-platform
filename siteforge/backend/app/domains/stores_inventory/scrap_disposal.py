"""Phase 7 scrap classification, independent review and disposal custody evidence.

No operation in this router updates the stock ledger or certifies a write-off.
"""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.router import audit, commit
from .material_handovers import _scope
from .models import StoresReceiptLot, StoresScrapCase

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Scrap and Disposal'])
CLASSIFICATIONS = {'Damaged','Obsolete','Expired','Unserviceable','SurplusScrap'}

class ScrapProposalIn(BaseModel):
    reference: str = Field(min_length=2,max_length=120)
    receipt_lot_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0,decimal_places=3)
    classification: str
    reason: str = Field(min_length=5,max_length=4000)
    evidence: str = Field(min_length=3,max_length=4000)

class ScrapReviewIn(BaseModel):
    version: int = Field(ge=1)
    decision: str
    evidence: str = Field(min_length=3,max_length=4000)

class ScrapDisposalEvidenceIn(BaseModel):
    version: int = Field(ge=1)
    disposal_reference: str = Field(min_length=2,max_length=120)
    evidence: str = Field(min_length=3,max_length=4000)


def _find(db,pid,org,sid,lock=False):
    q=select(StoresScrapCase).where(StoresScrapCase.id==sid,
        StoresScrapCase.project_id==pid,StoresScrapCase.organization_id==org)
    return db.execute(q.with_for_update() if lock else q).scalar_one_or_none()


def _out(r):
    return {'id':r.id,'reference':r.reference,'receipt_lot_id':r.receipt_lot_id,
        'quantity':str(r.quantity),'classification':r.classification,'reason':r.reason,
        'status':r.status,'version':r.version,'created_by':r.created_by,
        'reviewed_by':r.reviewed_by,'review_evidence':r.review_evidence,
        'disposal_reference':r.disposal_reference,'disposal_evidence':r.disposal_evidence,
        'stock_written_off':False,'inventory_readiness':'Unverified',
        'legal_disposal_authorized':False}


def _require_classification(value):
    if value not in CLASSIFICATIONS:
        raise HTTPException(422,'Invalid scrap classification')


@router.post('/scrap-cases',status_code=201)
def create_scrap(pid:int,data:ScrapProposalIn,u:User=Depends(authenticated),db:Session=Depends(get_db)):
    _scope(db,u,pid,'procurement.stock.edit')
    _require_classification(data.classification)
    lot=db.execute(select(StoresReceiptLot).where(StoresReceiptLot.id==data.receipt_lot_id,
        StoresReceiptLot.project_id==pid,StoresReceiptLot.organization_id==u.organization_id).with_for_update()).scalar_one_or_none()
    if lot is None: raise HTTPException(404,'Receipt lot not found')
    if data.quantity>lot.quantity: raise HTTPException(409,'Proposed quantity exceeds original lot provenance')
    existing=db.execute(select(StoresScrapCase.id).where(StoresScrapCase.project_id==pid,
        StoresScrapCase.reference==data.reference)).scalar_one_or_none()
    if existing: raise HTTPException(409,'Scrap reference already exists')
    # A lot's original receipt amount is not its on-hand amount. Avoid any implication
    # of available scrap; reject competing active proposed disposals conservatively.
    active=db.execute(select(func.coalesce(func.sum(StoresScrapCase.quantity),0)).where(
        StoresScrapCase.project_id==pid,StoresScrapCase.receipt_lot_id==lot.id,
        StoresScrapCase.status.in_(('Proposed','ReviewedForDisposal','DisposalEvidenceRecorded')))).scalar_one()
    if Decimal(str(active))+data.quantity>lot.quantity:
        raise HTTPException(409,'Open scrap quantities exceed lot provenance')
    case=StoresScrapCase(organization_id=u.organization_id,project_id=pid,
        reference=data.reference,receipt_lot_id=lot.id,quantity=data.quantity,
        classification=data.classification,reason=data.reason,evidence=data.evidence,
        status='Proposed',created_by=u.id)
    db.add(case);db.flush()
    audit(db,u,'stores.scrap.propose','stores_scrap_case',case.id,
        {'receipt_lot_id':lot.id,'quantity':str(data.quantity),'classification':data.classification,
         'stock_written_off':False},project_id=pid)
    commit(db)
    return _out(case)

@router.get('/scrap-cases')
def list_scrap(pid:int,u:User=Depends(authenticated),db:Session=Depends(get_db)):
    _scope(db,u,pid,'procurement.stock.view')
    cases=db.execute(select(StoresScrapCase).where(StoresScrapCase.project_id==pid,
        StoresScrapCase.organization_id==u.organization_id).order_by(StoresScrapCase.id.desc()).limit(200)).scalars().all()
    return {'items':[_out(c) for c in cases],'scope':'latest 200',
        'stock_written_off':False,'inventory_readiness':'Unverified'}

@router.post('/scrap-cases/{sid}/review')
def review_scrap(pid:int,sid:int,data:ScrapReviewIn,u:User=Depends(authenticated),db:Session=Depends(get_db)):
    _scope(db,u,pid,'procurement.stock.edit')
    if data.decision not in ('Reject','ApproveCustodyReview'):
        raise HTTPException(422,'Stock write-off approval not supported')
    case=_find(db,pid,u.organization_id,sid,lock=True)
    if case is None: raise HTTPException(404,'Scrap case not found')
    if case.version!=data.version or case.status!='Proposed': raise HTTPException(409,'Stale or terminal scrap review')
    if case.created_by==u.id: raise HTTPException(403,'Independent scrap reviewer required')
    case.status='Rejected' if data.decision=='Reject' else 'ReviewedForDisposal'
    case.reviewed_by=u.id;case.review_evidence=data.evidence;case.version+=1
    audit(db,u,'stores.scrap.review','stores_scrap_case',case.id,
        {'decision':data.decision,'stock_written_off':False},project_id=pid)
    commit(db)
    return _out(case)

@router.post('/scrap-cases/{sid}/disposal-evidence')
def record_disposal(pid:int,sid:int,data:ScrapDisposalEvidenceIn,u:User=Depends(authenticated),db:Session=Depends(get_db)):
    _scope(db,u,pid,'procurement.stock.edit')
    case=_find(db,pid,u.organization_id,sid,lock=True)
    if case is None: raise HTTPException(404,'Scrap case not found')
    if case.version!=data.version or case.status!='ReviewedForDisposal':
        raise HTTPException(409,'Case not reviewed or version stale')
    if u.id in (case.created_by,case.reviewed_by):
        raise HTTPException(403,'Independent disposal evidence recorder required')
    case.status='DisposalEvidenceRecorded';case.disposal_reference=data.disposal_reference
    case.disposal_evidence=data.evidence;case.disposal_recorded_by=u.id;case.version+=1
    audit(db,u,'stores.scrap.disposal_evidence','stores_scrap_case',case.id,
        {'disposal_reference':data.disposal_reference,'stock_written_off':False},project_id=pid)
    commit(db)
    return _out(case)
