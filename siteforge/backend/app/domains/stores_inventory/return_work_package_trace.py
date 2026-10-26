"""Read-only construction work-package issue/return trace; not a stock balance."""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from .material_handovers import _scope
from .models import StoresMaterialHandover, StoresMaterialReturn, StoresMaterialRequest, StoresTransferIssueAllocation, StoresTransferReturnAllocation
from app.domains.supply_chain.models import StockPosting, StockPostingLine

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Return Work Package Trace'])


def _quantity(value):
    number = Decimal(str(value))
    if not number.is_finite() or number < 0:
        raise HTTPException(409, 'Invalid issue/return quantity in source records')
    return number


def build_work_package_trace(handovers, requests, returns, issue_lines, postings, transfer_issues=(), transfer_returns=(), return_lines=()):
    """Only POSTED Return movements reduce outstanding ledger-issued quantity.

    A pending/QA-accepted custody return is NOT a ledger return. Handover receipt
    is not a verified construction consumption or installation event.
    """
    request_by_id = {r.id: r for r in requests}
    return_by_handover = {r.handover_id: r for r in returns}
    line_by_id = {r.id: r for r in issue_lines}
    posting_by_id = {p.id: p for p in postings}
    transfer_issue_by_line = {a.stock_posting_line_id: a for a in transfer_issues}
    transfer_return_by_line = {a.stock_posting_line_id: a for a in transfer_returns}
    return_lines_by_posting = {}
    for line in return_lines:
        return_lines_by_posting.setdefault(line.posting_id, []).append(line)
    output = []
    for handover in handovers:
        req = request_by_id.get(handover.material_request_id)
        line = line_by_id.get(handover.stock_posting_line_id)
        issue = posting_by_id.get(line.posting_id) if line else None
        if req is None or line is None or issue is None or issue.kind != 'Issue' or issue.status != 'Posted':
            continue  # do not invent missing source links
        issued = _quantity(line.quantity)
        if issued == 0 or _quantity(handover.dispatched_quantity) != issued:
            raise HTTPException(409, 'Handover quantity and posted issue differ')
        transfer_issue = transfer_issue_by_line.get(line.id)
        if transfer_issue and _quantity(transfer_issue.quantity) != issued:
            raise HTTPException(409, 'Transfer issue provenance quantity does not match ledger issue')
        ret = return_by_handover.get(handover.id)
        posted_return = Decimal('0')
        custody_pending = Decimal('0')
        if ret:
            if ret.stock_posting_id is not None:
                rp = posting_by_id.get(ret.stock_posting_id)
                if rp is None or rp.kind != 'Return' or rp.status != 'Posted':
                    raise HTTPException(409, 'Recorded return posting is not a posted ledger return')
                posted_return = _quantity(ret.received_quantity)
                if transfer_issue:
                    matching_lines = return_lines_by_posting.get(rp.id, [])
                    if len(matching_lines) != 1:
                        raise HTTPException(409, 'Transfer return must have exactly one ledger posting line')
                    return_line = matching_lines[0]
                    allocation = transfer_return_by_line.get(return_line.id)
                    if (allocation is None or allocation.original_issue_line_id != line.id
                        or allocation.transfer_destination_lot_id != transfer_issue.transfer_destination_lot_id
                        or _quantity(allocation.quantity) != posted_return
                        or _quantity(return_line.quantity) != posted_return):
                        raise HTTPException(409, 'Transfer return provenance conflicts with original issue')
            else:
                custody_pending = _quantity(ret.received_quantity if ret.received_quantity is not None else ret.requested_quantity)
        if posted_return > issued:
            raise HTTPException(409, 'Posted returns exceed original issued quantity')
        output.append(dict(
            work_package_id=req.work_package_id, planning_wbs_id=req.planning_wbs_id,
            requirement_line_id=req.requirement_line_id, material_request_id=req.id,
            handover_id=handover.id, issue_posting_id=issue.id,
            return_id=ret.id if ret else None, return_status=ret.status if ret else None,
            item_id=line.item_id, unit=line.unit,
            issued_quantity=str(issued), ledger_posted_return_quantity=str(posted_return),
            ledger_outstanding_quantity=str(issued - posted_return),
            pending_custody_return_quantity=str(custody_pending),
            handover_received_quantity=str(handover.received_quantity) if handover.received_quantity is not None else None,
            issue_lot_source='Transfer' if transfer_issue else 'GRN / legacy unverified',
            transfer_destination_lot_id=transfer_issue.transfer_destination_lot_id if transfer_issue else None,
            return_provenance_verified=bool(transfer_issue and ret and ret.stock_posting_id is not None),
            traceability='Transfer returns provenance-checked where mapped; GRN/legacy provenance not fully verified',
            construction_consumption_verified=False,
        ))
    return output


def load_transfer_trace_provenance(db, pid, organization_id, issue_lines, returns):
    """Fetch exact project-scoped transfer provenance, including posted return lines."""
    issue_ids = [line.id for line in issue_lines]
    return_posting_ids = [r.stock_posting_id for r in returns if r.stock_posting_id is not None]
    t_issues = db.execute(select(StoresTransferIssueAllocation).where(
        StoresTransferIssueAllocation.organization_id == organization_id,
        StoresTransferIssueAllocation.project_id == pid,
        StoresTransferIssueAllocation.stock_posting_line_id.in_(issue_ids))).scalars().all() if issue_ids else []
    return_lines = db.execute(select(StockPostingLine).where(
        StockPostingLine.posting_id.in_(return_posting_ids))).scalars().all() if return_posting_ids else []
    t_returns = db.execute(select(StoresTransferReturnAllocation).where(
        StoresTransferReturnAllocation.organization_id == organization_id,
        StoresTransferReturnAllocation.project_id == pid,
        StoresTransferReturnAllocation.stock_posting_line_id.in_([line.id for line in return_lines]))).scalars().all() if return_lines else []
    return t_issues, t_returns, return_lines


@router.get('/material-returns/construction-trace')
def construction_return_trace(pid: int, work_package_id: int | None = None,
    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Read model of issued vs posted returned quantity for linked work packages."""
    _scope(db, u, pid, 'stores.requests.view')
    if work_package_id is not None and work_package_id <= 0:
        raise HTTPException(422, 'work_package_id must be positive')
    request_query = select(StoresMaterialRequest).where(
        StoresMaterialRequest.organization_id == u.organization_id,
        StoresMaterialRequest.project_id == pid)
    if work_package_id is not None:
        request_query = request_query.where(StoresMaterialRequest.work_package_id == work_package_id)
    requests = db.execute(request_query).scalars().all()
    if not u.organization_admin:
        requests = [r for r in requests if r.created_by == u.id]
    req_ids = [r.id for r in requests]
    if not req_ids:
        return {'records': [], 'coverage': 'Request-linked handovers only', 'inventory_verified': False,
                'construction_consumption_verified': False}
    handovers = db.execute(select(StoresMaterialHandover).where(
        StoresMaterialHandover.organization_id == u.organization_id,
        StoresMaterialHandover.project_id == pid,
        StoresMaterialHandover.material_request_id.in_(req_ids))).scalars().all()
    if not handovers:
        return {'records': [], 'coverage': 'Request-linked handovers only', 'inventory_verified': False,
                'construction_consumption_verified': False}
    returns = db.execute(select(StoresMaterialReturn).where(
        StoresMaterialReturn.organization_id == u.organization_id,
        StoresMaterialReturn.project_id == pid,
        StoresMaterialReturn.handover_id.in_([h.id for h in handovers]))).scalars().all()
    lines = db.execute(select(StockPostingLine).where(
        StockPostingLine.id.in_([h.stock_posting_line_id for h in handovers]))).scalars().all()
    posting_ids = {l.posting_id for l in lines} | {r.stock_posting_id for r in returns if r.stock_posting_id is not None}
    postings = db.execute(select(StockPosting).where(
        StockPosting.id.in_(posting_ids), StockPosting.organization_id == u.organization_id,
        StockPosting.project_id == pid)).scalars().all()
    provenance = load_transfer_trace_provenance(db, pid, u.organization_id, lines, returns)
    records = build_work_package_trace(handovers, requests, returns, lines, postings, *provenance)
    return {'records': records, 'coverage': 'Request-linked, posted source issues with handovers only; legacy or unmapped movements may be missing',
            'inventory_verified': False, 'construction_consumption_verified': False,
            'note': 'Outstanding = issued quantity minus ledger-posted returns, not site usage or installed quantity.'}
