"""Read-only Procurement mirror and separate Finance posting (Phase 31.2).

Procurement retains ownership of PO and invoice records. A Recorded invoice
is not cost until an authorized Finance user explicitly verifies/posts it.
"""
from decimal import Decimal
from datetime import datetime, timezone
from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.domains.supply_chain.models import PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine, VendorInvoice, VendorInvoiceLine
from .models import FinanceCostCode, FinanceProcurementAllocation, FinanceSupplierInvoicePosting

COMMITTED_STATES={'Issued','Acknowledged','Partially Received','Received','Closed'}
ZERO=Decimal('0.00')

class AllocationIn(BaseModel):
    cost_code_id:int

class PostingIn(BaseModel):
    verification_note:str=Field(min_length=8,max_length=1000)

def amount_lines(lines,quantity,rate):
    return sum((Decimal(str(getattr(x,quantity)))*Decimal(str(getattr(x,rate))) for x in lines),ZERO)

def order_value(db:Session,po:PurchaseOrder):
    return amount_lines(db.query(PurchaseOrderLine).filter_by(purchase_order_id=po.id).all(),'quantity','unit_price')

def invoice_value(db:Session,invoice:VendorInvoice):
    return amount_lines(db.query(VendorInvoiceLine).filter_by(invoice_id=invoice.id).all(),'quantity','billed_unit_price')

def validate_line_entitlement(ordered, lines, received, previously_billed):
    """Testable quantity/rate guard shared by Finance-posting reconciliation."""
    if not lines:
        raise HTTPException(409, 'Invoice has no lines to reconcile')
    claimed = {line_id: ZERO for line_id in ordered}
    for line in lines:
        po_line = ordered.get(line.purchase_order_line_id)
        if not po_line:
            raise HTTPException(409, 'Invoice line references a different or missing purchase order line')
        quantity = Decimal(str(line.quantity))
        rate = Decimal(str(line.billed_unit_price))
        if quantity <= ZERO or rate < ZERO:
            raise HTTPException(409, 'Invoice quantities must be positive and rates nonnegative')
        if rate != Decimal(str(po_line.unit_price)):
            raise HTTPException(409, 'Invoice rate differs from approved PO rate; amendment or variance review required')
        claimed[line.purchase_order_line_id] += quantity
    for line_id, quantity in claimed.items():
        if quantity + previously_billed.get(line_id, ZERO) > Decimal(str(ordered[line_id].quantity)):
            raise HTTPException(409, 'Cumulative invoiced quantity exceeds approved PO quantity')
        if quantity + previously_billed.get(line_id, ZERO) > received.get(line_id, ZERO):
            raise HTTPException(409, 'Cumulative invoiced quantity exceeds posted goods receipts; review required')
    return len(lines)


def receipt_match(db:Session, po:PurchaseOrder, invoice:VendorInvoice):
    """Cumulative three-way PO/posted receipt/invoice matching; fails closed."""
    ordered = {line.id: line for line in db.query(PurchaseOrderLine).filter_by(purchase_order_id=po.id).all()}
    lines = db.query(VendorInvoiceLine).filter_by(invoice_id=invoice.id).all()
    receipts = db.query(GoodsReceipt).filter_by(project_id=po.project_id, organization_id=po.organization_id, purchase_order_id=po.id, status='Posted').all()
    receipt_ids = [receipt.id for receipt in receipts]
    received = {line_id: ZERO for line_id in ordered}
    if receipt_ids:
        for line in db.query(GoodsReceiptLine).filter(GoodsReceiptLine.goods_receipt_id.in_(receipt_ids)).all():
            if line.purchase_order_line_id in received:
                received[line.purchase_order_line_id] += Decimal(str(line.quantity))
    posted_ids = [row.vendor_invoice_id for row in db.query(FinanceSupplierInvoicePosting).filter_by(project_id=po.project_id, organization_id=po.organization_id, purchase_order_id=po.id).all()]
    previously_billed = {line_id: ZERO for line_id in ordered}
    if posted_ids:
        for line in db.query(VendorInvoiceLine).filter(VendorInvoiceLine.invoice_id.in_(posted_ids)).all():
            if line.purchase_order_line_id in previously_billed:
                previously_billed[line.purchase_order_line_id] += Decimal(str(line.quantity))
    matched_count = validate_line_entitlement(ordered, lines, received, previously_billed)
    return {'matched_line_count': matched_count, 'goods_receipt_ids': receipt_ids}

def overview(db:Session,pid:int,org_id:int):
    allocations={a.purchase_order_id:a for a in db.query(FinanceProcurementAllocation).filter_by(project_id=pid,organization_id=org_id).all()}
    posts={p.vendor_invoice_id:p for p in db.query(FinanceSupplierInvoicePosting).filter_by(project_id=pid,organization_id=org_id).all()}
    orders=db.query(PurchaseOrder).filter_by(project_id=pid,organization_id=org_id).order_by(PurchaseOrder.id).all()
    invoices=db.query(VendorInvoice).filter_by(project_id=pid,organization_id=org_id).order_by(VendorInvoice.id).all()
    by_po={}
    for inv in invoices:by_po.setdefault(inv.purchase_order_id,[]).append(inv)
    result=[]
    for po in orders:
        allocation=allocations.get(po.id)
        posted=sum((p.amount for inv in by_po.get(po.id,[]) if (p:=posts.get(inv.id))),ZERO)
        committed=order_value(db,po) if po.status in COMMITTED_STATES else ZERO
        if committed and (not po.currency or len(po.currency)!=3):
            # Inconsistent currency must not be mixed into financial totals.
            raise HTTPException(409,f'PO {po.number} has no valid currency')
        if posted and committed==ZERO:
            # Cancelled/superseded commitments must not hide posted costs.
            pass
        result.append({'purchase_order_id':po.id,'purchase_order_number':po.number,'status':po.status,'currency':po.currency,'cost_code_id':allocation.cost_code_id if allocation else None,'commitment_amount':str(committed),'recognized_actual_cost':str(posted),'open_commitment':str(max(committed-posted,ZERO)) if allocation else None,'allocation_status':'Mapped' if allocation else 'Unmapped'})
    invoice_result=[]
    for inv in invoices:
        posting=posts.get(inv.id)
        invoice_result.append({'vendor_invoice_id':inv.id,'invoice_number':inv.number,'purchase_order_id':inv.purchase_order_id,'procurement_status':inv.status,'claimed_amount':str(invoice_value(db,inv)),'finance_status':'Posted' if posting else 'Not Posted','posted_amount':str(posting.amount) if posting else None,'posted_at':posting.posted_at.isoformat() if posting else None})
    totals={}
    for po in result:
        if po['allocation_status']!='Mapped':continue
        cc=po['currency'];v=totals.setdefault(cc,{'approved_commitments':ZERO,'recognized_actual_cost':ZERO,'open_commitments':ZERO})
        v['approved_commitments']+=Decimal(po['commitment_amount']);v['recognized_actual_cost']+=Decimal(po['recognized_actual_cost']);v['open_commitments']+=Decimal(po['open_commitment'])
    return {'project_id':pid,'source':'Procurement purchase_orders/vendor_invoices; Finance postings','read_only':True,'cost_recognition_policy':'Only Finance-posted Recorded supplier invoices recognize cost','by_currency':{cc:{k:str(v) for k,v in row.items()} for cc,row in totals.items()},'purchase_orders':result,'supplier_invoices':invoice_result,'unmapped_purchase_order_count':sum(x['allocation_status']=='Unmapped' for x in result)}

def assign(db:Session,pid:int,org_id:int,actor:int,po_id:int,cost_code_id:int):
    po=db.query(PurchaseOrder).filter_by(id=po_id,project_id=pid,organization_id=org_id).one_or_none()
    cc=db.query(FinanceCostCode).filter_by(id=cost_code_id,project_id=pid,organization_id=org_id).one_or_none()
    if not po or not cc:raise HTTPException(404,'Purchase order or cost code not found in project')
    if db.query(FinanceProcurementAllocation).filter_by(project_id=pid,purchase_order_id=po_id).first():raise HTTPException(409,'PO already cost-coded; changes require a controlled adjustment')
    row=FinanceProcurementAllocation(project_id=pid,organization_id=org_id,purchase_order_id=po_id,cost_code_id=cost_code_id,assigned_by=actor)
    db.add(row)
    try:db.commit();db.refresh(row)
    except IntegrityError:db.rollback();raise HTTPException(409,'Duplicate allocation')
    return {'purchase_order_id':po_id,'cost_code_id':cost_code_id,'allocated_at':row.assigned_at.isoformat()}

def post(db:Session,pid:int,org_id:int,actor:int,invoice_id:int,note:str):
    invoice=db.query(VendorInvoice).filter_by(id=invoice_id,project_id=pid,organization_id=org_id).one_or_none()
    if not invoice:raise HTTPException(404,'Supplier invoice not found')
    if invoice.status!='Recorded':raise HTTPException(409,'Only Procurement Recorded invoices may be posted')
    if db.query(FinanceSupplierInvoicePosting).filter_by(project_id=pid,vendor_invoice_id=invoice_id).first():raise HTTPException(409,'Invoice already posted')
    po=db.query(PurchaseOrder).filter_by(id=invoice.purchase_order_id,project_id=pid,organization_id=org_id).one_or_none()
    allocation=db.query(FinanceProcurementAllocation).filter_by(project_id=pid,purchase_order_id=invoice.purchase_order_id).one_or_none()
    if not po or not allocation:raise HTTPException(409,'Purchase order requires cost-code mapping before posting')
    if po.status not in COMMITTED_STATES:raise HTTPException(409,'Purchase order is not in a recognized commitment state')
    if not po.currency or len(po.currency)!=3:raise HTTPException(409,'PO currency missing')
    match=receipt_match(db,po,invoice)
    amount=invoice_value(db,invoice)
    if amount<=0:raise HTTPException(409,'Invoice has no positive line amount')
    # Do not silently post supplier invoice exceeding the remaining PO entitlement.
    already=sum((p.amount for p in db.query(FinanceSupplierInvoicePosting).filter_by(project_id=pid,purchase_order_id=po.id).all()),ZERO)
    if already+amount>order_value(db,po):raise HTTPException(409,'Invoice exceeds remaining PO value; review PO amendment first')
    row=FinanceSupplierInvoicePosting(project_id=pid,organization_id=org_id,vendor_invoice_id=invoice.id,purchase_order_id=po.id,cost_code_id=allocation.cost_code_id,currency=po.currency,amount=amount,posted_by=actor,verification_note=note)
    db.add(row)
    try:db.commit();db.refresh(row)
    except IntegrityError:db.rollback();raise HTTPException(409,'Invoice already posted')
    return {'vendor_invoice_id':invoice.id,'status':'Posted','amount':str(row.amount),'currency':row.currency,'cost_code_id':row.cost_code_id,'posted_at':row.posted_at.isoformat()}
