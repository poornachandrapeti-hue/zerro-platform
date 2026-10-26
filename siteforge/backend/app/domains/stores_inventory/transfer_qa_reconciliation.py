"""Phase 6 transfer posting reconciliation and fail-closed destination QA hold.

This module does NOT release transfer-derived material for issue: existing lot
reservation/issue paths do not yet consume transfer-derived QA provenance.
"""
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.router import audit, commit
from app.domains.supply_chain.models import StockPosting, StockPostingLine
from .material_handovers import _scope
from .models import StoresTransfer, StoresTransferLotLineage, StoresTransferDestinationLot

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Transfer QA and Reconciliation'])


def reconcile_transfer_pair(transfer, lineage, destination, source, target, source_lines, target_lines):
    """Fail closed when either leg, posting identity or quantities disagree."""
    errors = []
    if lineage is None or destination is None or lineage.status != 'Posted':
        errors.append('TRANSFER_LINEAGE_NOT_POSTED')
    if source is None or target is None:
        errors.append('TRANSFER_POSTING_PAIR_INCOMPLETE')
    else:
        if (source.kind != 'TransferOut' or target.kind != 'TransferIn' or
                source.status != 'Posted' or target.status != 'Posted' or
                target.source_posting_id != source.id or
                (lineage is None or source.id != lineage.source_posting_id or target.id != lineage.destination_posting_id)):
            errors.append('TRANSFER_POSTING_LINK_MISMATCH')
        if (source.project_id != transfer.project_id or target.project_id != transfer.project_id or
                source.organization_id != transfer.organization_id or target.organization_id != transfer.organization_id or
                source.warehouse_id != transfer.source_warehouse_id or target.warehouse_id != transfer.destination_warehouse_id):
            errors.append('TRANSFER_POSTING_SCOPE_MISMATCH')
        if len(source_lines) != 1 or len(target_lines) != 1:
            errors.append('TRANSFER_POSTING_LINES_INCOMPLETE')
        else:
            outgoing, incoming = source_lines[0], target_lines[0]
            try:
                expected = Decimal(str(transfer.quantity))
                q_out = Decimal(str(outgoing.quantity))
                q_in = Decimal(str(incoming.quantity))
                if (not all(q.is_finite() for q in (expected, q_out, q_in)) or expected <= 0 or
                        q_out != expected or q_in != expected or
                        outgoing.item_id != transfer.item_id or incoming.item_id != transfer.item_id or
                        outgoing.unit != incoming.unit or incoming.source_line_id != outgoing.id):
                    errors.append('TRANSFER_POSTING_QUANTITY_OR_ITEM_MISMATCH')
            except (InvalidOperation, ValueError, TypeError):
                errors.append('TRANSFER_POSTING_INVALID_QUANTITY')
    if destination is not None and lineage is not None:
        if (destination.lineage_id != lineage.id or destination.source_receipt_lot_id != lineage.source_receipt_lot_id or
                destination.item_id != transfer.item_id or destination.destination_warehouse_id != transfer.destination_warehouse_id or
                Decimal(str(destination.quantity)) != Decimal(str(transfer.quantity))):
            errors.append('TRANSFER_DESTINATION_LOT_MISMATCH')
    # QA acceptance is not stock availability: transferred lots are not yet
    # addressable by the GRN-only reservation / issue services.
    qa_review_complete = destination is not None and destination.status == 'QAAcceptedPendingActivation'
    return {'transfer_id': transfer.id, 'balanced': not errors, 'blockers': errors,
            'destination_qa_status': destination.status if destination else 'Missing',
            'destination_qa_review_complete': qa_review_complete,
            'availability_blockers': ([] if not qa_review_complete else
               ['TRANSFER_DERIVED_LOT_RESERVATION_NOT_SUPPORTED', 'TRANSFER_DERIVED_LOT_ISSUE_NOT_SUPPORTED'])
               + ['LIVE_TRANSFER_POSTING_NOT_VALIDATED'],
            'available_for_issue': False, 'physical_stock_readiness': 'Unverified'}


def _load_pair(db, transfer, organization_id):
    lineage = db.execute(select(StoresTransferLotLineage).where(
        StoresTransferLotLineage.transfer_id == transfer.id,
        StoresTransferLotLineage.organization_id == organization_id)).scalar_one_or_none()
    destination = db.execute(select(StoresTransferDestinationLot).where(
        StoresTransferDestinationLot.transfer_id == transfer.id,
        StoresTransferDestinationLot.organization_id == organization_id)).scalar_one_or_none()
    source = db.get(StockPosting, lineage.source_posting_id) if lineage and lineage.source_posting_id else None
    target = db.get(StockPosting, lineage.destination_posting_id) if lineage and lineage.destination_posting_id else None
    source_lines = db.execute(select(StockPostingLine).where(StockPostingLine.posting_id == source.id)).scalars().all() if source else []
    target_lines = db.execute(select(StockPostingLine).where(StockPostingLine.posting_id == target.id)).scalars().all() if target else []
    return lineage, destination, source, target, source_lines, target_lines


@router.get('/material-transfers/{transfer_id}/ledger-reconciliation')
def transfer_ledger_reconciliation(pid: int, transfer_id: int,
                                   u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.view')
    transfer = db.execute(select(StoresTransfer).where(
        StoresTransfer.id == transfer_id, StoresTransfer.project_id == pid,
        StoresTransfer.organization_id == u.organization_id)).scalar_one_or_none()
    if transfer is None:
        raise HTTPException(404, 'Transfer not found')
    return reconcile_transfer_pair(transfer, *_load_pair(db, transfer, u.organization_id))


class DestinationQAReviewIn(BaseModel):
    decision: str = Field(pattern='^(Quarantined|Rejected)$')
    evidence: str = Field(min_length=3, max_length=4000)


@router.post('/material-transfers/{transfer_id}/destination-qa-hold')
def destination_qa_hold(pid: int, transfer_id: int, data: DestinationQAReviewIn,
                        u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Independent QA may quarantine/reject; no premature 'Accepted' release."""
    _scope(db, u, pid, 'quality.edit')
    transfer = db.execute(select(StoresTransfer).where(
        StoresTransfer.id == transfer_id, StoresTransfer.project_id == pid,
        StoresTransfer.organization_id == u.organization_id).with_for_update()).scalar_one_or_none()
    if transfer is None:
        raise HTTPException(404, 'Transfer not found')
    if u.id in (transfer.created_by, transfer.dispatched_by, transfer.received_by):
        raise HTTPException(403, 'Independent QA reviewer required')
    lineage, destination, source, target, outgoing, incoming = _load_pair(db, transfer, u.organization_id)
    result = reconcile_transfer_pair(transfer, lineage, destination, source, target, outgoing, incoming)
    if not result['balanced'] or destination is None or destination.status != 'PostedPendingQA':
        raise HTTPException(409, 'Transfer posting reconciliation and pending QA status required')
    destination.status = data.decision
    audit(db, u, 'transfer_destination_qa_hold', 'stores_transfers', transfer.id,
          details={'destination_lot_id': destination.id, 'decision': data.decision,
                   'evidence': data.evidence, 'available_for_issue': False}, project_id=pid)
    commit(db)
    return {'transfer_id': transfer.id, 'destination_lot_id': destination.id,
            'status': destination.status, 'available_for_issue': False}


class DestinationQAAcceptIn(BaseModel):
    evidence: str = Field(min_length=3, max_length=4000)


@router.post('/material-transfers/{transfer_id}/destination-qa-accept')
def destination_qa_accept(pid: int, transfer_id: int, data: DestinationQAAcceptIn,
                          u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Record independent QA acceptance WITHOUT making transferred stock available.

    A separate validated downstream lot-allocation capability is required
    before reservation or issue can consume this transfer-derived provenance.
    """
    _scope(db, u, pid, 'quality.edit')
    transfer = db.execute(select(StoresTransfer).where(
        StoresTransfer.id == transfer_id, StoresTransfer.project_id == pid,
        StoresTransfer.organization_id == u.organization_id).with_for_update()).scalar_one_or_none()
    if transfer is None:
        raise HTTPException(404, 'Transfer not found')
    if u.id in (transfer.created_by, transfer.dispatched_by, transfer.received_by):
        raise HTTPException(403, 'Independent QA reviewer required')
    lineage, destination, source, target, outgoing, incoming = _load_pair(db, transfer, u.organization_id)
    result = reconcile_transfer_pair(transfer, lineage, destination, source, target, outgoing, incoming)
    if not result['balanced'] or destination is None or destination.status != 'PostedPendingQA':
        raise HTTPException(409, 'Balanced posted transfer and pending destination QA required')
    destination.status = 'QAAcceptedPendingActivation'
    audit(db, u, 'transfer_destination_qa_accept', 'stores_transfers', transfer.id,
          details={'destination_lot_id': destination.id, 'evidence': data.evidence,
                   'available_for_issue': False, 'activation_required': True}, project_id=pid)
    commit(db)
    return {'transfer_id': transfer.id, 'destination_lot_id': destination.id,
            'status': destination.status, 'available_for_issue': False,
            'activation_required': True}
