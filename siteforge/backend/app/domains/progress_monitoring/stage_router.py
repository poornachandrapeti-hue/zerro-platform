"""Project-scoped scheme lifecycle; no progress source writes."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.models import User
from app.domains.planning_reporting.workspace_models import PlanningPublication
from .reports_router import allowed
from .stage_scheme import validate_weights
from .stage_models import ProgressStageScheme
router = APIRouter(prefix='/api/projects/{pid}/progress/stage-schemes', tags=['Progress Stage Schemes'])
class CreateScheme(BaseModel):
    weights:dict[str,int]
    planning_publication_id:int=Field(gt=0)
class Approval(BaseModel):
    approval_reference:str=Field(min_length=1,max_length=160)
def serial(s):
    return {'id':s.id,'version':s.version,'status':s.status,'weights':s.weights,'planning_publication_id':s.planning_publication_id,'approval_reference':s.approval_reference,'created_by':s.created_by,'approved_by':s.approved_by,'approved_at':s.approved_at}
@router.get('')
def list_schemes(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    allowed(db,user,pid,'planning.view')
    return [serial(s) for s in db.query(ProgressStageScheme).filter_by(organization_id=user.organization_id,project_id=pid).order_by(ProgressStageScheme.version.desc()).limit(100)]
@router.post('',status_code=201)
def create(pid:int,body:CreateScheme,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    allowed(db,user,pid,'planning.manage')
    errors=validate_weights(body.weights)
    if errors:raise HTTPException(422,errors)
    pub=db.query(PlanningPublication).filter_by(id=body.planning_publication_id,organization_id=user.organization_id,project_id=pid,status='Approved',is_current=True).one_or_none()
    if pub is None:raise HTTPException(422,'A current approved Planning publication is required')
    version=(db.query(func.max(ProgressStageScheme.version)).filter_by(project_id=pid).scalar() or 0)+1
    row=ProgressStageScheme(project_id=pid,organization_id=user.organization_id,version=version,status='Draft',weights=body.weights,planning_publication_id=pub.id,created_by=user.id)
    db.add(row);db.commit();db.refresh(row)
    return serial(row)
@router.post('/{scheme_id}/approve')
def approve(pid:int,scheme_id:int,body:Approval,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    allowed(db,user,pid,'progress.policy.approve')
    row=db.query(ProgressStageScheme).filter_by(id=scheme_id,organization_id=user.organization_id,project_id=pid).one_or_none()
    if row is None:raise HTTPException(404,'Scheme not found')
    if row.status!='Draft':raise HTTPException(409,'Only draft schemes can be approved')
    if row.created_by==user.id:raise HTTPException(403,'Scheme proposer cannot self-approve')
    pub=db.query(PlanningPublication).filter_by(id=row.planning_publication_id,organization_id=user.organization_id,project_id=pid,status='Approved',is_current=True).one_or_none()
    if pub is None:raise HTTPException(409,'Referenced Planning baseline is no longer current and approved')
    predecessor=db.query(ProgressStageScheme).filter_by(organization_id=user.organization_id,project_id=pid,status='Approved').with_for_update().first()
    if predecessor and row.version<=predecessor.version:
        raise HTTPException(409,'Replacement version must be newer than current approved scheme')
    errors=validate_weights(row.weights)
    if errors:raise HTTPException(422,errors)
    if predecessor:predecessor.status='Superseded'
    row.status='Approved';row.approval_reference=body.approval_reference;row.approved_by=user.id;row.approved_at=datetime.now(timezone.utc)
    db.commit();return serial(row)
