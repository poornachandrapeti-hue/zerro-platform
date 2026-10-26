"""Phase 7: count-sheet observations and independent review. Never posts stock."""
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
from app.domains.supply_chain.models import Warehouse, StockBalance
from .material_handovers import _scope
from .models import StoresCycleCount, StoresCycleCountLine, StoresReceiptLot

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Cycle Counts'])

class CountIn(BaseModel):
    reference: str = Field(min_length=2, max_length=120)
    warehouse_id: int = Field(gt=0)
    scheduled_date: date

class CountLineIn(BaseModel):
    version: int = Field(ge=1)
    receipt_lot_id: int = Field(gt=0)
    observed_quantity: Decimal = Field(ge=0, decimal_places=3)
    evidence: str = Field(min_length=3, max_length=4000)

class CountActionIn(BaseModel):
    version: int = Field(ge=1)
    evidence: str = Field(min_length=3, max_length=4000)


def variance(observed: Decimal, recorded: Decimal) -> Decimal:
    return observed - recorded


def _find(db, pid, org, count_id, *, lock=False):
    q = select(StoresCycleCount).where(StoresCycleCount.id == count_id,
        StoresCycleCount.project_id == pid, StoresCycleCount.organization_id == org)
    return db.execute(q.with_for_update() if lock else q).scalar_one_or_none()


def _serialize(count, lines):
    return dict(id=count.id, reference=count.reference, warehouse_id=count.warehouse_id,
        scheduled_date=count.scheduled_date.isoformat(), status=count.status,
        version=count.version, created_by=count.created_by, submitted_by=count.submitted_by,
        verified_by=count.verified_by, review_evidence=count.review_evidence,
        lines=[dict(id=line.id, receipt_lot_id=line.receipt_lot_id,
          observed_quantity=str(line.observed_quantity), recorded_lot_quantity=str(line.recorded_lot_quantity),
          variance=str(variance(line.observed_quantity, line.recorded_lot_quantity)),
          evidence=line.evidence, counted_by=line.counted_by) for line in lines],
        stock_adjustment_posted=False, stock_readiness='Unverified')



def reconcile_snapshot(count, lines, balances):
    """Advisory only: stock balance has no receipt-lot key and count may be partial."""
    observations = [dict(
        receipt_lot_id=line.receipt_lot_id,
        observed_quantity=str(line.observed_quantity),
        historical_receipt_quantity=str(line.recorded_lot_quantity),
        historical_difference=str(variance(line.observed_quantity, line.recorded_lot_quantity)),
        variance_verified=False,
    ) for line in lines]
    ledger = [dict(item_id=balance.item_id, unit=balance.unit,
        on_hand=str(balance.on_hand), reserved=str(balance.reserved),
        version=balance.version) for balance in balances]
    return dict(count_id=count.id, warehouse_id=count.warehouse_id,
        count_status=count.status, observations=observations,
        warehouse_ledger_balances=ledger,
        reconciliation_status='Blocked', stock_adjustment_posted=False,
        blockers=[
          'Count entries reference receipt lots; stock balances are warehouse/item aggregates without per-lot on-hand.',
          'Historical receipt quantities are not current on-hand balances and cannot be used for book variance.',
          'A point-in-time stock snapshot and complete GRN plus transfer-derived lot coverage are required.',
          'Concurrent postings after the count date and uncounted lots prevent authoritative variance.',
        ],
        independently_verified_count=(count.status == 'Verified'),
        authorized_stock_adjustment=False)


@router.get('/cycle-counts/{count_id}/variance-reconciliation')
def count_variance_reconciliation(pid:int,count_id:int,u:User=Depends(authenticated),db:Session=Depends(get_db)):
    """Read-only count vs warehouse ledger context; never asserts lot-level variance."""
    _scope(db,u,pid,'procurement.stock.view')
    count=_find(db,pid,u.organization_id,count_id)
    if not count: raise HTTPException(404,'Count not found')
    lines=db.execute(select(StoresCycleCountLine).where(
        StoresCycleCountLine.count_id==count.id).order_by(StoresCycleCountLine.id)).scalars().all()
    balances=db.execute(select(StockBalance).where(
        StockBalance.organization_id==u.organization_id,
        StockBalance.project_id==pid,
        StockBalance.warehouse_id==count.warehouse_id).order_by(StockBalance.item_id)).scalars().all()
    result=reconcile_snapshot(count,lines,balances)
    result['snapshot_observed_at']=datetime.now(timezone.utc).isoformat()
    result['snapshot_is_contemporaneous_with_physical_count']=False
    return result

@router.post('/cycle-counts', status_code=201)
def create_count(pid: int, data: CountIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db,u,pid,'procurement.stock.edit')
    wh=db.execute(select(Warehouse).where(Warehouse.id==data.warehouse_id,
        Warehouse.project_id==pid,Warehouse.organization_id==u.organization_id)).scalar_one_or_none()
    if wh is None: raise HTTPException(422,'Warehouse not in this project')
    if db.execute(select(StoresCycleCount.id).where(StoresCycleCount.project_id==pid,
            StoresCycleCount.reference==data.reference)).scalar_one_or_none():
        raise HTTPException(409,'Count reference already exists')
    count=StoresCycleCount(organization_id=u.organization_id,project_id=pid,warehouse_id=wh.id,
        reference=data.reference,scheduled_date=data.scheduled_date,created_by=u.id)
    db.add(count);db.flush()
    audit(db,u,'stores.cycle_count.create','stores_cycle_count',count.id,{'warehouse_id':wh.id},project_id=pid)
    commit(db)
    return _serialize(count,[])

@router.get('/cycle-counts')
def list_counts(pid:int,u:User=Depends(authenticated),db:Session=Depends(get_db)):
    _scope(db,u,pid,'procurement.stock.view')
    counts=db.execute(select(StoresCycleCount).where(StoresCycleCount.project_id==pid,
        StoresCycleCount.organization_id==u.organization_id).order_by(StoresCycleCount.id.desc()).limit(200)).scalars().all()
    return dict(items=[dict(id=c.id,reference=c.reference,warehouse_id=c.warehouse_id,status=c.status,
        scheduled_date=c.scheduled_date.isoformat(),version=c.version) for c in counts],
        scope='latest 200 counts',stock_adjustment_posted=False)

@router.get('/cycle-counts/{count_id}')
def count_details(pid:int,count_id:int,u:User=Depends(authenticated),db:Session=Depends(get_db)):
    _scope(db,u,pid,'procurement.stock.view')
    count=_find(db,pid,u.organization_id,count_id)
    if not count: raise HTTPException(404,'Count not found')
    lines=db.execute(select(StoresCycleCountLine).where(StoresCycleCountLine.count_id==count.id)).scalars().all()
    return _serialize(count,lines)

@router.post('/cycle-counts/{count_id}/lines')
def record_line(pid:int,count_id:int,data:CountLineIn,u:User=Depends(authenticated),db:Session=Depends(get_db)):
    _scope(db,u,pid,'procurement.stock.edit')
    count=_find(db,pid,u.organization_id,count_id,lock=True)
    if not count: raise HTTPException(404,'Count not found')
    if count.version!=data.version: raise HTTPException(409,'Stale count version')
    if count.status not in ('Draft','Recount'): raise HTTPException(409,'Count not open for counting')
    lot=db.execute(select(StoresReceiptLot).where(StoresReceiptLot.id==data.receipt_lot_id,
        StoresReceiptLot.project_id==pid,StoresReceiptLot.organization_id==u.organization_id,
        StoresReceiptLot.warehouse_id==count.warehouse_id)).scalar_one_or_none()
    if not lot: raise HTTPException(422,'Receipt lot not in count warehouse')
    # Do not call this snapshot physical on-hand: GRN provenance quantities include historical issues/returns.
    line=db.execute(select(StoresCycleCountLine).where(StoresCycleCountLine.count_id==count.id,
        StoresCycleCountLine.receipt_lot_id==lot.id).with_for_update()).scalar_one_or_none()
    if line is None:
        line=StoresCycleCountLine(count_id=count.id,receipt_lot_id=lot.id,
            recorded_lot_quantity=lot.quantity,observed_quantity=data.observed_quantity,
            evidence=data.evidence,counted_by=u.id)
        db.add(line)
    else:
        line.observed_quantity=data.observed_quantity;line.evidence=data.evidence;line.counted_by=u.id
    count.version+=1
    audit(db,u,'stores.cycle_count.line.record','stores_cycle_count',count.id,{'receipt_lot_id':lot.id},project_id=pid)
    commit(db)
    return count_details(pid,count_id,u,db)

@router.post('/cycle-counts/{count_id}/submit')
def submit_count(pid:int,count_id:int,data:CountActionIn,u:User=Depends(authenticated),db:Session=Depends(get_db)):
    _scope(db,u,pid,'procurement.stock.edit')
    count=_find(db,pid,u.organization_id,count_id,lock=True)
    if not count: raise HTTPException(404,'Count not found')
    if count.version!=data.version or count.status not in ('Draft','Recount'):
        raise HTTPException(409,'Count not available for submission at this version')
    if not db.execute(select(StoresCycleCountLine.id).where(StoresCycleCountLine.count_id==count.id)).first():
        raise HTTPException(409,'At least one counted line required')
    count.status='Submitted';count.submitted_by=u.id;count.review_evidence=data.evidence;count.version+=1
    audit(db,u,'stores.cycle_count.submit','stores_cycle_count',count.id,{'status':'Submitted'},project_id=pid)
    commit(db)
    return dict(id=count.id,status=count.status,version=count.version,stock_adjustment_posted=False)

@router.post('/cycle-counts/{count_id}/review')
def review_count(pid:int,count_id:int,data:CountActionIn,decision:str,
                 u:User=Depends(authenticated),db:Session=Depends(get_db)):
    _scope(db,u,pid,'procurement.stock.edit')
    if decision not in ('Verify','Recount'): raise HTTPException(422,'Invalid review decision')
    count=_find(db,pid,u.organization_id,count_id,lock=True)
    if not count: raise HTTPException(404,'Count not found')
    if count.version!=data.version or count.status!='Submitted':
        raise HTTPException(409,'Count not available for review')
    if u.id in (count.created_by,count.submitted_by):
        raise HTTPException(403,'Independent reviewer required')
    count.status='Verified' if decision=='Verify' else 'Recount'
    count.verified_by=u.id if decision=='Verify' else None
    count.review_evidence=data.evidence;count.version+=1
    audit(db,u,'stores.cycle_count.review','stores_cycle_count',count.id,{'decision':decision},project_id=pid)
    commit(db)
    return dict(id=count.id,status=count.status,version=count.version,stock_adjustment_posted=False,
        note='Recorded lot quantity is provenance, not a validated on-hand stock snapshot')
