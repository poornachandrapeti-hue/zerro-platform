"""Approval workflow for Finance journal *proposals*, never GL postings."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pydantic import ValidationError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.supply_chain.models import StockPostingLine, StockPosting
from .models import FinanceMovementJournalProposal as Proposal, FinanceCostCode, FinanceInventoryCostingPolicy
from .router import guard

router=APIRouter(prefix='/api/projects/{pid}/financials/movement-journal-proposals', tags=['Financials'])

class JournalLine(BaseModel):
    cost_code_id:int=Field(gt=0)
    debit:Decimal=Field(default=Decimal('0'),ge=0,max_digits=20,decimal_places=2)
    credit:Decimal=Field(default=Decimal('0'),ge=0,max_digits=20,decimal_places=2)

class NewProposal(BaseModel):
    source_movement_line_id:int=Field(gt=0)
    currency:str=Field(pattern=r'^[A-Z]{3}$')
    description:str=Field(min_length=3,max_length=400)
    lines:list[JournalLine]=Field(min_length=2,max_length=100)

class Decision(BaseModel):
    reason:str=Field(min_length=3,max_length=1000)

def validate_lines(lines):
    # Do not trust JSON-decoded proposal lines: they may bypass request validation.
    # PostgreSQL Numeric(20,2) must not receive unbounded, non-finite or fractional-cent amounts.
    if not 2 <= len(lines) <= 100:
        raise HTTPException(422, 'Journal proposal must contain 2 to 100 lines')
    debit=Decimal('0'); credit=Decimal('0')
    for line in lines:
        for amount in (line.debit, line.credit):
            if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2 or amount >= Decimal('1000000000000000000'):
                raise HTTPException(422, 'Journal amounts must be finite, non-negative and within 2 decimal places')
        if (line.debit>0)==(line.credit>0):
            raise HTTPException(422,'Each line needs exactly one positive debit or credit')
        debit+=line.debit;credit+=line.credit
    if debit<=0 or debit!=credit:
        raise HTTPException(422,'Journal proposal debits and credits must be positive and balanced')
    return str(debit)

def verify_current_costing_policy(db, pid, organization_id, currency):
    """Fail closed when the project's latest Finance costing policy is not approved.

    This is approval eligibility only, never proof of valued movements or GL postings.
    """
    policies = (db.query(FinanceInventoryCostingPolicy)
                .filter_by(project_id=pid, organization_id=organization_id)
                .order_by(FinanceInventoryCostingPolicy.revision.desc()).limit(1).all())
    if not policies:
        raise HTTPException(409, 'Finance inventory costing policy is missing')
    policy = policies[0]
    if policy.status != 'Approved' or policy.approved_by is None or policy.approved_at is None:
        raise HTTPException(409, 'Latest Finance inventory costing policy is not approved')
    if policy.costing_method not in {'FIFO', 'WEIGHTED_AVERAGE'}:
        raise HTTPException(409, 'Finance costing method is unsupported')
    if policy.currency != currency:
        raise HTTPException(409, 'Journal proposal currency differs from approved Finance policy')
    return policy

def verify_proposal_authority(db, pid, organization_id, proposal):
    """Re-check referenced source and Finance code authority at every transition.

    A proposal is not a journal posting; this prevents stale approvals when
    underlying movements are canceled or scoped Finance codes are withdrawn.
    """
    movement = db.query(StockPostingLine).filter_by(id=proposal.source_movement_line_id).first()
    if movement is None:
        raise HTTPException(409, 'Source stock movement no longer exists')
    posting = db.query(StockPosting).filter_by(
        id=movement.posting_id, project_id=pid, organization_id=organization_id
    ).first()
    if posting is None or posting.kind != 'Issue' or posting.status != 'Posted':
        raise HTTPException(409, 'Source stock issue is no longer posted in this project')
    if movement.quantity is None or not Decimal(str(movement.quantity)).is_finite() or Decimal(str(movement.quantity)) <= 0:
        raise HTTPException(409, 'Source stock issue quantity is invalid')
    verify_current_costing_policy(db, pid, organization_id, proposal.currency)
    checked_lines = [JournalLine(**line) for line in proposal.lines]
    validate_lines(checked_lines)
    for line in checked_lines:
        if not db.query(FinanceCostCode.id).filter_by(
            id=line.cost_code_id, project_id=pid, organization_id=organization_id
        ).first():
            raise HTTPException(409, 'Finance cost code is no longer valid in this project')
    return True

def output(x):
    return {'id':x.id,'project_id':x.project_id,'source_movement_line_id':x.source_movement_line_id,
            'proposal_revision':x.proposal_revision,'currency':x.currency,'description':x.description,
            'lines':x.lines,'status':x.status,'created_by':x.created_by,'submitted_by':x.submitted_by,
            'approved_by':x.approved_by,'decision_reason':x.decision_reason,
            'gl_posted':False,'movement_valuation_certified':False}

def build_approved_handoff(proposal):
    """Deterministic, read-only approved proposal handoff; NEVER a GL posting."""
    if proposal.status != 'Approved' or proposal.approved_by is None or proposal.approved_at is None:
        raise HTTPException(409, 'Only independently approved proposals can be exported')
    try:
        lines = [JournalLine(**line) for line in proposal.lines]
    except (ValidationError, ValueError, TypeError) as exc:
        raise HTTPException(409, 'Stored journal proposal lines are invalid') from exc
    total = validate_lines(lines)
    payload = {
        'schema_version': 1,
        'organization_id': proposal.organization_id,
        'project_id': proposal.project_id,
        'proposal_id': proposal.id,
        'proposal_revision': proposal.proposal_revision,
        'source_movement_line_id': proposal.source_movement_line_id,
        'currency': proposal.currency,
        'description': proposal.description,
        'lines': [{'cost_code_id': line.cost_code_id,
                   'debit': format(line.debit, '.2f'),
                   'credit': format(line.credit, '.2f')} for line in lines],
        'balanced_total': format(Decimal(total), '.2f'),
        'finance_approved_by': proposal.approved_by,
        'finance_approved_at': proposal.approved_at.isoformat(),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    return {'posting_status': 'NOT_POSTED', 'movement_valuation_certified': False,
            'idempotency_key': f"finance-proposal:{proposal.organization_id}:{proposal.project_id}:{proposal.id}:{proposal.proposal_revision}",
            'payload_sha256': digest, 'journal_proposal': payload}

@router.get('/{proposal_id}/approved-handoff')
def approved_handoff(pid:int,proposal_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    p=db.query(Proposal).filter_by(id=proposal_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if p is None:raise HTTPException(404,'Proposal not found')
    # Verify the source and project finance references again, even on a read.
    verify_proposal_authority(db,pid,user.organization_id,p)
    return build_approved_handoff(p)

def get_scoped(db,pid,org,id):
    p=db.query(Proposal).filter_by(id=id,project_id=pid,organization_id=org).with_for_update().one_or_none()
    if p is None:raise HTTPException(404,'Proposal not found')
    return p

@router.get('')
def list_proposals(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return [output(x) for x in db.query(Proposal).filter_by(project_id=pid,organization_id=user.organization_id).order_by(Proposal.id.desc()).limit(200)]

@router.post('',status_code=201)
def create_proposal(pid:int,body:NewProposal,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    validate_lines(body.lines)
    verify_current_costing_policy(db, pid, user.organization_id, body.currency)
    # A stock line must exist in this project, but valuation is not inferred from it.
    movement=db.query(StockPostingLine).filter_by(id=body.source_movement_line_id).first()
    if movement is None:
        raise HTTPException(422,'Unknown stock posting line')
    posting=db.query(StockPosting).filter_by(id=movement.posting_id,project_id=pid,organization_id=user.organization_id).first()
    if posting is None or posting.status!='Posted' or posting.kind!='Issue':
        raise HTTPException(422,'Source must be a posted issue in this project')
    # Enforce the same source, quantity, costing-policy and cost-code gates
    # at creation as at submission/approval. A Draft must not be created
    # against invalid or unscoped evidence.
    from types import SimpleNamespace
    candidate = SimpleNamespace(source_movement_line_id=body.source_movement_line_id,
                                currency=body.currency,
                                lines=[{'cost_code_id':l.cost_code_id,
                                        'debit':str(l.debit), 'credit':str(l.credit)}
                                       for l in body.lines])
    verify_proposal_authority(db, pid, user.organization_id, candidate)
    existing=db.query(Proposal).filter_by(project_id=pid,organization_id=user.organization_id,
          source_movement_line_id=body.source_movement_line_id).order_by(Proposal.proposal_revision.desc()).with_for_update().first()
    if existing and existing.status not in {'Rejected'}:
        raise HTTPException(409,'Existing proposal must be rejected before new revision')
    row=Proposal(organization_id=user.organization_id,project_id=pid,source_movement_line_id=body.source_movement_line_id,
       proposal_revision=(existing.proposal_revision+1 if existing else 1),currency=body.currency,
       description=body.description,lines=[{'cost_code_id':l.cost_code_id,'debit':str(l.debit),'credit':str(l.credit)} for l in body.lines],created_by=user.id)
    db.add(row)
    try:db.commit();db.refresh(row)
    except IntegrityError:db.rollback();raise HTTPException(409,'Concurrent duplicate journal proposal')
    return output(row)

@router.post('/{proposal_id}/submit')
def submit(pid:int,proposal_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    p=get_scoped(db,pid,user.organization_id,proposal_id)
    if p.status!='Draft':raise HTTPException(409,'Only draft proposals can be submitted')
    verify_proposal_authority(db,pid,user.organization_id,p)
    p.status='Pending Review';p.submitted_by=user.id;db.commit()
    return output(p)

@router.post('/{proposal_id}/approve')
def approve(pid:int,proposal_id:int,decision:Decision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    p=get_scoped(db,pid,user.organization_id,proposal_id)
    if p.status!='Pending Review':raise HTTPException(409,'Proposal not pending')
    if user.id in {p.created_by,p.submitted_by}:raise HTTPException(403,'Independent approval required')
    verify_proposal_authority(db,pid,user.organization_id,p)
    p.status='Approved';p.approved_by=user.id;p.approved_at=datetime.now(timezone.utc);p.decision_reason=decision.reason
    db.commit();return output(p)

@router.post('/{proposal_id}/reject')
def reject(pid:int,proposal_id:int,decision:Decision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    p=get_scoped(db,pid,user.organization_id,proposal_id)
    if p.status!='Pending Review':raise HTTPException(409,'Proposal not pending')
    p.status='Rejected';p.approved_by=user.id;p.approved_at=datetime.now(timezone.utc);p.decision_reason=decision.reason
    db.commit();return output(p)
