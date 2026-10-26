"""Isolated, read-only Planning feed for authorized partner companies."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import Project, Membership, Role, User
from app.domains.identity_projects.security import authenticated
from .workspace_models import PlanningActivity, PlanningSchedule
from .partner_scope import visible_to_membership, partner_activity_projection

router = APIRouter(prefix='/api/projects/{pid}/partner-planning', tags=['Partner Planning'])


def authorized_memberships(db, user, pid):
    project = db.get(Project, pid)
    if project is None or project.organization_id != user.organization_id or not user.active:
        raise HTTPException(404, 'Project not found')
    # Even an organization administrator must explicitly use internal Planning APIs.
    # Partner access requires a scoped project membership with partner permission.
    granted = []
    for membership in db.query(Membership).filter_by(project_id=pid, user_id=user.id, active=True).all():
        role = db.get(Role, membership.role_id)
        if role and 'planning.partner.view' in (role.permissions or []) and 'planning.manage' not in (role.permissions or []) and 'planning.view' not in (role.permissions or []):
            granted.append(membership)
    if not granted:
        raise HTTPException(403, 'Partner Planning membership required')
    return granted


@router.get('/schedules/{schedule_id}/activities')
def partner_activities(pid:int, schedule_id:int, user:User=Depends(authenticated), db:Session=Depends(get_db)):
    memberships = authorized_memberships(db, user, pid)
    schedule = db.query(PlanningSchedule).filter_by(project_id=pid,id=schedule_id).one_or_none()
    # Draft scenarios, private forecasts and unpublished baselines must not reach partners.
    if schedule is None or schedule.status != 'Approved' or schedule.kind == 'Scenario':
        raise HTTPException(404, 'Published schedule not found')
    result = []
    for activity in db.query(PlanningActivity).filter_by(project_id=pid,schedule_id=schedule_id).order_by(PlanningActivity.code).all():
        if any(visible_to_membership(activity.company_id, activity.discipline_id, m) for m in memberships):
            result.append(partner_activity_projection(activity))
    return {'schedule_version':schedule.version,'activities':result}


@router.get('/schedules')
def partner_schedules(pid:int, user:User=Depends(authenticated), db:Session=Depends(get_db)):
    memberships = authorized_memberships(db, user, pid)
    schedules = db.query(PlanningSchedule).filter_by(project_id=pid, status='Approved').all()
    result = []
    for schedule in schedules:
        if schedule.kind == 'Scenario':
            continue
        count = sum(
            1 for activity in db.query(PlanningActivity).filter_by(project_id=pid, schedule_id=schedule.id).all()
            if any(visible_to_membership(activity.company_id, activity.discipline_id, m) for m in memberships)
        )
        if count:
            result.append({'id': schedule.id, 'version': schedule.version, 'activity_count': count})
    return {'schedules': result}


from datetime import date, datetime, timezone
from pydantic import BaseModel, Field
from .workspace_models import PartnerPlanningCommitment, PlanningLookaheadItem, PlanningLookahead
from .workspace_router import access

class PartnerCommitmentInput(BaseModel):
    commitment: str
    expected_date: date | None = None
    note: str = Field(default='', max_length=1000)

def _scoped_activity(db, pid, schedule_id, activity_id, memberships):
    schedule = db.query(PlanningSchedule).filter_by(project_id=pid, id=schedule_id, status='Approved').one_or_none()
    if not schedule or schedule.kind == 'Scenario':
        raise HTTPException(404, 'Published schedule not found')
    activity = db.query(PlanningActivity).filter_by(project_id=pid, schedule_id=schedule_id, id=activity_id).one_or_none()
    if not activity:
        raise HTTPException(404, 'Activity not found')
    allowed = [m for m in memberships if visible_to_membership(activity.company_id, activity.discipline_id, m)]
    if not allowed:
        raise HTTPException(404, 'Activity not found')
    return activity

@router.post('/schedules/{schedule_id}/activities/{activity_code}/commitments', status_code=201)
def submit_partner_commitment(pid:int, schedule_id:int, activity_code:str, body:PartnerCommitmentInput,
                              user:User=Depends(authenticated), db:Session=Depends(get_db)):
    memberships = authorized_memberships(db, user, pid)
    activity = db.query(PlanningActivity).filter_by(project_id=pid, schedule_id=schedule_id, code=activity_code).one_or_none()
    if not activity: raise HTTPException(404, "Activity not found")
    activity = _scoped_activity(db, pid, schedule_id, activity.id, memberships)
    if body.commitment not in ('Committed','Declined','AtRisk'):
        raise HTTPException(422, 'Unsupported commitment')
    if body.commitment in ('Declined','AtRisk') and not body.note.strip():
        raise HTTPException(422, 'Reason required')
    # One new submission per request; previous decisions remain in the audit trail.
    row = PartnerPlanningCommitment(organization_id=user.organization_id, project_id=pid,
        schedule_id=schedule_id, activity_id=activity.id, company_id=activity.company_id,
        submitted_by=user.id, commitment=body.commitment, expected_date=body.expected_date, note=body.note.strip())
    db.add(row); db.commit(); db.refresh(row)
    return {'id':row.id, 'status':row.status, 'commitment':row.commitment}

@router.get('/commitments')
def list_partner_commitments(pid:int, user:User=Depends(authenticated), db:Session=Depends(get_db)):
    memberships = authorized_memberships(db, user, pid)
    rows=db.query(PartnerPlanningCommitment).filter_by(project_id=pid, organization_id=user.organization_id).order_by(PartnerPlanningCommitment.id.desc()).limit(250).all()
    items=[]
    for row in rows:
        activity=db.query(PlanningActivity).filter_by(project_id=pid,id=row.activity_id, schedule_id=row.schedule_id).one_or_none()
        if activity and activity.company_id==row.company_id and any(visible_to_membership(activity.company_id,activity.discipline_id,m) for m in memberships):
            items.append({'id':row.id, 'activity_code':activity.code,'commitment':row.commitment,'expected_date':row.expected_date,'note':row.note,'status':row.status,'review_note':row.review_note})
    return {'items':items}

def reviewer_memberships(db, user, pid, write=False):
    """Return ONLY authorized internal memberships; admin scope is explicit."""
    access(db, user, pid, write)
    if user.organization_admin:
        return None  # full project visibility, after active/admin access check
    granted = []
    required = 'planning.manage' if write else 'planning.view'
    for m in db.query(Membership).filter_by(project_id=pid, user_id=user.id, active=True).all():
        role = db.get(Role, m.role_id)
        permissions = set(role.permissions or []) if role else set()
        if 'planning.partner.view' in permissions:
            continue
        if required in permissions or (not write and 'planning.manage' in permissions):
            granted.append(m)
    return granted


def reviewer_can_access(activity, memberships):
    """Full-project admin bypasses; everyone else needs matching company/scope."""
    if memberships is None:
        return True
    return any(visible_to_membership(activity.company_id, activity.discipline_id, m)
               for m in memberships)


class PartnerReviewInput(BaseModel):
    action: str
    note: str = Field(default='',max_length=1000)

@router.get('/internal/commitments')
def internal_commitments(pid:int, user:User=Depends(authenticated), db:Session=Depends(get_db)):
    memberships = reviewer_memberships(db, user, pid)
    # Filter before applying response limit so out-of-scope entries cannot crowd out results.
    rows = db.query(PartnerPlanningCommitment).filter_by(project_id=pid, organization_id=user.organization_id).order_by(PartnerPlanningCommitment.id.desc()).all()
    items = []
    for r in rows:
        activity = db.query(PlanningActivity).filter_by(project_id=pid, schedule_id=r.schedule_id, id=r.activity_id).one_or_none()
        if activity is None or activity.company_id != r.company_id or not reviewer_can_access(activity, memberships):
            continue
        items.append({'id':r.id,'activity_id':r.activity_id,'company_id':r.company_id,'commitment':r.commitment,'note':r.note,'status':r.status,'submitted_at':r.submitted_at,'expected_date':r.expected_date,'review_note':r.review_note,'submitted_by':r.submitted_by})
        if len(items) >= 250:
            break
    return {'items': items}

@router.post('/internal/commitments/{commitment_id}/review')
def review_partner_commitment(pid:int, commitment_id:int, body:PartnerReviewInput, user:User=Depends(authenticated), db:Session=Depends(get_db)):
    memberships = reviewer_memberships(db, user, pid, True)
    row=db.query(PartnerPlanningCommitment).filter_by(project_id=pid, organization_id=user.organization_id,id=commitment_id).one_or_none()
    if not row: raise HTTPException(404,'Commitment not found')
    activity = db.query(PlanningActivity).filter_by(project_id=pid, schedule_id=row.schedule_id, id=row.activity_id).one_or_none()
    if activity is None or activity.company_id != row.company_id or not reviewer_can_access(activity, memberships):
        raise HTTPException(404, 'Commitment not found')
    if row.status!='Submitted': raise HTTPException(409,'Already reviewed')
    if row.submitted_by==user.id: raise HTTPException(403,'Independent reviewer required')
    if body.action not in ('Accepted','Returned'): raise HTTPException(422,'Invalid decision')
    if body.action=='Returned' and not body.note.strip(): raise HTTPException(422,'Return reason required')
    row.status=body.action;row.review_note=body.note.strip();row.reviewed_by=user.id;row.reviewed_at=datetime.now(timezone.utc)
    db.commit()
    return {'id':row.id,'status':row.status}
