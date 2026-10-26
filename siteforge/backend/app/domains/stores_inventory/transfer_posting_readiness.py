"""Phase 6 controlled transfer-posting preflight (read-only).

A transfer may not be booked by composing generic Issue/Accept postings: that
would bypass lot QA provenance and falsely classify transfer-in as a GRN.
This module establishes explicit fail-closed eligibility and useful blockers.
"""
import os
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.supply_chain.models import StockBalance
from .material_handovers import _scope
from .models import StoresTransfer, StoresReceiptLot, StoresTransferLotLineage, StoresInspectionCase, StoresLotQAAttribution, StoresTransferDestinationLot
from app.domains.supply_chain.models import GoodsReceiptLine, StockPosting, StockPostingLine
from app.domains.identity_projects.models import Project
from .atomic_lot_issue import _posting_quantities, _require_full_coverage
from .atomic_lot_acceptance import _checked_qty
from .models import StoresOutboundLotAllocation
from app.domains.supply_chain import stock
from app.domains.identity_projects.router import audit, commit

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Transfer Posting Readiness'])


def checked_balance(on_hand, reserved):
    try:
        on, res = Decimal(str(on_hand)), Decimal(str(reserved))
    except (InvalidOperation, ValueError, TypeError):
        return None, 'Invalid aggregate quantity'
    if not on.is_finite() or not res.is_finite() or on < 0 or res < 0 or res > on:
        return None, 'Corrupt aggregate stock balance'
    return on - res, None


def evaluate_transfer_posting(transfer, *, source_balance=None, destination_balance=None):
    """Pure check; never interpret custody acknowledgment as inventory posting."""
    blockers = []
    if transfer.status != 'Received':
        blockers.append('Destination receipt must be complete without unresolved discrepancy')
    if transfer.discrepancy_status not in ('Not Required', 'Resolved'):
        blockers.append('Transfer discrepancy must be resolved')
    if transfer.received_quantity is None or transfer.dispatched_quantity is None:
        blockers.append('Dispatch and received quantities are required')
    else:
        try:
            sent = Decimal(str(transfer.dispatched_quantity))
            received = Decimal(str(transfer.received_quantity))
            damaged = Decimal(str(transfer.damaged_quantity or 0))
            if not all(x.is_finite() for x in (sent, received, damaged)) or sent <= 0 or received != sent or damaged != 0:
                blockers.append('Only fully received, undamaged transfers are eligible')
        except (InvalidOperation, ValueError, TypeError):
            blockers.append('Invalid dispatched or received quantity')
    if transfer.destination_custodian_company_id is not None and transfer.custody_confirmed_by is None:
        blockers.append('Destination custody confirmation required')
    if (transfer.destination_project_id or transfer.project_id) != transfer.project_id:
        blockers.append('Inter-project stock and lot ownership migration is not yet implemented')
    if source_balance is None:
        blockers.append('Source stock balance not found')
    else:
        available, problem = checked_balance(source_balance.on_hand, source_balance.reserved)
        if problem:
            blockers.append('Source: ' + problem)
        elif transfer.dispatched_quantity is not None and available < Decimal(str(transfer.dispatched_quantity)):
            blockers.append('Source unreserved stock does not cover dispatch')
    if destination_balance is not None:
        _, problem = checked_balance(destination_balance.on_hand, destination_balance.reserved)
        if problem:
            blockers.append('Destination: ' + problem)
    blockers.append('Requires a matched source-lot plan and destination transfer-lot plan')
    blockers.append('Destination lot remains quarantined pending independent QA clearance')
    if os.getenv('STORES_ATOMIC_TRANSFER_POSTING_ENABLED', 'false').lower() != 'true':
        blockers.append('STORES_ATOMIC_TRANSFER_POSTING_ENABLED is disabled')
    if os.getenv('STORES_LOT_WRITER_CUTOVER', 'false').lower() != 'true':
        blockers.append('STORES_LOT_WRITER_CUTOVER is disabled')
    return {'transfer_id': transfer.id, 'source_project_id': transfer.project_id,
            'destination_project_id': transfer.destination_project_id or transfer.project_id,
            'eligible_for_posting': False, 'inventory_posted': False,
            'physical_stock_readiness': 'Unverified', 'blockers': blockers}


class SourceLotPlanIn(BaseModel):
    source_receipt_lot_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    evidence: str = Field(min_length=3, max_length=4000)


def validate_source_lot_plan(transfer, lot, amount):
    """Fail closed if source lot does not match the exact transfer identity."""
    if transfer.status != 'Received' or transfer.discrepancy_status not in ('Not Required', 'Resolved'):
        raise HTTPException(409, 'Transfer must be fully received and discrepancies closed')
    if transfer.received_quantity != transfer.dispatched_quantity or Decimal(str(transfer.damaged_quantity or 0)) != 0:
        raise HTTPException(409, 'Damaged or partial transfers are not eligible for lot planning')
    if lot.project_id != transfer.project_id or lot.organization_id != transfer.organization_id or lot.warehouse_id != transfer.source_warehouse_id:
        raise HTTPException(409, 'Source receipt lot does not belong to transfer source warehouse')
    if amount != Decimal(str(transfer.quantity)) or amount != Decimal(str(transfer.dispatched_quantity)):
        raise HTTPException(409, 'Source lot plan must exactly cover dispatched transfer quantity')


@router.post('/material-transfers/{transfer_id}/source-lot-plan', status_code=201)
def plan_transfer_source_lot(pid: int, transfer_id: int, data: SourceLotPlanIn,
                             u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Record source provenance only: never post or activate destination stock."""
    _scope(db, u, pid, 'procurement.stock.edit')
    amount = _checked_qty(data.quantity)
    transfer = db.execute(select(StoresTransfer).where(
        StoresTransfer.id == transfer_id, StoresTransfer.project_id == pid,
        StoresTransfer.organization_id == u.organization_id).with_for_update()).scalar_one_or_none()
    if transfer is None:
        raise HTTPException(404, 'Transfer not found')
    existing = db.execute(select(StoresTransferLotLineage).where(
        StoresTransferLotLineage.transfer_id == transfer_id).with_for_update()).scalar_one_or_none()
    if existing:
        if (existing.source_receipt_lot_id == data.source_receipt_lot_id and
            Decimal(str(existing.quantity)) == amount and existing.evidence == data.evidence):
            return {'lineage_id': existing.id, 'status': existing.status, 'inventory_posted': False}
        raise HTTPException(409, 'Transfer already has a different source lot plan')
    lot = db.execute(select(StoresReceiptLot).where(
        StoresReceiptLot.id == data.source_receipt_lot_id,
        StoresReceiptLot.organization_id == u.organization_id,
        StoresReceiptLot.project_id == pid).with_for_update()).scalar_one_or_none()
    if lot is None:
        raise HTTPException(404, 'Source receipt lot not found')
    validate_source_lot_plan(transfer, lot, amount)
    receipt_line = db.get(GoodsReceiptLine, lot.goods_receipt_line_id)
    from app.domains.supply_chain import stock
    material, unit = stock._receipt_item(db, receipt_line) if receipt_line else (None, None)
    if material is None or material.id != transfer.item_id:
        raise HTTPException(409, 'Receipt lot material does not match the transfer item')
    # Existing fully posted movements need explicit attribution before any
    # transfer quantity may be trusted at lot granularity.
    from types import SimpleNamespace
    _require_full_coverage(db, SimpleNamespace(id=pid), transfer.source_warehouse_id, transfer.item_id)
    qa_case = db.execute(select(StoresInspectionCase).where(
        StoresInspectionCase.goods_receipt_line_id == lot.goods_receipt_line_id
    ).with_for_update()).scalar_one_or_none()
    if qa_case is None or qa_case.status not in ('Pending Inspection', 'Disposition Recorded'):
        raise HTTPException(409, 'Current source lot QA approval is missing or revoked')
    qa_accepted = db.execute(select(func.coalesce(func.sum(StoresLotQAAttribution.quantity), 0)).where(
        StoresLotQAAttribution.receipt_lot_id == lot.id,
        StoresLotQAAttribution.inspection_case_id == qa_case.id,
        StoresLotQAAttribution.disposition == 'Accepted',
        StoresLotQAAttribution.case_version_at_entry == qa_case.version
    )).scalar_one()
    accepted = _posting_quantities(db, lot.id, 'Accept')
    outbound = _posting_quantities(db, lot.id, 'Issue', outbound=True)
    returned = _posting_quantities(db, lot.id, 'Return', outbound=True)
    existing_plans = db.execute(select(func.coalesce(func.sum(StoresTransferLotLineage.quantity), 0)).where(
        StoresTransferLotLineage.source_receipt_lot_id == lot.id,
        StoresTransferLotLineage.source_posting_id.is_(None)
    )).scalar_one()
    remaining = accepted - outbound + returned - Decimal(str(existing_plans))
    if accepted > Decimal(str(qa_accepted)):
        raise HTTPException(409, 'Source lot attribution exceeds current QA clearance')
    if amount > remaining or remaining < 0:
        raise HTTPException(409, 'Source receipt lot does not have sufficient attributed quantity')
    row = StoresTransferLotLineage(organization_id=u.organization_id, project_id=pid,
        transfer_id=transfer.id, source_receipt_lot_id=lot.id, quantity=amount,
        status='Planned', evidence=data.evidence, created_by=u.id)
    db.add(row)
    db.flush()
    audit(db, u, 'plan_transfer_source_lot', 'stores_transfers', transfer.id,
          details={'receipt_lot_id': lot.id, 'quantity': str(amount)}, project_id=pid)
    commit(db)
    return {'lineage_id': row.id, 'status': row.status, 'inventory_posted': False}



class DestinationLotPlanIn(BaseModel):
    lot_code: str = Field(min_length=1, max_length=100)
    evidence: str = Field(min_length=3, max_length=4000)


def validate_destination_lot_plan(transfer, lineage):
    """A provenance reference is not a stock credit or an approved QA lot."""
    if transfer.status != 'Received' or transfer.discrepancy_status not in ('Not Required', 'Resolved'):
        raise HTTPException(409, 'Destination receipt and discrepancy resolution required')
    if transfer.destination_custodian_company_id is not None and transfer.custody_confirmed_by is None:
        raise HTTPException(409, 'Destination custody confirmation required')
    if lineage is None or lineage.status != 'Planned' or lineage.source_posting_id is not None:
        raise HTTPException(409, 'An unposted source-lot plan is required')
    if Decimal(str(lineage.quantity)) != Decimal(str(transfer.quantity)):
        raise HTTPException(409, 'Source and destination planned quantities differ')


@router.post('/material-transfers/{transfer_id}/destination-lot-plan', status_code=201)
def plan_transfer_destination_lot(pid: int, transfer_id: int, data: DestinationLotPlanIn,
                                  u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Create immutable destination provenance; never mutate stock or mark QA passed."""
    _scope(db, u, pid, 'procurement.stock.edit')
    transfer = db.execute(select(StoresTransfer).where(
        StoresTransfer.id == transfer_id, StoresTransfer.project_id == pid,
        StoresTransfer.organization_id == u.organization_id).with_for_update()).scalar_one_or_none()
    if transfer is None:
        raise HTTPException(404, 'Transfer not found')
    if (transfer.destination_project_id or pid) != pid:
        raise HTTPException(409, 'Inter-project destination-lot planning requires destination-side authorization integration')
    lineage = db.execute(select(StoresTransferLotLineage).where(
        StoresTransferLotLineage.transfer_id == transfer.id).with_for_update()).scalar_one_or_none()
    validate_destination_lot_plan(transfer, lineage)
    existing = db.execute(select(StoresTransferDestinationLot).where(
        StoresTransferDestinationLot.transfer_id == transfer.id).with_for_update()).scalar_one_or_none()
    lot_code = data.lot_code.strip()
    if not lot_code:
        raise HTTPException(422, 'Destination lot code is required')
    if existing is not None:
        if existing.lot_code == lot_code and existing.evidence == data.evidence:
            return {'destination_lot_id': existing.id, 'status': existing.status, 'inventory_posted': False}
        raise HTTPException(409, 'Destination lot already planned with different values')
    duplicate = db.execute(select(StoresTransferDestinationLot).where(
        StoresTransferDestinationLot.destination_warehouse_id == transfer.destination_warehouse_id,
        StoresTransferDestinationLot.lot_code == lot_code)).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(409, 'Destination lot code already exists in warehouse')
    row = StoresTransferDestinationLot(organization_id=u.organization_id,
        source_project_id=pid, destination_project_id=pid, transfer_id=transfer.id,
        lineage_id=lineage.id, source_receipt_lot_id=lineage.source_receipt_lot_id,
        destination_warehouse_id=transfer.destination_warehouse_id, item_id=transfer.item_id,
        lot_code=lot_code, quantity=lineage.quantity, status='PendingPostingAndQA',
        evidence=data.evidence, created_by=u.id)
    db.add(row)
    db.flush()
    audit(db, u, 'plan_transfer_destination_lot', 'stores_transfers', transfer.id,
          details={'destination_lot_id': row.id, 'source_lot_id': lineage.source_receipt_lot_id,
                   'quantity': str(lineage.quantity)}, project_id=pid)
    commit(db)
    return {'destination_lot_id': row.id, 'status': row.status, 'inventory_posted': False}

@router.get('/material-transfers/{transfer_id}/posting-readiness')
def transfer_posting_readiness(pid: int, transfer_id: int,
                               u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    transfer = db.execute(select(StoresTransfer).where(
        StoresTransfer.id == transfer_id, StoresTransfer.project_id == pid,
        StoresTransfer.organization_id == u.organization_id)).scalar_one_or_none()
    if transfer is None:
        raise HTTPException(404, 'Transfer not found')
    source_balance = db.execute(select(StockBalance).where(
        StockBalance.organization_id == u.organization_id,
        StockBalance.project_id == transfer.project_id,
        StockBalance.warehouse_id == transfer.source_warehouse_id,
        StockBalance.item_id == transfer.item_id)).scalar_one_or_none()
    dest_balance = db.execute(select(StockBalance).where(
        StockBalance.organization_id == u.organization_id,
        StockBalance.project_id == (transfer.destination_project_id or transfer.project_id),
        StockBalance.warehouse_id == transfer.destination_warehouse_id,
        StockBalance.item_id == transfer.item_id)).scalar_one_or_none()
    return evaluate_transfer_posting(transfer, source_balance=source_balance, destination_balance=dest_balance)


def assert_transfer_posting_gate():
    """Never enable automatically based on a successfully built deployment."""
    if (os.getenv('STORES_ATOMIC_TRANSFER_POSTING_ENABLED', 'false').lower() != 'true'
            or os.getenv('STORES_LOT_WRITER_CUTOVER', 'false').lower() != 'true'):
        raise HTTPException(503, 'Atomic transfer posting is disabled pending live PostgreSQL validation')


def _assert_transfer_ready(transfer, lineage, destination):
    if (transfer.destination_project_id or transfer.project_id) != transfer.project_id:
        raise HTTPException(409, 'Inter-project paired stock posting is not supported')
    if transfer.status != 'Received' or transfer.discrepancy_status not in ('Not Required', 'Resolved'):
        raise HTTPException(409, 'Destination receipt and discrepancy resolution are required')
    if transfer.destination_custodian_company_id is not None and transfer.custody_confirmed_by is None:
        raise HTTPException(409, 'Destination custody confirmation required')
    amount = _checked_qty(transfer.quantity)
    if (Decimal(str(transfer.dispatched_quantity or 0)) != amount
            or Decimal(str(transfer.received_quantity or 0)) != amount
            or Decimal(str(transfer.damaged_quantity or 0)) != 0):
        raise HTTPException(409, 'Full, undamaged delivery required')
    if lineage is None or destination is None or lineage.status != 'Planned':
        raise HTTPException(409, 'Both source and destination lot plans are required')
    if lineage.source_posting_id or lineage.destination_posting_id:
        raise HTTPException(409, 'Transfer already posted')
    if (destination.status != 'PendingPostingAndQA' or destination.lineage_id != lineage.id
            or destination.source_receipt_lot_id != lineage.source_receipt_lot_id
            or destination.destination_warehouse_id != transfer.destination_warehouse_id
            or destination.item_id != transfer.item_id
            or Decimal(str(destination.quantity)) != amount
            or Decimal(str(lineage.quantity)) != amount):
        raise HTTPException(409, 'Transfer lot lineage and material quantities are inconsistent')
    return amount


@router.post('/material-transfers/{transfer_id}/post-stock')
def post_transfer_stock(pid: int, transfer_id: int,
                        u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Paired same-project stock posting; never releases destination lot to issue.

    Both stock postings and both stock balances are committed exactly once at
    the end. Any validation or database failure rolls back the complete pair.
    """
    _scope(db, u, pid, 'procurement.stock.edit')
    assert_transfer_posting_gate()
    from .posting_number_lock import lock_stock_posting_number
    for number in sorted((f'TR-{transfer_id}-OUT', f'TR-{transfer_id}-IN')):
        lock_stock_posting_number(db, organization_id=u.organization_id, project_id=pid, number=number)
    transfer = db.execute(select(StoresTransfer).where(
        StoresTransfer.id == transfer_id, StoresTransfer.project_id == pid,
        StoresTransfer.organization_id == u.organization_id).with_for_update()).scalar_one_or_none()
    if transfer is None:
        raise HTTPException(404, 'Transfer not found')
    lineage = db.execute(select(StoresTransferLotLineage).where(
        StoresTransferLotLineage.transfer_id == transfer.id).with_for_update()).scalar_one_or_none()
    destination = db.execute(select(StoresTransferDestinationLot).where(
        StoresTransferDestinationLot.transfer_id == transfer.id).with_for_update()).scalar_one_or_none()
    amount = _assert_transfer_ready(transfer, lineage, destination)
    # Lock the source lot and current QA case before all inventory changes.
    lot = db.execute(select(StoresReceiptLot).where(
        StoresReceiptLot.id == lineage.source_receipt_lot_id,
        StoresReceiptLot.project_id == pid, StoresReceiptLot.organization_id == u.organization_id,
        StoresReceiptLot.warehouse_id == transfer.source_warehouse_id).with_for_update()).scalar_one_or_none()
    if lot is None:
        raise HTTPException(409, 'Source lot no longer matches the transfer')
    line = db.get(GoodsReceiptLine, lot.goods_receipt_line_id)
    item, unit = stock._receipt_item(db, line) if line else (None, None)
    if item is None or item.id != transfer.item_id or not unit:
        raise HTTPException(409, 'Source lot material and unit mismatch')
    qa = db.execute(select(StoresInspectionCase).where(
        StoresInspectionCase.goods_receipt_line_id == line.id).with_for_update()).scalar_one_or_none()
    if qa is None or qa.status not in ('Pending Inspection', 'Disposition Recorded'):
        raise HTTPException(409, 'Source lot has no current QA clearance')
    qa_accepted = Decimal(str(db.execute(select(func.coalesce(func.sum(StoresLotQAAttribution.quantity), 0)).where(
        StoresLotQAAttribution.receipt_lot_id == lot.id,
        StoresLotQAAttribution.inspection_case_id == qa.id,
        StoresLotQAAttribution.disposition == 'Accepted',
        StoresLotQAAttribution.case_version_at_entry == qa.version)).scalar_one()))
    _require_full_coverage(db, type('ProjectRef', (), {'id': pid})(), transfer.source_warehouse_id, transfer.item_id)
    accepted = _posting_quantities(db, lot.id, 'Accept')
    issued = _posting_quantities(db, lot.id, 'Issue', outbound=True)
    returned = _posting_quantities(db, lot.id, 'Return', outbound=True)
    already_transferred = Decimal(str(db.execute(select(func.coalesce(func.sum(StoresTransferLotLineage.quantity), 0)).where(
        StoresTransferLotLineage.source_receipt_lot_id == lot.id,
        StoresTransferLotLineage.status == 'Posted')).scalar_one()))
    planned_elsewhere = Decimal(str(db.execute(select(func.coalesce(func.sum(StoresTransferLotLineage.quantity), 0)).where(
        StoresTransferLotLineage.source_receipt_lot_id == lot.id,
        StoresTransferLotLineage.status == 'Planned',
        StoresTransferLotLineage.id != lineage.id)).scalar_one()))
    if accepted > qa_accepted or accepted - issued + returned - already_transferred - planned_elsewhere < amount:
        raise HTTPException(409, 'Insufficient source lot quantity under current QA attribution')
    # Deterministic warehouse lock order avoids competing transfer deadlocks.
    project = db.get(Project, pid)
    balances = {}
    for warehouse in sorted((transfer.source_warehouse_id, transfer.destination_warehouse_id)):
        balances[warehouse] = stock._lock_balance(db, u, project, warehouse, transfer.item_id, unit)
    src, dst = balances[transfer.source_warehouse_id], balances[transfer.destination_warehouse_id]
    available, err = checked_balance(src.on_hand, src.reserved)
    if err or available < amount:
        raise HTTPException(409, 'Insufficient consistent source unreserved stock')
    _, err = checked_balance(dst.on_hand, dst.reserved)
    if err:
        raise HTTPException(409, 'Destination aggregate balance is inconsistent')
    if transfer.source_warehouse_id == transfer.destination_warehouse_id:
        raise HTTPException(409, 'Source and destination warehouses must differ')
    out_number = f'TR-{transfer.id}-OUT'
    in_number = f'TR-{transfer.id}-IN'
    # Posting-number locks were acquired before row locks above.
    out_post = stock._save(db, u, project, 'TransferOut', out_number, transfer.source_warehouse_id,
                           f'Transfer {transfer.id} to warehouse {transfer.destination_warehouse_id}', '', None, None)
    out_line = StockPostingLine(posting_id=out_post.id, item_id=transfer.item_id, quantity=amount, unit=unit)
    db.add(out_line)
    db.flush()
    db.add(StoresOutboundLotAllocation(organization_id=u.organization_id, project_id=pid,
        stock_posting_line_id=out_line.id, receipt_lot_id=lot.id,
        quantity=amount, reason=f'Transfer {transfer.id}', created_by=u.id))
    in_post = stock._save(db, u, project, 'TransferIn', in_number, transfer.destination_warehouse_id,
                          f'Transfer {transfer.id} from warehouse {transfer.source_warehouse_id}', '', None, out_post.id)
    db.add(StockPostingLine(posting_id=in_post.id, item_id=transfer.item_id,
                            source_line_id=out_line.id, quantity=amount, unit=unit))
    src.on_hand = Decimal(str(src.on_hand)) - amount
    dst.on_hand = Decimal(str(dst.on_hand)) + amount
    src.version += 1
    dst.version += 1
    lineage.source_posting_id = out_post.id
    lineage.destination_posting_id = in_post.id
    lineage.status = 'Posted'
    destination.status = 'PostedPendingQA'
    audit(db, u, 'post_transfer_stock_pair', 'stores_transfers', transfer.id,
          details={'source_posting_id': out_post.id, 'destination_posting_id': in_post.id,
                   'destination_lot_id': destination.id, 'quantity': str(amount),
                   'destination_lot_available_for_issue': False}, project_id=pid)
    commit(db)
    return {'transfer_id': transfer.id, 'source_posting_id': out_post.id,
            'destination_posting_id': in_post.id, 'quantity': str(amount),
            'destination_lot_id': destination.id, 'destination_qa_status': 'Pending',
            'available_for_issue': False}

