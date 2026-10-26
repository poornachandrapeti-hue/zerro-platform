"""Read-only GRN-to-invoice evidence. Invoice verification is not inventory valuation."""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.supply_chain.models import (GoodsReceipt, GoodsReceiptLine, VendorInvoice,
    VendorInvoiceLine, PurchaseOrderLine)
from .models import FinanceSupplierInvoicePosting, FinanceProcurementAllocation
from .router import guard

router = APIRouter(prefix='/api/projects/{pid}/financials/receipt-invoice-evidence', tags=['Financials'])


def classify_invoice_evidence(*, receipt_qty, matches):
    """Do not allocate PO-level invoice amounts to a receipt line by assumption."""
    qty = Decimal(str(receipt_qty))
    if not qty.is_finite() or qty <= 0:
        return 'INVALID_RECEIPT_QUANTITY'
    if not matches:
        return 'NO_FINANCE_VERIFIED_INVOICE_LINE'
    ids = [m['invoice_line_id'] for m in matches]
    if len(set(ids)) != len(ids):
        return 'DUPLICATE_INVOICE_LINE'
    currencies = {m['currency'] for m in matches}
    if len(currencies) != 1:
        return 'MIXED_INVOICE_CURRENCIES'
    if any(not Decimal(str(m[k])).is_finite() or Decimal(str(m[k])) <= 0 for m in matches for k in ('quantity', 'unit_price')):
        return 'INVALID_INVOICE_LINE_VALUES'
    # Even complete PO line invoice quantities are not GRN line-specific accounting allocations.
    return 'PO_LINE_INVOICE_VERIFIED_RECEIPT_COST_UNALLOCATED'


@router.get('/{receipt_line_id}')
def receipt_invoice_evidence(pid:int, receipt_line_id:int, user:User=Depends(authenticated), db:Session=Depends(get_db)):
    guard(db, user, pid, 'financials.view')
    org = user.organization_id
    row = db.query(GoodsReceiptLine, GoodsReceipt, PurchaseOrderLine).join(
        GoodsReceipt, GoodsReceiptLine.goods_receipt_id == GoodsReceipt.id).join(
        PurchaseOrderLine, GoodsReceiptLine.purchase_order_line_id == PurchaseOrderLine.id).filter(
        GoodsReceiptLine.id == receipt_line_id, GoodsReceipt.project_id == pid,
        GoodsReceipt.organization_id == org).one_or_none()
    if not row:
        raise HTTPException(404, 'Receipt line not found in this project')
    line, receipt, po_line = row
    if receipt.status != 'Posted' or po_line.purchase_order_id != receipt.purchase_order_id:
        raise HTTPException(409, 'Receipt not posted or PO line does not match receipt')
    allocation = db.query(FinanceProcurementAllocation).filter_by(
        organization_id=org, project_id=pid, purchase_order_id=receipt.purchase_order_id).one_or_none()
    records = db.query(VendorInvoiceLine, VendorInvoice, FinanceSupplierInvoicePosting).join(
        VendorInvoice, VendorInvoiceLine.invoice_id == VendorInvoice.id).join(
        FinanceSupplierInvoicePosting, FinanceSupplierInvoicePosting.vendor_invoice_id == VendorInvoice.id).filter(
        VendorInvoiceLine.purchase_order_line_id == po_line.id,
        VendorInvoice.project_id == pid, VendorInvoice.organization_id == org,
        VendorInvoice.purchase_order_id == receipt.purchase_order_id,
        FinanceSupplierInvoicePosting.project_id == pid,
        FinanceSupplierInvoicePosting.organization_id == org,
        FinanceSupplierInvoicePosting.purchase_order_id == receipt.purchase_order_id).all()
    matches = []
    for invoice_line, invoice, posting in records:
        if (not allocation or posting.cost_code_id != allocation.cost_code_id or
            posting.posted_at is None or posting.posted_by is None):
            raise HTTPException(409, 'Finance verification missing or cost code inconsistent')
        matches.append({'invoice_line_id':invoice_line.id, 'invoice_id':invoice.id,
                        'finance_verification_id':posting.id, 'quantity':str(invoice_line.quantity),
                        'unit_price':str(invoice_line.billed_unit_price), 'currency':posting.currency})
    status = classify_invoice_evidence(receipt_qty=line.quantity, matches=matches)
    return {'receipt_line_id':line.id, 'goods_receipt_id':receipt.id,
            'purchase_order_id':receipt.purchase_order_id, 'purchase_order_line_id':po_line.id,
            'finance_cost_code_id':allocation.cost_code_id if allocation else None,
            'status':status, 'invoice_line_evidence':matches, 'read_only':True,
            'receipt_unit_cost_verified':False, 'movement_valuation_verified':False,
            'journal_posting_verified':False,
            'warning':'Finance invoice verification belongs to a PO line, not a specific GRN line. No receipt cost or journal posting can be certified from these references.'}
