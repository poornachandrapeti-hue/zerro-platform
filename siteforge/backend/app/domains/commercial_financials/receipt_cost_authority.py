"""Finance-owned receipt-specific invoice allocation, never a stock/journal posting."""
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.supply_chain.models import GoodsReceipt, GoodsReceiptLine, PurchaseOrder, PurchaseOrderLine, VendorInvoice, VendorInvoiceLine
from .models import FinanceReceiptCostAllocation as Allocation, FinanceSupplierInvoicePosting as Posting, FinanceInventoryCostingPolicy as Policy
from .router import guard

router=APIRouter(prefix='/api/projects/{pid}/financials/receipt-cost-allocations',tags=['Financials'])

class CreateAllocation(BaseModel):
    goods_receipt_line_id:int=Field(gt=0)
    vendor_invoice_line_id:int=Field(gt=0)
    quantity:Decimal=Field(gt=0,max_digits=20,decimal_places=6)
    source_reference:str=Field(min_length=3,max_length=160)

class Decision(BaseModel):
    reason:str=Field(min_length=3,max_length=1000)

def validate_allocation(a:Allocation, db:Session, pid:int, org:int):
    """Recheck Finance verification, receipt lineage, and cumulative quantities on submit/approve."""
    row=(db.query(GoodsReceiptLine,GoodsReceipt,PurchaseOrderLine,PurchaseOrder,VendorInvoiceLine,VendorInvoice,Posting)
        .join(GoodsReceipt,GoodsReceiptLine.goods_receipt_id==GoodsReceipt.id)
        .join(PurchaseOrderLine,GoodsReceiptLine.purchase_order_line_id==PurchaseOrderLine.id)
        .join(PurchaseOrder,PurchaseOrderLine.purchase_order_id==PurchaseOrder.id)
        .join(VendorInvoiceLine,VendorInvoiceLine.id==a.vendor_invoice_line_id)
        .join(VendorInvoice,VendorInvoiceLine.invoice_id==VendorInvoice.id)
        .join(Posting,Posting.vendor_invoice_id==VendorInvoice.id)
        .filter(GoodsReceiptLine.id==a.goods_receipt_line_id,GoodsReceipt.project_id==pid,GoodsReceipt.organization_id==org,
                PurchaseOrder.id==GoodsReceipt.purchase_order_id,PurchaseOrder.project_id==pid,PurchaseOrder.organization_id==org,
                VendorInvoice.project_id==pid,VendorInvoice.organization_id==org,
                VendorInvoice.purchase_order_id==PurchaseOrder.id,VendorInvoiceLine.purchase_order_line_id==PurchaseOrderLine.id,
                Posting.organization_id==org,Posting.project_id==pid,Posting.purchase_order_id==PurchaseOrder.id).one_or_none())
    if not row:raise HTTPException(409,'Receipt, invoice and Finance verification lineage must match')
    grl,gr,pol,po,invline,inv,post=row
    if gr.status!='Posted' or post.posted_at is None or post.posted_by is None:
        raise HTTPException(409,'Posted receipt and verified Finance invoice required')
    policy=db.query(Policy).filter_by(project_id=pid,organization_id=org,status='Approved',currency=post.currency).first()
    if policy is None:raise HTTPException(409,'Approved Finance costing policy required')
    unit=Decimal(str(invline.billed_unit_price))
    qty=Decimal(str(a.quantity))
    if not unit.is_finite() or unit<=0 or qty<=0 or not qty.is_finite():raise HTTPException(409,'Invalid invoice cost or allocated quantity')
    if str(post.currency)!=str(po.currency):raise HTTPException(409,'Invoice and PO currencies mismatch')
    if Decimal(str(a.unit_cost))!=unit or a.currency!=post.currency:raise HTTPException(409,'Finance cost evidence has changed')
    # Lock a shared receipt/invoice parent to serialize allocations competing for the same source line.
    db.query(VendorInvoiceLine.id).filter(VendorInvoiceLine.id==invline.id).with_for_update().first()
    db.query(GoodsReceiptLine.id).filter(GoodsReceiptLine.id==grl.id).with_for_update().first()
    rows=db.query(Allocation).filter(Allocation.project_id==pid,Allocation.organization_id==org,
                                    Allocation.status.in_(['Draft','Pending Review','Approved'])).all()
    receipt_total=sum((Decimal(str(x.quantity)) for x in rows if x.goods_receipt_line_id==grl.id),Decimal('0'))
    invoice_total=sum((Decimal(str(x.quantity)) for x in rows if x.vendor_invoice_line_id==invline.id),Decimal('0'))
    if receipt_total>Decimal(str(grl.quantity)) or invoice_total>Decimal(str(invline.quantity)):
        raise HTTPException(409,'Receipt or verified invoice allocation quantity exceeded')

def serialize(a):
    return {'id':a.id,'project_id':a.project_id,'goods_receipt_line_id':a.goods_receipt_line_id,
        'vendor_invoice_line_id':a.vendor_invoice_line_id,'quantity':str(a.quantity),'currency':a.currency,
        'unit_cost':str(a.unit_cost),'status':a.status,'source_reference':a.source_reference,
        'created_by':a.created_by,'submitted_by':a.submitted_by,'approved_by':a.approved_by,
        'approved_at':a.approved_at.isoformat() if a.approved_at else None,
        'receipt_cost_evidence_approved':a.status=='Approved',
        'movement_valuation_verified':False,'journal_posting_verified':False}

def get_locked(db,pid,org,aid):
    a=db.query(Allocation).filter_by(id=aid,project_id=pid,organization_id=org).with_for_update().one_or_none()
    if a is None:raise HTTPException(404,'Allocation not found')
    return a

@router.get('')
def list_allocations(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return [serialize(a) for a in db.query(Allocation).filter_by(project_id=pid,organization_id=user.organization_id).order_by(Allocation.id.desc()).all()]

@router.post('',status_code=201)
def create(pid:int,body:CreateAllocation,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    row=(db.query(VendorInvoiceLine,VendorInvoice,Posting)
         .join(VendorInvoice,VendorInvoiceLine.invoice_id==VendorInvoice.id)
         .join(Posting,Posting.vendor_invoice_id==VendorInvoice.id)
         .filter(VendorInvoiceLine.id==body.vendor_invoice_line_id,VendorInvoice.project_id==pid,VendorInvoice.organization_id==user.organization_id,
                 Posting.project_id==pid,Posting.organization_id==user.organization_id).one_or_none())
    if row is None:raise HTTPException(409,'Verified Finance invoice line required')
    line,inv,post=row
    a=Allocation(organization_id=user.organization_id,project_id=pid,goods_receipt_line_id=body.goods_receipt_line_id,
        vendor_invoice_line_id=body.vendor_invoice_line_id,quantity=body.quantity,currency=post.currency,
        unit_cost=line.billed_unit_price,source_reference=body.source_reference.strip(),status='Draft',created_by=user.id,decision_reason='')
    db.add(a)
    try:
        db.flush()
        validate_allocation(a,db,pid,user.organization_id)
        db.commit();db.refresh(a)
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Duplicate receipt/invoice allocation')
    return serialize(a)

@router.post('/{allocation_id}/submit')
def submit(pid:int,allocation_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    a=get_locked(db,pid,user.organization_id,allocation_id)
    if a.status!='Draft':raise HTTPException(409,'Only draft allocations may be submitted')
    validate_allocation(a,db,pid,user.organization_id)
    a.status='Pending Review';a.submitted_by=user.id;db.commit();return serialize(a)

@router.post('/{allocation_id}/approve')
def approve(pid:int,allocation_id:int,body:Decision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    a=get_locked(db,pid,user.organization_id,allocation_id)
    if a.status!='Pending Review':raise HTTPException(409,'Allocation not pending review')
    if user.id in {a.created_by,a.submitted_by}:raise HTTPException(403,'Independent Finance approval required')
    validate_allocation(a,db,pid,user.organization_id)
    a.status='Approved';a.approved_by=user.id;a.approved_at=datetime.now(timezone.utc);a.decision_reason=body.reason
    db.commit();return serialize(a)

@router.post('/{allocation_id}/reject')
def reject(pid:int,allocation_id:int,body:Decision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    a=get_locked(db,pid,user.organization_id,allocation_id)
    if a.status!='Pending Review':raise HTTPException(409,'Allocation not pending review')
    if user.id in {a.created_by,a.submitted_by}:raise HTTPException(403,'Independent Finance review required')
    a.status='Rejected';a.approved_by=user.id;a.decision_reason=body.reason;db.commit();return serialize(a)

@router.get('/consolidated-receipt-preview')
def consolidated_receipt_preview(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    """Finance-owned, read-only receipt cost preview; never certifies journals or movements."""
    from .verified_receipt_layers import consolidate_receipt_layers
    from .landed_cost_authority import receipt_cost_preview as landed_preview
    from app.domains.supply_chain.models import GoodsReceiptLine, GoodsReceipt, PurchaseOrderLine, PurchaseOrder
    org=user.organization_id
    guard(db,user,pid,'financials.view')
    approved=(db.query(Allocation).filter_by(project_id=pid,organization_id=org,status='Approved')
              .order_by(Allocation.goods_receipt_line_id,Allocation.id).all())
    if not approved:
        return {'status':'NO_APPROVED_INVOICE_ALLOCATIONS','read_only':True,'receipt_lines':[],
                'movement_valuation_verified':False,'journal_posting_verified':False}
    receipt_ids=sorted({a.goods_receipt_line_id for a in approved})
    rows=(db.query(GoodsReceiptLine,GoodsReceipt,PurchaseOrderLine,PurchaseOrder)
          .join(GoodsReceipt,GoodsReceiptLine.goods_receipt_id==GoodsReceipt.id)
          .join(PurchaseOrderLine,GoodsReceiptLine.purchase_order_line_id==PurchaseOrderLine.id)
          .join(PurchaseOrder,PurchaseOrderLine.purchase_order_id==PurchaseOrder.id)
          .filter(GoodsReceiptLine.id.in_(receipt_ids),GoodsReceipt.organization_id==org,
                  GoodsReceipt.project_id==pid,PurchaseOrder.organization_id==org,
                  PurchaseOrder.project_id==pid,GoodsReceipt.purchase_order_id==PurchaseOrder.id).all())
    if len(rows)!=len(receipt_ids):raise HTTPException(409,'Missing or out-of-scope receipt lineage')
    receipts=[]
    for line,gr,po_line,po in rows:
        if gr.status!='Posted':raise HTTPException(409,'Receipt is not posted')
        receipts.append({'id':line.id,'quantity':line.quantity,'currency':po.currency})
    invoice=[]
    for a in approved:
        if not a.approved_at or a.approved_by in {None,a.created_by,a.submitted_by}:
            raise HTTPException(409,'Receipt allocation approval evidence is incomplete')
        invoice.append({'receipt_line_id':a.goods_receipt_line_id,'allocation_id':a.id,
                        'quantity':a.quantity,'unit_cost':a.unit_cost,'currency':a.currency,
                        'independently_approved':True})
    preview=landed_preview(pid=pid,user=user,db=db)
    # Carry actual approved batch IDs, not a synthetic ID 0, so downstream
    # reconciliation can detect duplicated or missing Finance charge provenance.
    landed=[]
    for allocation in preview.get('batch_allocations',[]):
        if allocation['receipt_line_id'] in receipt_ids:
            landed.append({'receipt_line_id':allocation['receipt_line_id'],
                           'batch_id':allocation['batch_id'],
                           'amount':allocation['amount'],
                           'currency':allocation['currency'],
                           'independently_approved':True})
    try:result=consolidate_receipt_layers(receipts=receipts,invoice_allocations=invoice,landed_allocations=landed)
    except (ValueError,ArithmeticError,TypeError) as exc:
        raise HTTPException(409,f'Receipt cost evidence inconsistent: {exc}') from exc
    return {'status':'UNPOSTED_FINANCE_COST_PREVIEW','read_only':True,'receipt_lines':result,
            'movement_valuation_verified':False,'journal_posting_verified':False,
            'warning':'Approved receipt costs are a preview only. Remaining receipt layers, FIFO/weighted-average stock valuation and accounting journals are unverified.'}
