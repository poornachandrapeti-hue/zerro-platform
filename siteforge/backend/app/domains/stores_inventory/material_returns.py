"""Phase 5 material returns: custody, QA and explicitly gated lot-aware ledger posting."""
import os
import hmac
from datetime import date, datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.router import audit, commit
from .material_handovers import _scope
from .models import StoresMaterialReturn, StoresMaterialHandover, StoresMaterialRequest, StoresOutboundLotAllocation, StoreLocation, StoresConstructionMaterialUsage, StoresTransferIssueAllocation, StoresTransferReturnAllocation, StoresTransferDestinationLot
from app.domains.supply_chain.models import StockPosting, StockPostingLine
from app.domains.supply_chain import stock
from app.domains.supply_chain.service import _amount, _event

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Material Returns'])

class ReturnPlacementIn(BaseModel):
    version: int = Field(ge=1)
    location_id: int = Field(gt=0)
    evidence: str = Field(min_length=3, max_length=4000)

class ReturnRequestIn(BaseModel):
    handover_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    condition: str = Field(pattern='^(Unused|Damaged|Surplus)$')
    reason: str = Field(min_length=3, max_length=4000)

class ReturnReceiptIn(BaseModel):
    version: int = Field(ge=1)
    received_quantity: Decimal = Field(gt=0, decimal_places=3)
    evidence: str = Field(min_length=3, max_length=4000)

class ReturnQAIn(BaseModel):
    version: int = Field(ge=1)
    decision: str = Field(pattern='^(Accepted|Rejected|Quarantined)$')
    evidence: str = Field(min_length=3, max_length=4000)

def payload(row):
    return dict(id=row.id, handover_id=row.handover_id, requested_quantity=str(row.requested_quantity),
        received_quantity=str(row.received_quantity) if row.received_quantity is not None else None,
        condition=row.condition, reason=row.reason, status=row.status, version=row.version,
        submitted_by=row.submitted_by, received_by=row.received_by, qa_by=row.qa_by,
        receipt_evidence=row.receipt_evidence, qa_decision=row.qa_decision, qa_evidence=row.qa_evidence,
        stock_posted=row.stock_posting_id is not None, stock_posting_id=row.stock_posting_id,
        location_id=row.return_location_id, placement_evidence=row.placement_evidence,
        placement_by=row.placement_by,
        inventory_readiness='Unverified')

def validate_return_quantity(acknowledged_qty, return_qty):
    available, qty = Decimal(str(acknowledged_qty)), Decimal(str(return_qty))
    if not available.is_finite() or not qty.is_finite() or available <= 0 or qty <= 0 or qty > available:
        raise HTTPException(422, 'Return must be positive and no greater than contractor-received quantity')

def _record(db, pid, u, rid, lock=False):
    q = select(StoresMaterialReturn).where(StoresMaterialReturn.id == rid,
        StoresMaterialReturn.project_id == pid, StoresMaterialReturn.organization_id == u.organization_id)
    record = db.execute(q.with_for_update() if lock else q).scalar_one_or_none()
    if record is None:
        raise HTTPException(404, 'Return not found')
    return record

@router.post('/material-returns', status_code=201)
def submit_return(pid: int, data: ReturnRequestIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'stores.requests.create')
    h = db.execute(select(StoresMaterialHandover).where(
        StoresMaterialHandover.id == data.handover_id, StoresMaterialHandover.organization_id == u.organization_id,
        StoresMaterialHandover.project_id == pid).with_for_update()).scalar_one_or_none()
    if not h:
        raise HTTPException(404, 'Handover not found')
    req = db.get(StoresMaterialRequest, h.material_request_id)
    if not req or req.project_id != pid or req.organization_id != u.organization_id or req.created_by != u.id:
        raise HTTPException(403, 'Only the original material requester may return this handover')
    if h.status not in ('Acknowledged', 'Resolved') or h.received_quantity is None:
        raise HTTPException(409, 'Handover acknowledgment and discrepancy review must be complete')
    validate_return_quantity(h.received_quantity, data.quantity)
    if db.execute(select(StoresMaterialReturn.id).where(StoresMaterialReturn.handover_id == h.id)).first():
        raise HTTPException(409, 'A return request already exists for this handover')
    row = StoresMaterialReturn(organization_id=u.organization_id, project_id=pid,
        handover_id=h.id, requested_quantity=data.quantity, condition=data.condition,
        reason=data.reason.strip(), submitted_by=u.id, status='Submitted')
    db.add(row); db.flush()
    audit(db, u, 'submit_material_return', 'stores_material_returns', row.id, project_id=pid)
    commit(db)
    return payload(row)

@router.get('/material-returns')
def list_returns(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'stores.requests.view')
    rows = db.execute(select(StoresMaterialReturn).where(
        StoresMaterialReturn.organization_id == u.organization_id, StoresMaterialReturn.project_id == pid
    ).order_by(StoresMaterialReturn.id.desc()).limit(300)).scalars().all()
    if not u.organization_admin:
        rows = [r for r in rows if r.submitted_by == u.id]
    return {'records':[payload(r) for r in rows]}

@router.post('/material-returns/{return_id}/receive')
def receive_return(pid: int, return_id: int, data: ReturnReceiptIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    r = _record(db, pid, u, return_id, lock=True)
    if r.status != 'Submitted' or r.version != data.version:
        raise HTTPException(409, 'Return already received or stale version')
    if u.id == r.submitted_by:
        raise HTTPException(403, 'Return requester cannot verify Stores receipt')
    validate_return_quantity(r.requested_quantity, data.received_quantity)
    r.received_quantity = data.received_quantity
    r.receipt_evidence = data.evidence.strip()
    r.received_by = u.id
    r.status = 'Awaiting QA'
    r.version += 1
    audit(db, u, 'receive_material_return', 'stores_material_returns', r.id, project_id=pid)
    commit(db)
    return payload(r)

@router.post('/material-returns/{return_id}/qa-disposition')
def qa_return(pid: int, return_id: int, data: ReturnQAIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'quality.edit')
    r = _record(db, pid, u, return_id, lock=True)
    if r.status != 'Awaiting QA' or r.version != data.version:
        raise HTTPException(409, 'Return has no pending QA decision or stale version')
    if u.id in (r.submitted_by, r.received_by):
        raise HTTPException(403, 'Independent QA reviewer required')
    r.qa_decision = data.decision
    r.qa_evidence = data.evidence.strip()
    r.qa_by = u.id
    r.status = 'QA ' + data.decision
    r.version += 1
    audit(db, u, 'qa_material_return', 'stores_material_returns', r.id, project_id=pid)
    commit(db)
    return payload(r)


def _return_source_warehouse(db, pid, organization_id, row):
    handover = db.execute(select(StoresMaterialHandover).where(
        StoresMaterialHandover.id == row.handover_id,
        StoresMaterialHandover.project_id == pid,
        StoresMaterialHandover.organization_id == organization_id)).scalar_one_or_none()
    if handover is None:
        raise HTTPException(409, 'Return handover is missing')
    line = db.get(StockPostingLine, handover.stock_posting_line_id)
    posting = db.get(StockPosting, line.posting_id) if line else None
    if (posting is None or posting.project_id != pid or posting.organization_id != organization_id
            or posting.kind != 'Issue' or posting.status != 'Posted'):
        raise HTTPException(409, 'A valid posted source issue is required')
    return posting.warehouse_id


def _validate_return_location(location, *, project_id, organization_id, warehouse_id):
    if (location is None or location.project_id != project_id
            or location.organization_id != organization_id or location.warehouse_id != warehouse_id
            or not location.active or location.location_type != 'Bin'):
        raise HTTPException(422, 'Active bin within the original issue warehouse is required')


@router.post('/material-returns/{return_id}/placement')
def set_return_placement(pid: int, return_id: int, data: ReturnPlacementIn,
    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Custody/bin assignment only; stock balance remains unchanged."""
    _scope(db, u, pid, 'procurement.stock.edit')
    record = _record(db, pid, u, return_id, lock=True)
    if record.status != 'QA Accepted' or record.qa_decision != 'Accepted' or record.version != data.version:
        raise HTTPException(409, 'Current accepted QA decision and version required')
    if record.stock_posting_id is not None:
        raise HTTPException(409, 'Posted returns cannot be relocated through custody placement')
    if u.id in (record.submitted_by, record.received_by, record.qa_by):
        raise HTTPException(403, 'Independent Stores placement operator required')
    warehouse_id = _return_source_warehouse(db, pid, u.organization_id, record)
    location = db.execute(select(StoreLocation).where(StoreLocation.id == data.location_id).with_for_update()).scalar_one_or_none()
    _validate_return_location(location, project_id=pid, organization_id=u.organization_id, warehouse_id=warehouse_id)
    record.return_location_id = location.id
    record.placement_evidence = data.evidence.strip()
    record.placement_by = u.id
    record.version += 1
    audit(db, u, 'place_material_return', 'stores_material_returns', record.id, project_id=pid)
    commit(db)
    return payload(record)


@router.get('/material-returns/reconciliation')
def return_reconciliation(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Read-only custody-to-ledger exceptions; NOT an inventory/bin balance."""
    _scope(db, u, pid, 'procurement.stock.edit')
    records = db.execute(select(StoresMaterialReturn).where(
        StoresMaterialReturn.project_id == pid, StoresMaterialReturn.organization_id == u.organization_id)
        .order_by(StoresMaterialReturn.id.desc()).limit(500)).scalars().all()
    result = []
    for row in records:
        if row.status == 'QA Accepted' and row.return_location_id is None:
            reason = 'Awaiting bin placement'
        elif row.status == 'QA Accepted' and row.stock_posting_id is None:
            reason = 'Awaiting gated ledger posting'
        elif row.stock_posting_id is not None:
            reason = 'Posted reference recorded; physical reconciliation not verified'
        else:
            reason = 'Custody or QA workflow pending / rejected'
        result.append({'return_id': row.id, 'status': row.status, 'location_id': row.return_location_id,
                       'stock_posting_id': row.stock_posting_id, 'reconciliation_state': reason})
    return {'records': result, 'ledger_verified': False, 'location_stock_balance_available': False,
            'note': 'Bin assignment is custody metadata, not a separate inventory ledger.'}


def summarize_return_exceptions(records):
    """Conservative custody summary; never represents verified inventory quantities."""
    states = {"awaiting_stores_receipt": 0, "awaiting_qa": 0,
              "qa_quarantined": 0, "qa_rejected": 0,
              "awaiting_bin_placement": 0, "awaiting_gated_posting": 0,
              "posted_unverified": 0}
    exceptions = []
    for r in records:
        if r.stock_posting_id is not None:
            kind = 'posted_unverified'
        elif r.status == 'Submitted':
            kind = 'awaiting_stores_receipt'
        elif r.status == 'Awaiting QA':
            kind = 'awaiting_qa'
        elif r.status == 'QA Quarantined':
            kind = 'qa_quarantined'
        elif r.status == 'QA Rejected':
            kind = 'qa_rejected'
        elif r.status == 'QA Accepted' and r.return_location_id is None:
            kind = 'awaiting_bin_placement'
        elif r.status == 'QA Accepted':
            kind = 'awaiting_gated_posting'
        else:
            # Unknown states must not be counted as stock-ready.
            kind = 'unknown_state'
        if kind in states:
            states[kind] += 1
        exceptions.append({'return_id': r.id, 'handover_id': r.handover_id,
                           'status': r.status, 'exception_code': kind,
                           'stock_posting_id': r.stock_posting_id})
    return {'counts': states, 'total_records': len(records), 'exceptions': exceptions,
            'physical_stock_readiness': 'Unverified', 'ledger_reconciled': False,
            'coverage': 'Most recent 500 project returns only; not an all-time total'}


# A review task follows the custody exception; it is not a second return state or ledger.
RETURN_EXCEPTION_TASK_TYPE = 'stores.material_return.exception_review'


class ReturnExceptionAssignIn(BaseModel):
    owner_id: int = Field(gt=0)


class ReturnExceptionResolveIn(BaseModel):
    task_version: int = Field(ge=1)
    evidence: str = Field(min_length=3, max_length=4000)


def _return_exception_kind(record):
    entry = summarize_return_exceptions([record])['exceptions'][0]
    return entry['exception_code']


@router.post('/material-returns/{return_id}/exception-task')
def assign_return_exception(pid: int, return_id: int, data: ReturnExceptionAssignIn,
    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Assign one active exception review using shared My Tasks/notifications."""
    from app.domains.coordination.models import Task
    from app.domains.coordination.service import _task
    from app.domains.identity_projects.security import permitted
    project = _scope(db, u, pid, 'procurement.stock.edit')
    record = _record(db, pid, u, return_id, lock=True)
    category = _return_exception_kind(record)
    if category == 'posted_unverified':
        raise HTTPException(409, 'Posted returns require reconciliation, not custody exception assignment')
    owner = db.get(User, data.owner_id)
    if not owner or not owner.active or owner.organization_id != u.organization_id:
        raise HTTPException(422, 'Active assignee from this organization required')
    required_permission = 'quality.edit' if category in ('awaiting_qa', 'qa_quarantined', 'qa_rejected') else 'procurement.stock.edit'
    permitted(db, owner, project, required_permission)
    if owner.id == record.submitted_by or (required_permission == 'quality.edit' and owner.id == record.received_by):
        raise HTTPException(403, 'Independent exception assignee required')
    existing = db.execute(select(Task).where(Task.organization_id == u.organization_id,
        Task.project_id == pid, Task.source_type == RETURN_EXCEPTION_TASK_TYPE,
        Task.source_id == return_id, Task.status.in_(['Open','In Progress','Blocked']))
        .with_for_update()).scalars().first()
    if existing:
        if existing.owner_id != owner.id:
            raise HTTPException(409, 'Exception already assigned to another owner')
        return {'task_id': existing.id, 'created': False, 'exception_code': category}
    task = _task(db, u, project, owner.id,
        f'Review Stores return {return_id}: {category.replace("_", " ")}',
        RETURN_EXCEPTION_TASK_TYPE, return_id, 'High')
    # Capture state at assignment so completion demands an actual workflow transition.
    task.evidence = f'Assigned exception: {category}'
    audit(db, u, 'assign_return_exception', 'stores_material_returns', record.id, project_id=pid)
    commit(db)
    return {'task_id': task.id, 'created': True, 'exception_code': category}


@router.post('/material-returns/{return_id}/exception-task/{task_id}/resolve')
def resolve_return_exception(pid: int, return_id: int, task_id: int, data: ReturnExceptionResolveIn,
    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Close review only after the real custody/QA state changes; no stock posting."""
    from app.domains.coordination.models import Task
    _scope(db, u, pid, 'procurement.stock.edit')
    record = _record(db, pid, u, return_id, lock=True)
    task = db.execute(select(Task).where(Task.id == task_id,
        Task.organization_id == u.organization_id, Task.project_id == pid,
        Task.source_type == RETURN_EXCEPTION_TASK_TYPE, Task.source_id == return_id)
        .with_for_update()).scalar_one_or_none()
    if task is None:
        raise HTTPException(404, 'Exception task not found')
    if task.owner_id != u.id and not u.organization_admin:
        raise HTTPException(403, 'Only assigned exception owner may resolve')
    if task.version != data.task_version or task.status not in ('Open','In Progress','Blocked'):
        raise HTTPException(409, 'Exception task already closed or stale version')
    original = (task.evidence or '').split('Assigned exception: ', 1)
    if len(original) != 2 or not original[1].strip():
        raise HTTPException(409, 'Missing original exception classification')
    current = _return_exception_kind(record)
    if current == original[1].strip():
        raise HTTPException(409, 'Complete the underlying Stores/QA workflow before resolving the exception')
    task.status = 'Completed'
    task.evidence = f'{task.evidence}\nResolved ({current}): {data.evidence.strip()}'
    task.version += 1
    audit(db, u, 'resolve_return_exception', 'stores_material_returns', return_id, project_id=pid)
    commit(db)
    return {'task_id': task.id, 'status': task.status, 'exception_code': current,
            'physical_stock_readiness': 'Unverified'}


@router.get('/material-returns/exception-monitor')
def material_return_exception_monitor(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Project-scoped internal dashboard feed; no cross-tenant or stock-ready inference."""
    _scope(db, u, pid, 'procurement.stock.edit')
    rows = db.execute(select(StoresMaterialReturn).where(
        StoresMaterialReturn.project_id == pid,
        StoresMaterialReturn.organization_id == u.organization_id
    ).order_by(StoresMaterialReturn.id.desc()).limit(500)).scalars().all()
    return summarize_return_exceptions(rows)


def summarize_return_exception_tasks(records, tasks, *, today=None):
    """Read-only workload metrics; counts cover only fetched return records."""
    today = today or date.today()
    base = summarize_return_exceptions(records)
    kinds = {entry['return_id']: entry['exception_code'] for entry in base['exceptions']}
    live = [task for task in tasks if task.source_id in kinds and task.status in ('Open', 'In Progress', 'Blocked')]
    owner_counts = {}
    for task in live:
        key = str(task.owner_id)
        owner_counts[key] = owner_counts.get(key, 0) + 1
    assigned_ids = {task.source_id for task in live}
    actionable = {rid for rid, kind in kinds.items() if kind != 'posted_unverified'}
    return {
        'counts': base['counts'],
        'active_tasks': len(live),
        'overdue_tasks': sum(task.due_date is not None and task.due_date < today for task in live),
        'blocked_tasks': sum(task.status == 'Blocked' for task in live),
        'unassigned_exceptions': len(actionable - assigned_ids),
        'by_owner_id': owner_counts,
        'total_records': base['total_records'],
        'coverage': base['coverage'],
        'physical_stock_readiness': 'Unverified',
        'ledger_reconciled': False,
    }


def _return_workload(db, organization_id, pid):
    from app.domains.coordination.models import Task
    records = db.execute(select(StoresMaterialReturn).where(
        StoresMaterialReturn.organization_id == organization_id,
        StoresMaterialReturn.project_id == pid
    ).order_by(StoresMaterialReturn.id.desc()).limit(500)).scalars().all()
    ids = [record.id for record in records]
    tasks = db.execute(select(Task).where(
        Task.organization_id == organization_id,
        Task.project_id == pid,
        Task.source_type == RETURN_EXCEPTION_TASK_TYPE,
        Task.source_id.in_(ids or [-1])
    )).scalars().all()
    return summarize_return_exception_tasks(records, tasks)


@router.get('/material-returns/exception-workload')
def return_exception_workload(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Internal assigned-owner and overdue task view; no verified physical stock KPI."""
    _scope(db, u, pid, 'procurement.stock.edit')
    return _return_workload(db, u.organization_id, pid)


@router.get('/internal-command-center/return-exceptions')
def internal_command_center_return_exceptions(pid: int, request: __import__('fastapi').Request,
    db: Session = Depends(get_db)):
    """Service-only feed; Command Center must enforce viewer's current project grants."""
    from app.config import settings
    from app.domains.identity_projects.models import Project
    expected = settings.command_center_identity_service_key
    provided = request.headers.get('X-ZerroR-Service-Key', '')
    if not expected or not hmac.compare_digest(expected, provided):
        raise HTTPException(403, 'Command Center service authentication required')
    project = db.get(Project, pid)
    if project is None:
        raise HTTPException(404, 'Project not found')
    result = _return_workload(db, project.organization_id, pid)
    return {
        **result,
        'organization_id': project.organization_id,
        'project_id': pid,
        'source': 'zerrobuild.stores.material_returns',
        'as_of': datetime.now(timezone.utc).isoformat(),
        'read_only': True,
    }


class ReturnPostingIn(BaseModel):
    version: int = Field(ge=1)
    posting_number: str = Field(min_length=1, max_length=80)
    evidence: str = Field(min_length=3, max_length=4000)


def _require_return_posting_gate():
    """Return posting is opt-in ONLY after shared-writer and DB validation."""
    if (os.getenv('STORES_ATOMIC_LOT_RETURN_ENABLED', 'false').lower() != 'true'
            or os.getenv('STORES_LOT_WRITER_CUTOVER', 'false').lower() != 'true'):
        raise HTTPException(503, 'Lot-aware return posting is disabled pending database validation')


def _require_postgres_row_locking(db):
    """Fail closed if the gated writer is run on a DB without row locks.

    PostgreSQL FOR UPDATE is required for serializing simultaneous posts on
    the original handover and inventory balance. SQLite ignores FOR UPDATE.
    """
    bind = db.get_bind()
    dialect = getattr(getattr(bind, 'dialect', None), 'name', None)
    if dialect != 'postgresql':
        raise HTTPException(503, 'Return stock posting requires PostgreSQL row-locking validation')


def _return_posting_quantity(record, source_line, previously_returned):
    """Never replenish more than the QA-accepted receipt or original outstanding issue."""
    quantity = _amount(record.received_quantity)
    requested = _amount(record.requested_quantity)
    issued = _amount(source_line.quantity)
    prior = _amount(previously_returned)
    if (not quantity.is_finite() or quantity <= 0
            or not requested.is_finite() or requested <= 0 or quantity > requested
            or not issued.is_finite() or issued <= 0
            or not prior.is_finite() or prior < 0 or prior + quantity > issued):
        raise HTTPException(409, 'Return exceeds issued or outstanding quantity')
    return quantity


def ensure_return_not_consumed(issued, previously_returned, new_return, committed_or_pending_usage):
    """Block returning stock already evidenced as consumed or installed.

    Pending QA usage is reserved for this check until accepted or rejected.
    """
    quantities = tuple(_amount(x) for x in
        (issued, previously_returned, new_return, committed_or_pending_usage))
    if any(not x.is_finite() or x < 0 for x in quantities):
        raise HTTPException(409, 'Invalid return or usage quantity')
    issue_qty, prior, proposed, usage = quantities
    if prior + proposed + usage > issue_qty:
        raise HTTPException(409, 'Return conflicts with verified or pending Construction material usage')


def _return_balance_after_posting(on_hand, reserved, quantity):
    """Validate old and proposed balance before a transaction writes any posting.

    This is defensive; the row-level PostgreSQL balance lock remains the
    concurrency boundary and the caller must commit all changes together.
    """
    existing = _amount(on_hand)
    held = _amount(reserved)
    addition = _amount(quantity)
    if (not existing.is_finite() or not held.is_finite() or not addition.is_finite()
            or existing < 0 or held < 0 or addition <= 0 or held > existing):
        raise HTTPException(409, 'Inconsistent existing inventory balance or return quantity')
    updated = existing + addition
    if not updated.is_finite() or updated < held:
        raise HTTPException(409, 'Invalid inventory balance after return')
    return updated


@router.post('/material-returns/{return_id}/post-stock')
def post_qa_accepted_return(pid: int, return_id: int, data: ReturnPostingIn,
    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Single-transaction posting to existing stock ledger; never a second ledger.

    Disabled by default. PostgreSQL transactional validation and legacy path
    migration must precede any deployment-level activation.
    """
    _require_return_posting_gate()
    _require_postgres_row_locking(db)
    project = _scope(db, u, pid, 'procurement.stock.edit')
    from .posting_number_lock import lock_stock_posting_number
    lock_stock_posting_number(db, organization_id=u.organization_id, project_id=pid,
                              number=data.posting_number.strip())
    r = _record(db, pid, u, return_id, lock=True)
    if r.stock_posting_id is not None or r.status == 'Stock Posted':
        raise HTTPException(409, 'Return was already posted')
    if r.status != 'QA Accepted' or r.qa_decision != 'Accepted' or r.version != data.version:
        raise HTTPException(409, 'Current independent QA acceptance and version required')
    if u.id in (r.submitted_by, r.received_by, r.qa_by):
        raise HTTPException(403, 'Independent stock posting operator required')
    if r.return_location_id is None:
        raise HTTPException(409, 'An audited return bin placement is required before posting')
    _validate_return_location(db.execute(select(StoreLocation).where(
        StoreLocation.id == r.return_location_id).with_for_update()).scalar_one_or_none(),
        project_id=pid, organization_id=u.organization_id,
        warehouse_id=_return_source_warehouse(db, pid, u.organization_id, r))
    handover = db.execute(select(StoresMaterialHandover).where(
        StoresMaterialHandover.id == r.handover_id,
        StoresMaterialHandover.project_id == pid,
        StoresMaterialHandover.organization_id == u.organization_id).with_for_update()).scalar_one_or_none()
    if not handover or handover.status not in ('Acknowledged', 'Resolved'):
        raise HTTPException(409, 'Valid acknowledged handover required')
    issued_line = db.execute(select(StockPostingLine).where(
        StockPostingLine.id == handover.stock_posting_line_id).with_for_update()).scalar_one_or_none()
    issue = db.get(StockPosting, issued_line.posting_id) if issued_line else None
    if not issue or issue.organization_id != u.organization_id or issue.project_id != pid or issue.kind != 'Issue' or issue.status != 'Posted':
        raise HTTPException(409, 'Original issued stock must still be posted')
    allocations = db.execute(select(StoresOutboundLotAllocation).where(
        StoresOutboundLotAllocation.stock_posting_line_id == issued_line.id,
        StoresOutboundLotAllocation.project_id == pid,
        StoresOutboundLotAllocation.organization_id == u.organization_id).with_for_update()).scalars().all()
    transfer_allocations = db.execute(select(StoresTransferIssueAllocation).where(
        StoresTransferIssueAllocation.stock_posting_line_id == issued_line.id,
        StoresTransferIssueAllocation.project_id == pid,
        StoresTransferIssueAllocation.organization_id == u.organization_id).with_for_update()).scalars().all()
    grn_origin = len(allocations) == 1 and not transfer_allocations and _amount(allocations[0].quantity) == _amount(issued_line.quantity)
    transfer_origin = len(transfer_allocations) == 1 and not allocations and _amount(transfer_allocations[0].quantity) == _amount(issued_line.quantity)
    if not (grn_origin or transfer_origin):
        raise HTTPException(409, 'Full single-lot issue provenance required for return')
    if transfer_origin:
        if os.getenv('STORES_TRANSFER_LOT_RETURN_ENABLED', 'false').lower() != 'true':
            raise HTTPException(503, 'Transfer-derived stock returns disabled pending database validation')
        lot = db.execute(select(StoresTransferDestinationLot).where(
            StoresTransferDestinationLot.id == transfer_allocations[0].transfer_destination_lot_id,
            StoresTransferDestinationLot.organization_id == u.organization_id,
            StoresTransferDestinationLot.destination_project_id == pid,
            StoresTransferDestinationLot.destination_warehouse_id == issue.warehouse_id,
            StoresTransferDestinationLot.item_id == issued_line.item_id).with_for_update()).scalar_one_or_none()
        if lot is None or lot.status != 'QAAcceptedPendingActivation':
            raise HTTPException(409, 'Transfer destination lot is not QA accepted')
    from sqlalchemy import func
    prior_return = _amount(db.execute(select(func.coalesce(func.sum(StockPostingLine.quantity), 0))
        .join(StockPosting, StockPosting.id == StockPostingLine.posting_id)
        .where(StockPosting.organization_id == u.organization_id,
               StockPosting.project_id == pid, StockPosting.status == 'Posted',
               StockPosting.kind == 'Return', StockPostingLine.source_line_id == issued_line.id)).scalar_one())
    quantity = _return_posting_quantity(r, issued_line, prior_return)
    # The handover row is locked before reading construction evidence. Usage
    # submission and QA verification lock that same handover first.
    usage_rows = db.execute(select(StoresConstructionMaterialUsage).where(
        StoresConstructionMaterialUsage.organization_id == u.organization_id,
        StoresConstructionMaterialUsage.project_id == pid,
        StoresConstructionMaterialUsage.handover_id == handover.id)).scalars().all()
    verified_or_pending = sum((_amount(usage.quantity) for usage in usage_rows
        if usage.status in ('Verified', 'Pending QA')), Decimal(0))
    ensure_return_not_consumed(issued_line.quantity, prior_return, quantity, verified_or_pending)
    # Ensure no missing lot provenance exists in any posted stock movement.
    from .atomic_lot_issue import _require_full_coverage
    if grn_origin:
        _require_full_coverage(db, project, issue.warehouse_id, issued_line.item_id)
    else:
        from .mixed_lot_allocation import mixed_lot_warehouse_balance
        diagnostic = mixed_lot_warehouse_balance(pid, issue.warehouse_id, issued_line.item_id, issued_line.unit, u, db)
        if not diagnostic['ledger_reconciles']:
            raise HTTPException(409, 'Transfer-derived return warehouse reconciliation failed')
    balance = stock._lock_balance(db, u, project, issue.warehouse_id, issued_line.item_id, issued_line.unit)
    on_hand, reserved = _amount(balance.on_hand), _amount(balance.reserved)
    updated_on_hand = _return_balance_after_posting(on_hand, reserved, quantity)
    posting = stock._save(db, u, project, 'Return', data.posting_number,
        issue.warehouse_id, f'QA-accepted Stores return {r.id}: {data.evidence.strip()}',
        issue.recipient, None, issue.id)
    line = StockPostingLine(posting_id=posting.id, item_id=issued_line.item_id,
        source_line_id=issued_line.id, quantity=quantity, unit=issued_line.unit)
    db.add(line); db.flush()
    if grn_origin:
        db.add(StoresOutboundLotAllocation(organization_id=u.organization_id, project_id=pid,
            stock_posting_line_id=line.id, receipt_lot_id=allocations[0].receipt_lot_id,
            quantity=quantity, reason=f'QA-accepted Stores return {r.id} / original issue {issued_line.id}',
            created_by=u.id))
    else:
        db.add(StoresTransferReturnAllocation(organization_id=u.organization_id, project_id=pid,
            stock_posting_line_id=line.id, original_issue_line_id=issued_line.id,
            transfer_destination_lot_id=lot.id, quantity=quantity, created_by=u.id))
    balance.on_hand = updated_on_hand
    balance.version += 1
    r.stock_posting_id = posting.id
    r.status = 'Stock Posted'
    r.version += 1
    _event(db, u, project.id, 'stock', posting.id, 'returned', str(r.id))
    audit(db, u, 'post_qa_accepted_material_return', 'stores_material_returns', r.id, project_id=pid)
    commit(db)
    return payload(r)
