"""Phase 7: audited preservation inspections and expiration monitoring; read-only to stock."""
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.router import audit, commit
from .material_handovers import _scope
from .models import StoresReceiptLot, StoresPreservationPlan, StoresPreservationCheck

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Preservation'])

class PlanIn(BaseModel):
    receipt_lot_id: int = Field(gt=0)
    instructions: str = Field(min_length=3, max_length=4000)
    frequency_days: int = Field(ge=1, le=3650)
    next_due_date: date
    responsible_user_id: int = Field(gt=0)

class CheckIn(BaseModel):
    version: int = Field(ge=1)
    request_key: str = Field(min_length=1, max_length=120)
    condition: str
    findings: str = Field(min_length=3, max_length=4000)
    evidence: str = Field(min_length=3, max_length=4000)

CONDITIONS = frozenset({'Good', 'Attention', 'Quarantined'})

def risk_status(next_due_date, expiry_date, condition, today):
    if expiry_date is not None and expiry_date < today:
        return 'Expired'
    if condition == 'Quarantined':
        return 'Quarantined'
    if next_due_date < today:
        return 'Overdue'
    if expiry_date is not None and expiry_date == today:
        return 'Expiring Today'
    if next_due_date == today:
        return 'Due Today'
    return 'Scheduled'

def require_preservation_clear(db, *, lot_id: int, project_id: int, organization_id: int, today=None):
    """Fail closed on recorded preservation holds; invoke under lot transaction lock.

    A missing plan is NOT evidence of clearance; historic receipt lots may not
    have been enrolled yet, so coverage is exposed separately in the monitor.
    """
    today = today or date.today()
    plan = db.execute(select(StoresPreservationPlan).where(
        StoresPreservationPlan.receipt_lot_id == lot_id,
        StoresPreservationPlan.project_id == project_id,
        StoresPreservationPlan.organization_id == organization_id
    ).with_for_update()).scalar_one_or_none()
    if plan is None:
        return
    if plan.condition in ('Quarantined', 'Attention'):
        raise HTTPException(409, 'Preservation condition blocks reservation or issue')
    if plan.next_due_date < today:
        raise HTTPException(409, 'Overdue preservation inspection blocks reservation or issue')
    if plan.condition != 'Good':
        raise HTTPException(409, 'Preservation status is not cleared')

def serialize(plan, lot, today):
    return dict(id=plan.id, receipt_lot_id=plan.receipt_lot_id, warehouse_id=lot.warehouse_id,
        location_id=lot.location_id, lot_code=lot.lot_code, expiry_date=lot.expiry_date.isoformat() if lot.expiry_date else None,
        instructions=plan.instructions, frequency_days=plan.frequency_days,
        next_due_date=plan.next_due_date.isoformat(), responsible_user_id=plan.responsible_user_id,
        condition=plan.condition, status=risk_status(plan.next_due_date, lot.expiry_date, plan.condition, today),
        version=plan.version, last_checked_at=plan.last_checked_at.isoformat() if plan.last_checked_at else None,
        stock_readiness='Unverified')

@router.post('/preservation/plans', status_code=201)
def create_plan(pid: int, data: PlanIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    lot = db.execute(select(StoresReceiptLot).where(StoresReceiptLot.id == data.receipt_lot_id,
        StoresReceiptLot.project_id == pid, StoresReceiptLot.organization_id == u.organization_id)).scalar_one_or_none()
    if not lot:
        raise HTTPException(404, 'Receipt lot not found')
    from app.domains.identity_projects.models import User as IdentityUser
    owner = db.execute(select(IdentityUser).where(IdentityUser.id == data.responsible_user_id,
        IdentityUser.organization_id == u.organization_id)).scalar_one_or_none()
    if not owner:
        raise HTTPException(422, 'Responsible user not in organization')
    if db.execute(select(StoresPreservationPlan.id).where(StoresPreservationPlan.project_id == pid,
        StoresPreservationPlan.receipt_lot_id == lot.id)).scalar_one_or_none():
        raise HTTPException(409, 'Preservation plan already exists for this lot')
    plan = StoresPreservationPlan(organization_id=u.organization_id, project_id=pid,
        receipt_lot_id=lot.id, instructions=data.instructions, frequency_days=data.frequency_days,
        next_due_date=data.next_due_date, responsible_user_id=data.responsible_user_id, created_by=u.id)
    db.add(plan)
    db.flush()
    audit(db,u,'stores.preservation.plan.create','stores_preservation_plan',plan.id,{'receipt_lot_id':lot.id},project_id=pid)
    commit(db)
    return serialize(plan, lot, date.today())

@router.get('/preservation/plans')
def plans(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.view')
    rows = db.execute(select(StoresPreservationPlan, StoresReceiptLot).join(StoresReceiptLot,
        StoresPreservationPlan.receipt_lot_id == StoresReceiptLot.id).where(
        StoresPreservationPlan.project_id == pid, StoresPreservationPlan.organization_id == u.organization_id)
        .order_by(StoresPreservationPlan.next_due_date, StoresPreservationPlan.id).limit(500)).all()
    today = date.today()
    return dict(items=[serialize(p,l,today) for p,l in rows], scope='first 500 plans', physical_stock_readiness='Unverified')

@router.post('/preservation/plans/{plan_id}/checks')
def record_check(pid: int, plan_id: int, data: CheckIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.edit')
    if data.condition not in CONDITIONS:
        raise HTTPException(422, 'Invalid preservation condition')
    plan = db.execute(select(StoresPreservationPlan).where(StoresPreservationPlan.id == plan_id,
        StoresPreservationPlan.project_id == pid, StoresPreservationPlan.organization_id == u.organization_id)
        .with_for_update()).scalar_one_or_none()
    if plan is None:
        raise HTTPException(404, 'Plan not found')
    existing = db.execute(select(StoresPreservationCheck).where(StoresPreservationCheck.plan_id == plan_id,
        StoresPreservationCheck.request_key == data.request_key)).scalar_one_or_none()
    if existing:
        if existing.condition != data.condition or existing.findings != data.findings or existing.evidence != data.evidence:
            raise HTTPException(409, 'Idempotency key reused with different evidence')
        return dict(id=existing.id, status='AlreadyRecorded', plan_version=plan.version)
    if plan.version != data.version:
        raise HTTPException(409, 'Stale preservation plan version')
    now = datetime.now(timezone.utc)
    row = StoresPreservationCheck(plan_id=plan.id, request_key=data.request_key,
        condition=data.condition, findings=data.findings, evidence=data.evidence, checked_by=u.id, checked_at=now)
    db.add(row)
    plan.condition = data.condition
    plan.last_checked_at = now
    plan.next_due_date = now.date() + timedelta(days=plan.frequency_days)
    plan.version += 1
    db.flush()
    audit(db,u,'stores.preservation.check','stores_preservation_plan',plan.id,
        {'check_id':row.id,'condition':data.condition},project_id=pid)
    commit(db)
    return dict(id=row.id, condition=row.condition, plan_version=plan.version, next_due_date=plan.next_due_date.isoformat(),
        stock_readiness='Unverified')

@router.get('/preservation/plans/{plan_id}/checks')
def plan_checks(pid: int, plan_id: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _scope(db, u, pid, 'procurement.stock.view')
    plan = db.execute(select(StoresPreservationPlan.id).where(
        StoresPreservationPlan.id == plan_id, StoresPreservationPlan.project_id == pid,
        StoresPreservationPlan.organization_id == u.organization_id)).scalar_one_or_none()
    if plan is None:
        raise HTTPException(404, 'Plan not found')
    rows = db.execute(select(StoresPreservationCheck).where(
        StoresPreservationCheck.plan_id == plan_id).order_by(
        StoresPreservationCheck.checked_at.desc(), StoresPreservationCheck.id.desc()).limit(100)).scalars().all()
    return {'items': [dict(id=r.id, condition=r.condition, findings=r.findings,
        evidence=r.evidence, checked_by=r.checked_by, checked_at=r.checked_at.isoformat()) for r in rows],
        'coverage': 'latest 100 inspections'}
