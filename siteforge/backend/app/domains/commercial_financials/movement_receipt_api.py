"""Authenticated read-only posted issue -> receipt cost provenance.

Amounts are indicative; no authoritative stock costing/journal claims.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.supply_chain.models import StockPosting, StockPostingLine, GoodsReceiptLine, GoodsReceipt
from app.domains.stores_inventory.models import StoresOutboundLotAllocation, StoresReceiptLot
from .router import guard
from .receipt_cost_authority import consolidated_receipt_preview
from .movement_receipt_reconciliation import reconcile_issue_receipt_evidence
from .models import FinanceInventoryCostingPolicy
from .movement_policy_evidence import classify_policy_evidence
from .receipt_lot_coverage import audit_lot_issue_coverage
from .movement_evidence_gate import classify_movement_cost_readiness
from .receipt_preview_selection import select_receipt_previews
from .movement_chronology import verify_receipt_acceptance_precedes_issue
from .receipt_acceptance_quantity import verify_receipt_acceptance_ceiling
from .receipt_lot_acceptance_coverage import verify_lot_acceptance_coverage
from .movement_query_bounds import (MAX_ISSUE_LOT_ALLOCATIONS,
                                    MAX_ACCEPTANCE_POSTINGS_PER_RECEIPT,
                                    require_complete_bounded_rows)

router = APIRouter(prefix='/api/projects/{pid}/financials/movement-receipt-reconciliation', tags=['Financials'])


@router.get('/{stock_posting_line_id}')
def movement_receipt_reconciliation(pid: int, stock_posting_line_id: int,
                                   user: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Return a single bounded issue line; source ledger never modified."""
    guard(db, user, pid, 'financials.view')
    org = user.organization_id
    line = (db.query(StockPostingLine, StockPosting)
            .join(StockPosting, StockPostingLine.posting_id == StockPosting.id)
            .filter(StockPostingLine.id == stock_posting_line_id,
                    StockPosting.project_id == pid, StockPosting.organization_id == org,
                    StockPosting.kind == 'Issue', StockPosting.status == 'Posted').one_or_none())
    if not line:
        raise HTTPException(404, 'Posted issue line not found in project')
    issue, posting = line
    allocations = (db.query(StoresOutboundLotAllocation)
                   .filter_by(stock_posting_line_id=issue.id, organization_id=org, project_id=pid)
                   .limit(MAX_ISSUE_LOT_ALLOCATIONS + 1).all())
    try:
        require_complete_bounded_rows(allocations, MAX_ISSUE_LOT_ALLOCATIONS, 'Issue receipt-lot allocations')
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    lot_ids = {a.receipt_lot_id for a in allocations}
    lots = (db.query(StoresReceiptLot).filter(StoresReceiptLot.id.in_(lot_ids),
             StoresReceiptLot.organization_id == org, StoresReceiptLot.project_id == pid).all()) if lot_ids else []
    if len(lots) != len(lot_ids):
        raise HTTPException(409, 'Missing or out-of-scope receipt-lot lineage')
    # Cross-issue intake ceiling: all posted issues for the same receipt lots,
    # not just the requested issue. This is a consistency gate, NOT free stock.
    lot_coverage = None
    if lot_ids:
        historical_rows = (db.query(StoresOutboundLotAllocation, StockPostingLine, StockPosting)
            .join(StockPostingLine, StoresOutboundLotAllocation.stock_posting_line_id == StockPostingLine.id)
            .join(StockPosting, StockPostingLine.posting_id == StockPosting.id)
            .filter(StoresOutboundLotAllocation.receipt_lot_id.in_(lot_ids),
                    StoresOutboundLotAllocation.organization_id == org,
                    StoresOutboundLotAllocation.project_id == pid,
                    StockPosting.organization_id == org, StockPosting.project_id == pid,
                    StockPosting.kind == 'Issue', StockPosting.status == 'Posted').limit(5001).all())
        if len(historical_rows) > 5000:
            raise HTTPException(409, 'Receipt lot coverage exceeds bounded audit capacity')
        try:
            lot_coverage = audit_lot_issue_coverage(
                organization_id=org, project_id=pid,
                lots=[{'id': lot.id, 'organization_id': lot.organization_id,
                       'project_id': lot.project_id, 'quantity': lot.quantity} for lot in lots],
                posted_allocations=[{'stock_posting_line_id': movement.id,
                                     'receipt_lot_id': allocation.receipt_lot_id,
                                     'organization_id': allocation.organization_id,
                                     'project_id': allocation.project_id,
                                     'quantity': allocation.quantity}
                                    for allocation, movement, _ in historical_rows])
        except ValueError as exc:
            raise HTTPException(409, f'Historical lot coverage invalid: {exc}') from exc
    receipt_ids = {lot.goods_receipt_line_id for lot in lots}
    receipt_lines = (db.query(GoodsReceiptLine).filter(GoodsReceiptLine.id.in_(receipt_ids)).all()) if receipt_ids else []
    if len(receipt_lines) != len(receipt_ids):
        raise HTTPException(409, 'Missing receipt line')
    # Receipt lines have no project column: establish scope through their
    # authoritative GRN header before loading Finance cost evidence.
    receipt_headers = (db.query(GoodsReceiptLine, GoodsReceipt)
        .join(GoodsReceipt, GoodsReceiptLine.goods_receipt_id == GoodsReceipt.id)
        .filter(GoodsReceiptLine.id.in_(receipt_ids),
                GoodsReceipt.organization_id == org, GoodsReceipt.project_id == pid,
                GoodsReceipt.status == 'Posted').all()) if receipt_ids else []
    scoped_receipt_ids = {line.id for line, _ in receipt_headers}
    if len(receipt_headers) != len(receipt_ids) or scoped_receipt_ids != receipt_ids:
        raise HTTPException(409, 'Receipt header is missing, unposted, or out of project scope')
    receipt_warehouses = {line.id: header.warehouse_id for line, header in receipt_headers}
    receipt_quantities = {line.id: line.quantity for line, _ in receipt_headers}
    for lot in lots:
        if lot.warehouse_id != posting.warehouse_id:
            raise HTTPException(409, 'Issue and receipt-lot warehouse mismatch')
        receipt_warehouse = receipt_warehouses[lot.goods_receipt_line_id]
        if receipt_warehouse is not None and receipt_warehouse != lot.warehouse_id:
            raise HTTPException(409, 'Goods receipt and receipt-lot warehouse mismatch')
    # Verify lot provenance using already-posted acceptance line material identity.
    matched = {}
    chronology_events = []
    acceptance_quantity_evidence = []
    lot_acceptance_evidence = []
    # The issue's selected lot subset is insufficient for an intake ceiling:
    # other lots for the same GRN line must count toward accepted quantity.
    all_receipt_lots = (db.query(StoresReceiptLot)
        .filter(StoresReceiptLot.goods_receipt_line_id.in_(receipt_ids),
                StoresReceiptLot.organization_id == org,
                StoresReceiptLot.project_id == pid)
        .limit(5001).all()) if receipt_ids else []
    if len(all_receipt_lots) > 5000:
        raise HTTPException(409, 'Receipt lot intake audit exceeds bounded capacity')
    for receipt_lot in all_receipt_lots:
        if receipt_lot.warehouse_id != posting.warehouse_id:
            raise HTTPException(409, 'Receipt lot warehouse mismatch in intake audit')
    for receipt_id in receipt_ids:
        stock_lines = (db.query(StockPostingLine, StockPosting)
                       .join(StockPosting, StockPostingLine.posting_id == StockPosting.id)
                       .filter(StockPostingLine.goods_receipt_line_id == receipt_id,
                               StockPosting.organization_id == org, StockPosting.project_id == pid,
                               StockPosting.status == 'Posted', StockPosting.kind == 'Accept')
                       .limit(MAX_ACCEPTANCE_POSTINGS_PER_RECEIPT + 1).all())
        try:
            require_complete_bounded_rows(stock_lines, MAX_ACCEPTANCE_POSTINGS_PER_RECEIPT,
                                          'Receipt acceptance postings')
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        try:
            acceptance_result = verify_receipt_acceptance_ceiling(
                receipt_line_id=receipt_id, received_quantity=receipt_quantities[receipt_id],
                accepted_lines=[{'id': sl.id, 'goods_receipt_line_id': sl.goods_receipt_line_id,
                                 'quantity': sl.quantity} for sl, _ in stock_lines])
            acceptance_quantity_evidence.append(acceptance_result)
            lot_acceptance_evidence.append(verify_lot_acceptance_coverage(
                receipt_line_id=receipt_id, accepted_quantity=acceptance_result['accepted_quantity'],
                lots=[{'id': lot.id, 'goods_receipt_line_id': lot.goods_receipt_line_id,
                       'quantity': lot.quantity} for lot in all_receipt_lots
                      if lot.goods_receipt_line_id == receipt_id]))
        except ValueError as exc:
            raise HTTPException(409, f'Receipt acceptance quantity invalid: {exc}') from exc
        identities = {(sl.item_id, sl.unit) for sl, _ in stock_lines}
        chronology_events.extend((receipt_id, accepted_posting.created_at) for _, accepted_posting in stock_lines)
        if len(identities) != 1:
            raise HTTPException(409, 'Receipt material identity is missing or ambiguous')
        matched[receipt_id] = next(iter(identities))
    try:
        chronology = verify_receipt_acceptance_precedes_issue(posting.created_at, chronology_events)
    except ValueError as exc:
        raise HTTPException(409, f'Receipt acceptance chronology invalid: {exc}') from exc
    if any(matched[rid] != (issue.item_id, issue.unit) for rid in receipt_ids):
        raise HTTPException(409, 'Issue and receipt materials do not match')
    evidence = consolidated_receipt_preview(pid=pid, user=user, db=db)
    try:
        receipt_previews = select_receipt_previews(evidence.get('receipt_lines', []), receipt_ids)
        result = reconcile_issue_receipt_evidence(
            organization_id=org, project_id=pid,
            issues=[{'id':issue.id,'organization_id':org,'project_id':pid,
                     'material_id':issue.item_id,'unit':issue.unit,'quantity':issue.quantity}],
            lots=[{'id':lot.id,'organization_id':org,'project_id':pid,
                   'material_id':matched[lot.goods_receipt_line_id][0],
                   'unit':matched[lot.goods_receipt_line_id][1],
                   'goods_receipt_line_id':lot.goods_receipt_line_id} for lot in lots],
            allocations=[{'stock_posting_line_id':a.stock_posting_line_id,
                          'receipt_lot_id':a.receipt_lot_id,'quantity':a.quantity,
                          'organization_id':org,'project_id':pid} for a in allocations],
            receipt_previews=receipt_previews,
        )[0]
    except (ValueError, ArithmeticError, TypeError, KeyError) as exc:
        raise HTTPException(409, f'Issue receipt evidence invalid: {exc}') from exc
    policies = (db.query(FinanceInventoryCostingPolicy)
                .filter_by(organization_id=org, project_id=pid)
                .order_by(FinanceInventoryCostingPolicy.revision.desc()).all())
    policy_evidence = classify_policy_evidence(policies, result.get('currency'))
    return {'project_id':pid,'stock_posting_id':posting.id,'read_only':True,
            'costing_policy_evidence': policy_evidence,
            'finance_closure_readiness': classify_movement_cost_readiness(
                reconciliation=result, policy=policy_evidence, lot_coverage=lot_coverage),
            'receipt_lot_intake_coverage': lot_coverage,
            'receipt_acceptance_chronology': chronology,
            'receipt_acceptance_quantity_evidence': acceptance_quantity_evidence,
            'receipt_lot_acceptance_coverage': lot_acceptance_evidence,
            'costing_policy_applied':False,'movement_valuation_verified':False,
            'journal_posting_verified':False, 'result':result}
