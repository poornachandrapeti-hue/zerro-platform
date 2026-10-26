"""Finance charge-document workflow; no inventory or journal mutations."""
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.supply_chain.models import GoodsReceiptLine, GoodsReceipt
from .models import FinanceLandedCostBatch as Batch, FinanceLandedCostReceiptLink as Link, FinanceInventoryCostingPolicy as Policy
from .router import guard

router = APIRouter(prefix='/api/projects/{pid}/financials/landed-cost',tags=['Financials'])
CATEGORIES={'FREIGHT','INSURANCE','HANDLING','TRANSPORT','OTHER'}

class NewBatch(BaseModel):
    document_ref:str=Field(min_length=3,max_length=100)
    source_document:str=Field(min_length=3,max_length=200)
    category:str
    currency:str=Field(pattern=r'^[A-Z]{3}$')
    amount:Decimal=Field(gt=0,max_digits=20,decimal_places=2)
    goods_receipt_line_ids:list[int]=Field(min_length=1,max_length=250)

class Decision(BaseModel):
    reason:str=Field(min_length=3,max_length=1000)

def receipt_in_scope(db,pid,org_id,line_id):
    # The GRN, not this Finance batch, owns the source material receipt.
    return db.query(GoodsReceiptLine.id).join(GoodsReceipt,GoodsReceiptLine.goods_receipt_id==GoodsReceipt.id).filter(
        GoodsReceiptLine.id==line_id,GoodsReceipt.project_id==pid,GoodsReceipt.organization_id==org_id).first() is not None

def serialize(db,b):
    ids=[r.goods_receipt_line_id for r in db.query(Link).filter_by(batch_id=b.id).order_by(Link.goods_receipt_line_id)]
    return {'id':b.id,'project_id':b.project_id,'document_ref':b.document_ref,'category':b.category,
        'currency':b.currency,'amount':str(b.amount),'source_document':b.source_document,
        'status':b.status,'goods_receipt_line_ids':ids,'created_by':b.created_by,
        'submitted_by':b.submitted_by,'approved_by':b.approved_by,
        'approved_at':b.approved_at.isoformat() if b.approved_at else None,
        'decision_reason':b.decision_reason,'stock_posted':False,'journal_posted':False,
        'movement_valuation_verified':False}

def load(db,pid,org_id,bid):
    b=db.query(Batch).filter_by(id=bid,project_id=pid,organization_id=org_id).with_for_update().one_or_none()
    if b is None:raise HTTPException(404,'Landed cost batch not found')
    return b

@router.get('')
def list_batches(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return [serialize(db,b) for b in db.query(Batch).filter_by(project_id=pid,organization_id=user.organization_id).order_by(Batch.id.desc()).all()]

@router.post('',status_code=201)
def create_batch(pid:int,body:NewBatch,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    if body.category not in CATEGORIES:raise HTTPException(422,'Unsupported landed charge category')
    line_ids=body.goods_receipt_line_ids
    if len(set(line_ids))!=len(line_ids) or any(i<=0 for i in line_ids):
        raise HTTPException(422,'Duplicate or invalid goods receipt lines')
    policy=db.query(Policy).filter_by(project_id=pid,organization_id=user.organization_id,status='Approved',currency=body.currency).order_by(Policy.revision.desc()).first()
    if policy is None:raise HTTPException(409,'Approved Finance costing policy in charge currency required')
    for i in line_ids:
        if not receipt_in_scope(db,pid,user.organization_id,i):
            raise HTTPException(422,f'Goods receipt line {i} does not belong to this project')
    b=Batch(organization_id=user.organization_id,project_id=pid,document_ref=body.document_ref.strip(),
        source_document=body.source_document.strip(),category=body.category,currency=body.currency,
        amount=body.amount,created_by=user.id,status='Draft',decision_reason='')
    db.add(b)
    try:
        db.flush()
        for i in line_ids:db.add(Link(batch_id=b.id,goods_receipt_line_id=i))
        db.commit();db.refresh(b)
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Duplicate charge document or receipt reference')
    return serialize(db,b)

@router.post('/{batch_id}/submit')
def submit(pid:int,batch_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    b=load(db,pid,user.organization_id,batch_id)
    if b.status!='Draft':raise HTTPException(409,'Only draft charge batches may be submitted')
    b.status='Pending Review';b.submitted_by=user.id
    db.commit();return serialize(db,b)

@router.post('/{batch_id}/approve')
def approve(pid:int,batch_id:int,body:Decision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    b=load(db,pid,user.organization_id,batch_id)
    if b.status!='Pending Review':raise HTTPException(409,'Batch is not pending Finance review')
    if user.id in {b.created_by,b.submitted_by}:raise HTTPException(403,'Independent Finance approval required')
    if not db.query(Link.id).filter_by(batch_id=b.id).first():raise HTTPException(409,'Missing receipt references')
    for r in db.query(Link).filter_by(batch_id=b.id):
        if not receipt_in_scope(db,pid,user.organization_id,r.goods_receipt_line_id):
            raise HTTPException(409,'Receipt ownership changed; approval blocked')
    b.status='Approved';b.approved_by=user.id;b.approved_at=datetime.now(timezone.utc);b.decision_reason=body.reason
    db.commit();return serialize(db,b)

@router.post('/{batch_id}/reject')
def reject(pid:int,batch_id:int,body:Decision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    b=load(db,pid,user.organization_id,batch_id)
    if b.status!='Pending Review':raise HTTPException(409,'Batch is not pending Finance review')
    if user.id in {b.created_by,b.submitted_by}:raise HTTPException(403,'Independent Finance review required')
    b.status='Rejected';b.approved_by=user.id;b.decision_reason=body.reason
    db.commit();return serialize(db,b)

@router.get('/receipt-cost-preview')
def receipt_cost_preview(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    """Read-only sourced preview, never an authorized movement valuation.

    Only approved landed-cost batches are considered. PO prices are *indicative*
    until Finance has verified supplier cost and invoice/adjustment provenance.
    """
    from collections import defaultdict
    from .landed_cost_allocation import (ReceiptCostBasis, ApprovedLandedCharge,
                                         preview_landed_cost_allocation)
    from app.domains.supply_chain.models import PurchaseOrderLine, PurchaseOrder

    guard(db,user,pid,'financials.view')
    org=user.organization_id
    batches=db.query(Batch).filter_by(project_id=pid,organization_id=org,status='Approved').order_by(Batch.id).all()
    if not batches:
        return {'status':'NO_APPROVED_CHARGES','read_only':True,'receipt_lines':[],
                'finance_source_verified':False,'movement_valuation_verified':False,'journal_posting_verified':False}
    groups=defaultdict(list)
    as_of=datetime.now(timezone.utc)
    for b in batches:
        if b.approved_by is None or b.approved_at is None or not b.source_document.strip():
            raise HTTPException(409,f'Batch {b.id} lacks approval evidence')
        if b.approved_by in {b.created_by,b.submitted_by}:
            raise HTTPException(409,f'Batch {b.id} lacks independent approval')
        if b.approved_at.replace(tzinfo=b.approved_at.tzinfo or timezone.utc)>as_of:
            raise HTTPException(409,f'Batch {b.id} has future approval')
        links=db.query(Link).filter_by(batch_id=b.id).all()
        if not links:raise HTTPException(409,f'Batch {b.id} has no receipt links')
        receipts=[]
        seen=set()
        for link in links:
            if link.goods_receipt_line_id in seen:
                raise HTTPException(409,'Duplicate receipt link')
            seen.add(link.goods_receipt_line_id)
            result=(db.query(GoodsReceiptLine,GoodsReceipt,PurchaseOrderLine,PurchaseOrder)
                .join(GoodsReceipt,GoodsReceiptLine.goods_receipt_id==GoodsReceipt.id)
                .join(PurchaseOrderLine,GoodsReceiptLine.purchase_order_line_id==PurchaseOrderLine.id)
                .join(PurchaseOrder,PurchaseOrderLine.purchase_order_id==PurchaseOrder.id)
                .filter(GoodsReceiptLine.id==link.goods_receipt_line_id,
                        GoodsReceipt.project_id==pid,GoodsReceipt.organization_id==org,
                        PurchaseOrder.id==GoodsReceipt.purchase_order_id,
                        PurchaseOrder.project_id==pid,PurchaseOrder.organization_id==org).one_or_none())
            if result is None:raise HTTPException(409,'Receipt or purchase order lineage missing or out of scope')
            line,grn,po_line,po=result
            if grn.status!='Posted' or Decimal(str(line.quantity))<=0 or Decimal(str(po_line.unit_price))<=0:
                raise HTTPException(409,'Receipt is not posted or purchase price/quantity is invalid')
            if po.currency!=b.currency:
                raise HTTPException(409,'PO and approved charge currencies differ')
            receipts.append(ReceiptCostBasis(line.id,org,pid,po_line.id,Decimal(str(line.quantity)),
                                              Decimal(str(po_line.unit_price)),b.currency))
        groups[b.currency].append((b,receipts))
    output=[]
    batch_evidence=[]
    line_allocations=[]
    for currency,entries in groups.items():
        # Each batch allocates *only* to the receipt lines explicitly named on that batch.
        per_line=defaultdict(lambda:{'purchase_cost':None,'landed_cost':Decimal('0.00'), 'references':[]})
        for b,receipts in entries:
            charge=ApprovedLandedCharge(str(b.id),org,pid,currency,Decimal(str(b.amount)),
                                         'APPROVED',b.source_document,b.approved_by,
                                         b.approved_at.replace(tzinfo=b.approved_at.tzinfo or timezone.utc),b.category)
            try:
                preview=preview_landed_cost_allocation(receipts=receipts,charges=[charge],
                    organization_id=org,project_id=pid,currency=currency,as_of=as_of)
            except (ValueError,ArithmeticError,ZeroDivisionError) as exc:
                raise HTTPException(409,f'Cannot allocate batch {b.id}: {exc}') from exc
            batch_evidence.append({'batch_id':b.id,'currency':currency,'amount':str(b.amount),'independently_approved':True})
            for r in preview['receipt_lines']:
                line_allocations.append({'batch_id':b.id,'receipt_line_id':r['receipt_line_id'],
                                         'amount':r['allocated_landed_charge'],'currency':currency})
                slot=per_line[r['receipt_line_id']]
                base=Decimal(r['purchase_cost'])
                if slot['purchase_cost'] is not None and slot['purchase_cost']!=base:
                    raise HTTPException(409,'Conflicting receipt purchase basis')
                slot['purchase_cost']=base
                slot['landed_cost']+=Decimal(r['allocated_landed_charge'])
                slot['references'].append(b.id)
        output.extend({'receipt_line_id':line_id,'currency':currency,
                      'po_purchase_cost_indicative':str(row['purchase_cost']),
                      'approved_landed_charge_total':str(row['landed_cost']),
                      'indicative_total':str(row['purchase_cost']+row['landed_cost']),
                      'batch_ids':row['references']}
                      for line_id,row in sorted(per_line.items()))
    # Preserve individual Finance batch references. A single synthetic batch ID
    # erases provenance and prevents detecting repeated/reconciled charges.
    from .phase9_landed_cost_reconciliation import reconcile_landed_cost_batches
    for currency in groups:
        evidence=[b for b in batch_evidence if b['currency']==currency]
        allocations=[a for a in line_allocations if a['currency']==currency]
        try:
            reconcile_landed_cost_batches(batches=evidence,allocations=allocations,
                receipt_line_ids=sorted({a['receipt_line_id'] for a in allocations}),currency=currency)
        except ValueError as exc:
            raise HTTPException(409, f'Landed batch reconciliation failed: {exc}') from exc
    return {'status':'INDICATIVE_UNPOSTED_PREVIEW','read_only':True,
            'batch_allocations':line_allocations,'receipt_lines':output,'finance_source_verified':False,
            'movement_valuation_verified':False,'journal_posting_verified':False,
            'warning':'PO unit prices are not Finance-verified invoice/landed receipt costs. No actual inventory valuation or journal posting has been established.'}
