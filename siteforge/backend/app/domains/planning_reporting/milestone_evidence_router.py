"""Audited milestone-date evidence; no guessed completion dates.
Only organization admins can propose/review pending finer-grained Planning RBAC.
"""
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from .workspace_router import access
from .workspace_models import PlanningPublication, PlanningMilestoneEvidence

router = APIRouter(prefix='/api/projects/{pid}/planning', tags=['Planning Milestone Evidence'])

class EvidenceInput(BaseModel):
    publication_id: int
    activity_code: str = Field(min_length=1, max_length=80)
    achieved_on: date
    evidence_ref: str = Field(min_length=5, max_length=240)

class EvidenceDecision(BaseModel):
    decision: str
    note: str = Field(min_length=5, max_length=1000)

def publication(db, user, pid, pub_id, code=None):
    pub=db.query(PlanningPublication).filter_by(id=pub_id, project_id=pid, organization_id=user.organization_id, status='Approved').one_or_none()
    if not pub: raise HTTPException(422,'Approved publication not found in project')
    if code is not None:
        rows=(pub.snapshot or {}).get('activities') or []
        if not any(str(r.get('code'))==code and r.get('activity_type')=='Milestone' for r in rows if isinstance(r,dict)):
            raise HTTPException(422,'Milestone not present in approved snapshot')
    return pub

@router.get('/milestone-evidence')
def list_evidence(pid:int, publication_id:int, user:User=Depends(authenticated), db:Session=Depends(get_db)):
    access(db,user,pid)
    publication(db,user,pid,publication_id)
    rows=db.query(PlanningMilestoneEvidence).filter_by(project_id=pid, organization_id=user.organization_id,publication_id=publication_id).limit(501).all()
    if len(rows)>500: raise HTTPException(503,'Evidence listing limit exceeded')
    return [{'id':r.id,'activity_code':r.activity_code,'achieved_on':r.achieved_on,'evidence_ref':r.evidence_ref,'status':r.status,'submitted_at':r.submitted_at,'reviewed_at':r.reviewed_at} for r in rows]

@router.post('/milestone-evidence',status_code=201)
def submit_evidence(pid:int,body:EvidenceInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,write=True)
    if not user.organization_admin: raise HTTPException(403,'Organization administrator required until reviewer roles are mapped')
    pub=publication(db,user,pid,body.publication_id,body.activity_code)
    if body.achieved_on > datetime.now(timezone.utc).date(): raise HTTPException(422,'Future achievement date cannot be verified')
    existing=db.query(PlanningMilestoneEvidence).filter_by(publication_id=pub.id,activity_code=body.activity_code).first()
    if existing: raise HTTPException(409,'Evidence exists for this publication and milestone; revisions require controlled review')
    row=PlanningMilestoneEvidence(organization_id=user.organization_id,project_id=pid,publication_id=pub.id,
        activity_code=body.activity_code,achieved_on=body.achieved_on,evidence_ref=body.evidence_ref,submitted_by=user.id)
    db.add(row);db.commit();db.refresh(row)
    return {'id':row.id,'status':row.status}

@router.post('/milestone-evidence/{evidence_id}/decision')
def decide_evidence(pid:int,evidence_id:int,body:EvidenceDecision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,write=True)
    if not user.organization_admin: raise HTTPException(403,'Organization administrator required until reviewer roles are mapped')
    row=db.query(PlanningMilestoneEvidence).filter_by(id=evidence_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if not row: raise HTTPException(404,'Evidence not found')
    publication(db,user,pid,row.publication_id,row.activity_code)
    if row.status!='Pending Review': raise HTTPException(409,'Evidence already decided')
    if row.submitted_by==user.id: raise HTTPException(403,'Independent reviewer required')
    if body.decision not in ('Approved','Rejected'): raise HTTPException(422,'Decision must be Approved or Rejected')
    row.status=body.decision;row.reviewed_by=user.id;row.reviewed_at=datetime.now(timezone.utc);row.review_note=body.note
    db.commit()
    return {'id':row.id,'status':row.status}
