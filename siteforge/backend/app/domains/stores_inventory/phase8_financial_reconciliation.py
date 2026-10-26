"""Phase 8 Stores/Financials reference reconciliation; no accounting or valuation authority."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from .material_handovers import _scope
from app.domains.commercial_financials.models import (FinanceCostCode, FinanceProcurementAllocation, FinanceSupplierInvoicePosting)
from app.domains.supply_chain.models import (StockPostingLine, StockPosting, GoodsReceiptLine, PurchaseOrderLine, GoodsReceipt)
from .models import (StoresMaterialRequest, StoresMaterialHandover,
                     StoresMaterialReturn, StoresContractObligationLink)

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Phase 8 Finance References'])


def financial_reference_rows(requests, handovers, returns, contract_links):
    """No implied entitlement, price, financial posting, or recovery from custody evidence."""
    by_req = {}
    for handover in handovers:
        by_req.setdefault(handover.material_request_id, []).append(handover)
    by_handover = {}
    for return_record in returns:
        by_handover.setdefault(return_record.handover_id, []).append(return_record)
    linked = {x.material_request_id: x for x in contract_links}
    result = []
    for req in requests:
        related = by_req.get(req.id, [])
        link = linked.get(req.id)
        blockers = ['Inventory valuation is not established by a Stores movement',
                    'Financial cost-code allocation and journal reference are not linked to this Stores request',
                    'Contract recovery entitlement and amount require authorized Contracts/Financials review']
        if not req.requirement_line_id:
            blockers.append('Approved canonical Procurement requirement reference missing')
        if not link:
            blockers.append('Explicit Contract obligation reference missing')
        if not related:
            blockers.append('No posted-issue handover evidence for this Stores request')
        return_exceptions = []
        handover_rows = []
        for handover in related:
            matching_returns = by_handover.get(handover.id, [])
            if len(matching_returns) > 1:
                return_exceptions.append({'handover_id': handover.id, 'code': 'duplicate_return_reference'})
            for returned in matching_returns:
                if returned.stock_posting_id is not None:
                    code = 'posted_return_ledger_unverified'
                elif returned.status in ('QA Rejected', 'QA Quarantined'):
                    code = 'return_qa_exception'
                else:
                    code = 'return_not_posted'
                return_exceptions.append({'handover_id': handover.id, 'return_id': returned.id, 'code': code})
            primary_return = matching_returns[0] if len(matching_returns) == 1 else None
            handover_rows.append({
                'handover_id': handover.id, 'issue_line_id': handover.stock_posting_line_id,
                'status': handover.status,
                'return_id': primary_return.id if primary_return else None,
                'return_status': primary_return.status if primary_return else None,
                'return_posting_id': primary_return.stock_posting_id if primary_return else None,
                'return_reference_count': len(matching_returns),
            })
        if return_exceptions:
            blockers.append('Return custody/QA/posting requires authoritative stock-ledger reconciliation')
        result.append({
            'material_request_id': req.id, 'request_status': req.status,
            'requirement_line_id': req.requirement_line_id,
            'work_package_id': req.work_package_id, 'planning_wbs_id': req.planning_wbs_id,
            'item_id': req.item_id, 'unit': req.base_unit,
            'contract_id': link.contract_id if link else None,
            'contract_obligation_id': link.obligation_id if link else None,
            'contract_reference_only': bool(link),
            'handovers': handover_rows,
            'return_exceptions': return_exceptions,
            'valuation_verified': False, 'recovery_authorized': False,
            'finance_posting_created': False, 'billing_certified': False,
            'readiness': 'Blocked', 'blockers': blockers,
        })
    return result


def finance_authority_contract():
    """Declared integration capability, not guessed from invoice posting names.

    Finance supplier invoice *verification* is not a GL journal.  Do not
    classify inventory costs as verified until Finance owns a cost valuation
    record that references an exact stock posting line and journal evidence.
    """
    return {
        'authority': 'commercial_financials',
        'purchase_order_cost_code': {'model': 'FinanceProcurementAllocation', 'available': True,
                                     'scope': 'purchase_order'},
        'supplier_invoice_verification': {'model': 'FinanceSupplierInvoicePosting', 'available': True,
                                          'scope': 'purchase_order'},
        'movement_valuation': {'model': None, 'available': False,
                               'required_keys': ['organization_id', 'project_id',
                                                 'stock_posting_line_id', 'costing_method',
                                                 'currency', 'amount', 'valuation_id']},
        'accounting_journal': {'model': None, 'available': False,
                               'required_keys': ['organization_id', 'project_id',
                                                 'valuation_id', 'journal_entry_id',
                                                 'posted_at', 'posted_by']},
        'movement_cost_verified': False,
        'journal_posting_verified': False,
        'safe_next_action': 'Implement Finance-owned authoritative valuation and GL journal evidence before enabling movement-level amounts.',
    }


def finance_coverage_summary(cost_codes: int, po_allocations: int, invoice_postings: int):
    """Finance-owned project counts; never imply a per-issue valuation or linked invoice."""
    return {
        'finance_cost_codes': cost_codes,
        'purchase_order_cost_allocations': po_allocations,
        'supplier_invoice_verifications': invoice_postings,
        'stores_to_finance_link_verified': False,
        'inventory_cost_valuation_verified': False,
        'reason': 'Project finance records alone cannot associate a material handover with a cost code, purchase order, or invoice.',
    }


def trace_finance_evidence(handovers, posting_lines, receipt_lines, purchase_order_lines, receipts, allocations, postings, valid_cost_code_ids=None):
    """Read-only PO/cost-code evidence. Never turn a PO code into a stock valuation.

    Only a unique, explicit GRN lineage counts as a trace; invoice postings are
    reported as separate Finance-owned evidence, not movement-level costs.
    """
    lines = {x.id: x for x in posting_lines}
    grn_lines = {x.id: x for x in receipt_lines}
    po_lines = {x.id: x for x in purchase_order_lines}
    grns = {x.id: x for x in receipts}
    by_po = {}
    for allocation in allocations:
        by_po.setdefault(allocation.purchase_order_id, []).append(allocation)
    invoice_by_po = {}
    invoice_header_po_ids = {}
    for posting in postings:
        invoice_by_po.setdefault(posting.purchase_order_id, []).append(posting)
        header_id = getattr(posting, 'vendor_invoice_id', None)
        if header_id is not None:
            invoice_header_po_ids.setdefault(header_id, set()).add(posting.purchase_order_id)
    result = []
    for handover in handovers:
        reasons = []
        lineage = []
        seen = set()
        expected_item = None
        expected_unit = None
        current = lines.get(handover.stock_posting_line_id)
        while current is not None and current.id not in seen:
            seen.add(current.id)
            lineage.append(current.id)
            # An ancestry chain may not silently cross an item or unit boundary.
            # This is evidence integrity only; it does not establish a cost.
            item = getattr(current, 'item_id', None)
            unit = getattr(current, 'unit', None)
            if expected_item is None:
                expected_item = item
            elif item is not None and item != expected_item:
                reasons.append('Stock-line ancestry changes material item')
            if expected_unit is None:
                expected_unit = unit
            elif unit is not None and unit != expected_unit:
                reasons.append('Stock-line ancestry changes unit')
            if current.goods_receipt_line_id is not None:
                break
            next_id = current.source_line_id
            if next_id is not None and next_id not in lines:
                reasons.append('Stock-line ancestry is incomplete')
            current = lines.get(next_id)
        if current is not None and current.id in seen and current.goods_receipt_line_id is None:
            reasons.append('Stock-line ancestry contains a cycle')
        if current is None or current.goods_receipt_line_id is None:
            reasons.append('No explicit stock-line to goods-receipt lineage')
        receipt_line = grn_lines.get(current.goods_receipt_line_id) if current and current.goods_receipt_line_id else None
        po_line = po_lines.get(receipt_line.purchase_order_line_id) if receipt_line else None
        grn = grns.get(receipt_line.goods_receipt_id) if receipt_line else None
        if (receipt_line is None or po_line is None or grn is None
                or grn.purchase_order_id != po_line.purchase_order_id):
            reasons.append('Missing or inconsistent GRN / purchase order line')
            po_id = None
        else:
            po_id = po_line.purchase_order_id
            # The receipt's material must match the traced stock movement.
            # PO award lines do not carry an authoritative item identifier here.
            if getattr(grn, 'item_id', None) is not None and expected_item is not None and grn.item_id != expected_item:
                reasons.append('Goods receipt material differs from stock movement material')
        candidates = by_po.get(po_id, []) if po_id is not None else []
        if len(candidates) != 1:
            reasons.append('Exactly one Finance cost-code allocation is required for the purchase order')
        allocation = candidates[0] if len(candidates) == 1 else None
        if allocation and valid_cost_code_ids is not None and allocation.cost_code_id not in valid_cost_code_ids:
            reasons.append('Finance cost code is absent from this organization and project')
            allocation = None
        invoices = invoice_by_po.get(po_id, []) if po_id is not None else []
        invoice_ids = [x.id for x in invoices]
        if len(invoice_ids) != len(set(invoice_ids)):
            reasons.append('Duplicate Finance invoice posting identifier found for purchase order')
        if po_id is not None and not invoices:
            reasons.append('No Finance supplier invoice posting reference for purchase order')
        # Invoice verification is Finance-owned; a PO match alone is insufficient
        # if the invoice is coded to a different cost center, or an invoice was
        # accidentally represented by more than one Finance verification.
        invoice_header_ids = [getattr(x, 'vendor_invoice_id', None) for x in invoices]
        known_headers = [x for x in invoice_header_ids if x is not None]
        if len(known_headers) != len(set(known_headers)):
            reasons.append('Duplicate Finance verification for the same supplier invoice')
        if any(len(invoice_header_po_ids[header_id]) > 1 for header_id in known_headers):
            reasons.append('Supplier invoice is linked to multiple purchase orders in Finance verification evidence')
        if allocation is not None and any(
            getattr(x, 'cost_code_id', allocation.cost_code_id) != allocation.cost_code_id
            for x in invoices
        ):
            reasons.append('Supplier invoice Finance cost code conflicts with purchase order allocation')
        currencies = {getattr(x, 'currency', None) for x in invoices if getattr(x, 'currency', None)}
        if len(currencies) > 1:
            reasons.append('Supplier invoice verifications use inconsistent currencies')
        # Finance verification quality is separate from the movement/PO reference trace.
        # Never aggregate supplier invoice amounts into stock movement valuation:
        # partial receipts, taxes, and multiple GRNs make this attribution unsafe.
        finance_evidence_issues = []
        for invoice in invoices:
            invoice_key = getattr(invoice, 'id', None)
            raw_amount = getattr(invoice, 'amount', None)
            try:
                amount = Decimal(str(raw_amount))
                if not amount.is_finite() or amount <= 0:
                    raise InvalidOperation()
            except (InvalidOperation, TypeError, ValueError):
                finance_evidence_issues.append(f'Finance invoice verification {invoice_key}: valid positive amount missing')
            if getattr(invoice, 'vendor_invoice_id', None) is None:
                finance_evidence_issues.append(f'Finance invoice verification {invoice_key}: source invoice header missing')
            if not getattr(invoice, 'currency', None):
                finance_evidence_issues.append(f'Finance invoice verification {invoice_key}: currency missing')
            if getattr(invoice, 'posted_by', None) is None or getattr(invoice, 'posted_at', None) is None:
                finance_evidence_issues.append(f'Finance invoice verification {invoice_key}: approval audit metadata missing')
        # Structural conflicts must never produce a misleading COMPLETE badge.
        # A complete invoice is not the same as a consistent invoice-to-PO trace.
        finance_conflicts = [reason for reason in reasons if (
            'Finance' in reason or 'invoice' in reason or 'currencies' in reason
        )]
        finance_evidence_status = ('FINANCE_PO_VERIFICATIONS_COMPLETE'
                                   if invoices and not finance_evidence_issues and not finance_conflicts
                                   else 'FINANCE_PO_VERIFICATIONS_INCOMPLETE')
        # Purchase-order invoice references do not certify handover-level journal posting.
        reference_traced = bool(po_id is not None and allocation is not None and not reasons)
        result.append({
            'handover_id': handover.id,
            'stock_posting_line_id': handover.stock_posting_line_id,
            'stock_line_trace': lineage,
            'goods_receipt_line_id': receipt_line.id if receipt_line and po_id is not None else None,
            'purchase_order_line_id': po_line.id if po_id is not None else None,
            'purchase_order_id': po_id,
            'finance_allocation_id': allocation.id if allocation else None,
            'finance_cost_code_id': allocation.cost_code_id if allocation else None,
            'finance_invoice_posting_ids': sorted(set(invoice_ids)),
            'finance_invoice_header_ids': sorted(set(known_headers)),
            'invoice_currencies': sorted(currencies),
            'procurement_finance_reference_traced': reference_traced,
            'reconciliation_status': 'PO_FINANCE_REFERENCES_TRACED' if reference_traced else 'BLOCKED_MISSING_OR_AMBIGUOUS_EVIDENCE',
            'invoice_link_scope': 'PURCHASE_ORDER_ONLY' if invoices else 'NONE',
            'finance_verification_evidence_status': finance_evidence_status,
            'finance_verification_evidence_issues': finance_evidence_issues + finance_conflicts,
            'costing_method_status': 'NOT_CONFIGURED_OR_NOT_EVIDENCED',
            'movement_valuation_authority': 'NOT_ESTABLISHED',
            'journal_authority': 'NOT_ESTABLISHED',
            'accounting_posting_status': 'UNVERIFIED',
            'movement_cost_verified': False,
            'journal_verified': False,
            'financial_value': None,
            'blockers': reasons + ['No authoritative movement-level valuation or journal relationship established'],
        })
    return result


def finance_trace_summary(records):
    """Bounded, read-only status counters; never a monetary or journal total."""
    traced = sum(r['reconciliation_status'] == 'PO_FINANCE_REFERENCES_TRACED' for r in records)
    return {'handover_count': len(records), 'po_finance_references_traced': traced,
            'blocked_handovers': len(records) - traced,
            'movement_value_verified': 0, 'accounting_journals_verified': 0}


@router.get('/phase8/financial-reference-reconciliation')
def financial_reference_reconciliation(pid: int, work_package_id: int | None = None,
    limit: int = 200, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    # Internal Financials reference-review feed; no supplier, contract price or billing details.
    _scope(db, u, pid, 'stores.requests.review')
    if limit < 1 or limit > 500 or (work_package_id is not None and work_package_id <= 0):
        raise HTTPException(422, 'Invalid filter or limit')
    query = select(StoresMaterialRequest).where(
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.organization_id == u.organization_id)
    if work_package_id is not None:
        query = query.where(StoresMaterialRequest.work_package_id == work_package_id)
    requests = db.execute(query.order_by(StoresMaterialRequest.id.desc()).limit(limit)).scalars().all()
    ids = [r.id for r in requests]
    handovers = db.execute(select(StoresMaterialHandover).where(
        StoresMaterialHandover.project_id == pid,
        StoresMaterialHandover.organization_id == u.organization_id,
        StoresMaterialHandover.material_request_id.in_(ids))).scalars().all() if ids else []
    handover_ids = [h.id for h in handovers]
    returns = db.execute(select(StoresMaterialReturn).where(
        StoresMaterialReturn.project_id == pid,
        StoresMaterialReturn.organization_id == u.organization_id,
        StoresMaterialReturn.handover_id.in_(handover_ids))).scalars().all() if handover_ids else []
    links = db.execute(select(StoresContractObligationLink).where(
        StoresContractObligationLink.project_id == pid,
        StoresContractObligationLink.organization_id == u.organization_id,
        StoresContractObligationLink.material_request_id.in_(ids))).scalars().all() if ids else []
    def project_count(model):
        return db.execute(select(func.count()).select_from(model).where(
            model.organization_id == u.organization_id, model.project_id == pid)).scalar_one()
    finance_coverage = finance_coverage_summary(
        project_count(FinanceCostCode),
        project_count(FinanceProcurementAllocation),
        project_count(FinanceSupplierInvoicePosting),
    )
    # Resolve ledger ancestry in bounded batches; never approximate it from item/WBS alone.
    seed_ids = {h.stock_posting_line_id for h in handovers}
    line_map = {}
    frontier = seed_ids
    for _ in range(16):
        todo = frontier - set(line_map)
        if not todo:
            break
        # Scope EVERY ancestry hop through its parent posting, not only the GRN.
        # This prevents traversing a foreign project's stock lineage.
        fetched = db.execute(select(StockPostingLine).join(
            StockPosting, StockPosting.id == StockPostingLine.posting_id).where(
            StockPostingLine.id.in_(todo),
            StockPosting.project_id == pid,
            StockPosting.organization_id == u.organization_id)).scalars().all()
        line_map.update({line.id: line for line in fetched})
        frontier = {line.source_line_id for line in fetched if line.source_line_id is not None}
    receipt_ids = {line.goods_receipt_line_id for line in line_map.values() if line.goods_receipt_line_id is not None}
    grn_lines = db.execute(select(GoodsReceiptLine).where(GoodsReceiptLine.id.in_(receipt_ids))).scalars().all() if receipt_ids else []
    po_line_ids = {line.purchase_order_line_id for line in grn_lines}
    po_lines = db.execute(select(PurchaseOrderLine).where(PurchaseOrderLine.id.in_(po_line_ids))).scalars().all() if po_line_ids else []
    grn_ids = {line.goods_receipt_id for line in grn_lines}
    grns = db.execute(select(GoodsReceipt).where(GoodsReceipt.id.in_(grn_ids), GoodsReceipt.organization_id == u.organization_id, GoodsReceipt.project_id == pid)).scalars().all() if grn_ids else []
    po_ids = {line.purchase_order_id for line in po_lines}
    allocations = db.execute(select(FinanceProcurementAllocation).where(FinanceProcurementAllocation.purchase_order_id.in_(po_ids), FinanceProcurementAllocation.project_id == pid, FinanceProcurementAllocation.organization_id == u.organization_id)).scalars().all() if po_ids else []
    invoice_postings = db.execute(select(FinanceSupplierInvoicePosting).where(FinanceSupplierInvoicePosting.purchase_order_id.in_(po_ids), FinanceSupplierInvoicePosting.project_id == pid, FinanceSupplierInvoicePosting.organization_id == u.organization_id)).scalars().all() if po_ids else []
    cost_code_ids = {x.cost_code_id for x in allocations}
    valid_cost_code_ids = set(db.execute(select(FinanceCostCode.id).where(
        FinanceCostCode.id.in_(cost_code_ids), FinanceCostCode.project_id == pid,
        FinanceCostCode.organization_id == u.organization_id)).scalars().all()) if cost_code_ids else set()
    evidence = trace_finance_evidence(handovers, list(line_map.values()), grn_lines, po_lines, grns, allocations, invoice_postings, valid_cost_code_ids)
    return {'records': financial_reference_rows(requests, handovers, returns, links),
            'transaction_finance_evidence': evidence,
            'transaction_finance_summary': finance_trace_summary(evidence),
            'finance_coverage': finance_coverage,
            'finance_authority_contract': finance_authority_contract(),
            'as_of': datetime.now(timezone.utc),
            'coverage': f'Latest {limit} Stores material requests; read-only references, not ledger valuation',
            'finance_posting_created': False, 'valuation_verified': False,
            'automatic_contract_recovery': False, 'physical_stock_verified': False}
