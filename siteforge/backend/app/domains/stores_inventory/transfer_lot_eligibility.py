"""Read-only transfer-derived lot eligibility; never implies available stock."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.models import User
from .models import StoresTransfer, StoresTransferDestinationLot
from .transfer_qa_reconciliation import _scope, _load_pair, reconcile_transfer_pair

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Transfer Lot Eligibility'])


def _eligibility(transfer, destination, reconciliation):
    qa_accepted = bool(destination and destination.status == 'QAAcceptedPendingActivation')
    blockers = list(reconciliation.get('blockers') or [])
    if not qa_accepted:
        blockers.append('DESTINATION_QA_NOT_ACCEPTED')
    blockers.extend(('TRANSFER_DERIVED_RESERVATION_ALLOCATION_NOT_IMPLEMENTED',
                     'TRANSFER_DERIVED_ISSUE_POSTING_NOT_IMPLEMENTED',
                     'LIVE_DATABASE_TRANSACTION_VALIDATION_PENDING'))
    return {
        'transfer_id': transfer.id,
        'destination_lot_id': destination.id if destination else None,
        'destination_warehouse_id': transfer.destination_warehouse_id,
        'project_id': transfer.project_id,
        'item_id': transfer.item_id,
        'quantity': str(destination.quantity) if destination else None,
        'destination_qa_status': destination.status if destination else 'Missing',
        'paired_posting_balanced': bool(reconciliation.get('balanced')),
        'qa_evidence_accepted': qa_accepted,
        'reservable': False, 'issuable': False, 'physical_stock_readiness': 'Unverified',
        'blockers': list(dict.fromkeys(blockers)),
    }


@router.get('/material-transfers/{transfer_id}/destination-lot-eligibility')
def destination_lot_eligibility(pid: int, transfer_id: int,
                                u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.view')
    transfer = db.execute(select(StoresTransfer).where(
        StoresTransfer.id == transfer_id,
        StoresTransfer.project_id == pid,
        StoresTransfer.organization_id == u.organization_id)).scalar_one_or_none()
    if transfer is None:
        raise HTTPException(404, 'Transfer not found')
    lineage, destination, source, target, outgoing, incoming = _load_pair(db, transfer, u.organization_id)
    return _eligibility(transfer, destination,
        reconcile_transfer_pair(transfer, lineage, destination, source, target, outgoing, incoming))
