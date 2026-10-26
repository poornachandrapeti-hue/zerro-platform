"""Phase 6 mixed provenance reconciliation, read-only and deliberately fail-closed.

This is a warehouse/item/unit accounting diagnostic, NOT a reservation/issue
service. GRN and transfer-derived quantities may share StockBalance but must
never be represented as one interchangeable QA-cleared lot pool.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.models import User
from app.domains.supply_chain.models import StockPosting, StockPostingLine, StockBalance
from .material_handovers import _scope
from .models import StoresTransferDestinationLot, StoresTransferLotLineage

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Mixed Lot Provenance'])


def summarize_provenance(movements, transfer_lots, aggregate_on_hand, *, unit):
    """Pure accounting of posted stock movements; never grants availability.

    movements: (kind, quantity, posting_id, source_posting_id, source_line_id).
    transfer_lots: (destination_posting_id, status, quantity, lot_code).
    Unknown posting kinds/invalid linkage cause a reconciliation blocker.
    """
    totals = defaultdict(lambda: Decimal('0'))
    blockers = set()
    incoming_by_posting = defaultdict(list)
    for posting_id, status, qty, code in transfer_lots:
        incoming_by_posting[posting_id].append((status, qty, code))
    seen_incoming = set()
    for kind, raw_qty, posting_id, source_posting_id, source_line_id in movements:
        try:
            qty = Decimal(str(raw_qty))
            if not qty.is_finite() or qty <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError, TypeError):
            blockers.add('INVALID_POSTING_QUANTITY')
            continue
        if kind == 'TransferIn':
            totals['transfer_in'] += qty
            matches = incoming_by_posting.get(posting_id, [])
            if len(matches) != 1 or not source_posting_id or not source_line_id:
                blockers.add('TRANSFER_DESTINATION_PROVENANCE_MISSING')
            else:
                status, raw_lot_qty, _ = matches[0]
                if posting_id in seen_incoming:
                    blockers.add('DUPLICATE_TRANSFER_IN_LINE')
                seen_incoming.add(posting_id)
                try:
                    lot_qty = Decimal(str(raw_lot_qty))
                    if not lot_qty.is_finite() or lot_qty != qty:
                        blockers.add('TRANSFER_LOT_QUANTITY_MISMATCH')
                except (InvalidOperation, ValueError, TypeError):
                    blockers.add('TRANSFER_LOT_QUANTITY_MISMATCH')
                if status != 'QAAcceptedPendingActivation':
                    blockers.add('TRANSFER_LOT_NOT_QA_ACCEPTED')
        elif kind == 'TransferOut':
            totals['transfer_out'] += qty
        elif kind == 'Accept':
            totals['grn_accept'] += qty
        elif kind == 'Issue':
            totals['issued'] += qty
        elif kind == 'Return':
            totals['returned'] += qty
        else:
            blockers.add('UNSUPPORTED_POSTING_KIND')
    for posting_id in incoming_by_posting:
        if posting_id not in seen_incoming:
            blockers.add('ORPHAN_DESTINATION_LOT_OR_INVALID_TRANSFER_IN')
    net = totals['grn_accept'] + totals['transfer_in'] + totals['returned'] - totals['transfer_out'] - totals['issued']
    try:
        balance = Decimal(str(aggregate_on_hand))
        if not balance.is_finite():
            raise InvalidOperation
    except (InvalidOperation, ValueError, TypeError):
        balance = None
        blockers.add('INVALID_AGGREGATE_BALANCE')
    if balance is not None and net != balance:
        blockers.add('LEDGER_BALANCE_MISMATCH')
    if net < 0:
        blockers.add('NEGATIVE_LEDGER_NET')
    if totals['transfer_in']:
        blockers.add('TRANSFER_LOT_ALLOCATION_AND_ISSUE_NOT_IMPLEMENTED')
    return {
        'unit': unit,
        'grn_accepted': str(totals['grn_accept']),
        'transfer_in': str(totals['transfer_in']),
        'transfer_out': str(totals['transfer_out']),
        'issued': str(totals['issued']),
        'returned': str(totals['returned']),
        'calculated_on_hand': str(net),
        'recorded_on_hand': str(balance) if balance is not None else None,
        'ledger_reconciles': balance is not None and net == balance and not (blockers - {'TRANSFER_LOT_ALLOCATION_AND_ISSUE_NOT_IMPLEMENTED'}),
        'reservable': False, 'issuable': False,
        'physical_stock_readiness': 'Unverified',
        'blockers': sorted(blockers | {'LIVE_DATABASE_TRANSACTION_VALIDATION_PENDING'}),
    }


@router.get('/lot-provenance/warehouse-balance')
def mixed_lot_warehouse_balance(pid: int, warehouse_id: int, item_id: int, unit: str,
                                u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.view')
    if warehouse_id <= 0 or item_id <= 0 or not unit.strip():
        raise HTTPException(422, 'Valid warehouse, item and unit required')
    movements = db.execute(select(StockPosting.kind, StockPostingLine.quantity, StockPosting.id,
                                  StockPosting.source_posting_id, StockPostingLine.source_line_id)
        .join(StockPostingLine, StockPostingLine.posting_id == StockPosting.id)
        .where(StockPosting.project_id == pid, StockPosting.organization_id == u.organization_id,
               StockPosting.warehouse_id == warehouse_id, StockPosting.status == 'Posted',
               StockPostingLine.item_id == item_id, StockPostingLine.unit == unit)).all()
    lots = db.execute(select(StoresTransferLotLineage.destination_posting_id,
                             StoresTransferDestinationLot.status, StoresTransferDestinationLot.quantity,
                             StoresTransferDestinationLot.lot_code)
        .join(StoresTransferLotLineage, StoresTransferDestinationLot.lineage_id == StoresTransferLotLineage.id)
        .where(StoresTransferDestinationLot.organization_id == u.organization_id,
               StoresTransferDestinationLot.destination_project_id == pid,
               StoresTransferDestinationLot.destination_warehouse_id == warehouse_id,
               StoresTransferDestinationLot.item_id == item_id)).all()
    balance = db.execute(select(StockBalance).where(
        StockBalance.project_id == pid, StockBalance.warehouse_id == warehouse_id,
        StockBalance.item_id == item_id, StockBalance.unit == unit)).scalar_one_or_none()
    result = summarize_provenance(movements, lots, balance.on_hand if balance else 0, unit=unit)
    if balance is None:
        result['blockers'] = sorted(set(result['blockers']) | {'STOCK_BALANCE_ROW_MISSING'})
        result['ledger_reconciles'] = False
    return {'project_id': pid, 'warehouse_id': warehouse_id, 'item_id': item_id, **result}
