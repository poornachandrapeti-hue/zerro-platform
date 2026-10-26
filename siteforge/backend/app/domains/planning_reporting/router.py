"""SiteForge-authoritative approved schedule register.

Only organization administrators can approve; immutable revisions are audited.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import hmac
from app.db import get_db
from app.config import settings
from app.domains.identity_projects.models import Project, User, Audit
from app.domains.identity_projects.security import authenticated
from app.baseline_validation import validate_document
from .models import PlanningBaseline

router = APIRouter(prefix="/api", tags=["Planning baselines"])

class BaselineDraft(BaseModel):
    revision: str = Field(min_length=1, max_length=80)
    activities: list[dict] = Field(min_length=1)


def _project(db, user, pid):
    project = db.get(Project, pid)
    if not project or project.organization_id != user.organization_id:
        raise HTTPException(404, "Project not found")
    return project

@router.post("/projects/{pid}/planning/baselines", status_code=201)
def create_baseline(pid: int, body: BaselineDraft, user: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, user, pid)
    if not user.organization_admin:
        raise HTTPException(403, "Organization administrator required to register baselines")
    document = {"project_code":project.code, "revision":body.revision, "approval_status":"draft", "activities":body.activities}
    try:
        validate_document(document, require_approved=False)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc))
    row = PlanningBaseline(organization_id=user.organization_id, project_id=pid, revision=body.revision, status="draft", document=document, created_by=user.id)
    db.add(row)
    try:
        db.flush()
        db.add(Audit(organization_id=user.organization_id, actor_id=user.id, action="create", resource="planning_baseline_revisions", resource_id=row.id, project_id=pid, details={"revision":row.revision}))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Baseline revision already exists")
    return {"id":row.id,"status":row.status,"revision":row.revision}

@router.post("/projects/{pid}/planning/baselines/{revision_id}/approve")
def approve_baseline(pid: int, revision_id: int, approval_reference: str, user: User = Depends(authenticated), db: Session = Depends(get_db)):
    _project(db, user, pid)
    if not user.organization_admin:
        raise HTTPException(403, "Organization administrator approval required")
    row = db.query(PlanningBaseline).filter_by(id=revision_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if not row:
        raise HTTPException(404, "Revision not found")
    if row.created_by == user.id:
        raise HTTPException(403, "A separate organization administrator must approve this revision")
    if row.status != "draft":
        raise HTTPException(409, "Only draft revisions may be approved")
    if not approval_reference.strip():
        raise HTTPException(422, "Approval reference required")
    now = datetime.now(timezone.utc)
    document = dict(row.document)
    document.update(approval_status="approved",approval_reference=approval_reference.strip(),approved_by=str(user.id),approved_on=now.date().isoformat())
    validate_document(document, require_approved=True)
    row.status="approved"
    row.document=document
    row.approved_by=user.id
    row.approved_at=now
    db.add(Audit(organization_id=user.organization_id, actor_id=user.id, action="approve", resource="planning_baseline_revisions", resource_id=row.id,project_id=pid,details={"revision":row.revision,"approval_reference":approval_reference}))
    db.commit()
    return {"id":row.id,"status":row.status,"revision":row.revision}

@router.get("/projects/{pid}/planning/baselines")
def list_baselines(pid: int, user: User = Depends(authenticated), db: Session = Depends(get_db)):
    _project(db,user,pid)
    if not user.organization_admin:
        raise HTTPException(403, "Organization administrator required")
    rows=db.query(PlanningBaseline).filter_by(project_id=pid,organization_id=user.organization_id).order_by(PlanningBaseline.id.desc()).all()
    return [{"id":row.id,"revision":row.revision,"status":row.status,"approved_at":row.approved_at} for row in rows]

@router.get("/integration/vision360/projects/{project_code}/approved-baseline")
def integration_approved_baseline(project_code: str,x_vision_service_key: str | None = Header(default=None),db: Session = Depends(get_db)):
    secret=settings.vision360_service_key
    if not secret or not x_vision_service_key or not hmac.compare_digest(secret,x_vision_service_key):
        raise HTTPException(403,"Integration unavailable")
    org=settings.vision360_organization_id
    if not org:
        raise HTTPException(503,"Integration organization not configured")
    project=db.query(Project).filter_by(organization_id=org,code=project_code).one_or_none()
    if not project:
        raise HTTPException(404,"Project not found")
    rows=db.query(PlanningBaseline).filter_by(project_id=project.id,organization_id=org,status="approved").order_by(PlanningBaseline.approved_at.desc(),PlanningBaseline.id.desc()).limit(2).all()
    if not rows:
        return {"status":"not_configured", "project_code":project.code}
    doc=rows[0].document
    validate_document(doc,require_approved=True)
    return {"status":"approved", "project_code":project.code, "baseline":doc}
