"""Finance-owned inventory valuation policy; configuration only, never a posting API."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from .router import guard
from .models import FinanceInventoryCostingPolicy as Policy

router = APIRouter(prefix='/api/projects/{pid}/financials/inventory-costing', tags=['Financials'])
METHODS = frozenset({'FIFO', 'WEIGHTED_AVERAGE'})

def policy_out(p):
    return dict(id=p.id, project_id=p.project_id, revision=p.revision,
                costing_method=p.costing_method, currency=p.currency,
                effective_note=p.effective_note, status=p.status,
                created_by=p.created_by, submitted_by=p.submitted_by,
                approved_by=p.approved_by,
                approved_at=p.approved_at.isoformat() if p.approved_at else None,
                decision_reason=p.decision_reason,
                movement_valuation_ready=False, journal_posting_ready=False)

class PolicyInput(BaseModel):
    costing_method: str
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    effective_note: str = Field(min_length=3, max_length=1000)

class DecisionInput(BaseModel):
    reason: str = Field(min_length=3,max_length=1000)

@router.get('')
def list_policies(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return [policy_out(p) for p in db.query(Policy).filter_by(project_id=pid,organization_id=user.organization_id).order_by(Policy.revision.desc()).all()]

@router.post('',status_code=201)
def create_policy(pid:int,body:PolicyInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    if body.costing_method not in METHODS:
        raise HTTPException(422,'Unsupported inventory costing method')
    prior=db.query(Policy).filter_by(project_id=pid,organization_id=user.organization_id).order_by(Policy.revision.desc()).with_for_update().first()
    if prior and prior.status not in {'Approved','Rejected'}:
        raise HTTPException(409,'Resolve the previous inventory costing policy revision first')
    p=Policy(project_id=pid,organization_id=user.organization_id,revision=prior.revision+1 if prior else 1,
             costing_method=body.costing_method,currency=body.currency,
             effective_note=body.effective_note,created_by=user.id,status='Draft')
    db.add(p)
    try:
        db.commit();db.refresh(p)
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Policy revision already exists')
    return policy_out(p)

@router.post('/{policy_id}/submit')
def submit_policy(pid:int,policy_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    p=db.query(Policy).filter_by(id=policy_id,project_id=pid,organization_id=user.organization_id).with_for_update().one_or_none()
    if p is None: raise HTTPException(404,'Policy not found')
    if p.status!='Draft': raise HTTPException(409,'Only draft policies can be submitted')
    p.status='Pending Review';p.submitted_by=user.id
    db.commit();db.refresh(p)
    return policy_out(p)

@router.post('/{policy_id}/approve')
def approve_policy(pid:int,policy_id:int,body:DecisionInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    p=db.query(Policy).filter_by(id=policy_id,project_id=pid,organization_id=user.organization_id).with_for_update().one_or_none()
    if p is None: raise HTTPException(404,'Policy not found')
    if p.status!='Pending Review': raise HTTPException(409,'Policy not pending review')
    if user.id in {p.created_by,p.submitted_by}:raise HTTPException(403,'Independent Finance approval required')
    p.status='Approved';p.approved_by=user.id;p.approved_at=datetime.now(timezone.utc);p.decision_reason=body.reason
    db.commit();db.refresh(p)
    return policy_out(p)
