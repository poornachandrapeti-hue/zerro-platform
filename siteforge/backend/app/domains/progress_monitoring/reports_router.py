"""Progress report workflow; no source transaction approvals occur here."""
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from .report_exports import xlsx_bytes, pdf_bytes, check_sections
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import get_db
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.models import User, Membership, Role
from app.domains.planning_reporting.workspace_router import access
from .router import dashboard, progress_scope
from .reports_models import ProgressReport, ProgressReportEvent

router=APIRouter(prefix='/api/projects/{pid}/progress/reports',tags=['Progress Reports'])

# Dedicated Progress grants, with existing Planning-grant compatibility until RBAC migration.
PROGRESS_PERMISSIONS = {
    'planning.view': 'progress.view',
    'planning.manage': 'progress.prepare',
    'progress.review': 'progress.review',
    'progress.approve': 'progress.approve',
    'progress.publish': 'progress.publish',
    'progress.policy.approve': 'progress.policy.approve',
}

def permission_granted(grants, permission):
    """No partner grant or view-only grant can authorize a Progress write."""
    grants=set(grants or [])
    if 'planning.partner.view' in grants:return False
    dedicated=PROGRESS_PERMISSIONS.get(permission, permission)
    if dedicated in grants:return True
    # Compatibility with existing ZerroBuild Planning roles (not partner roles).
    if permission=='planning.view':return bool({'planning.view','planning.manage','progress.review','progress.approve','progress.publish','progress.prepare','progress.policy.approve'} & grants)
    if permission=='planning.manage':return 'planning.manage' in grants
    if permission in ('progress.review','progress.approve','progress.publish','progress.policy.approve'):
        return 'planning.manage' in grants
    return False

def allowed(db,user,pid,permission):
    access(db,user,pid)
    scope=progress_scope(db,user,pid)
    if not scope['all']:
        raise HTTPException(403,'Report workflow requires an unrestricted internal project membership')
    if user.organization_admin:return
    for m in db.query(Membership).filter_by(project_id=pid,user_id=user.id,active=True).all():
        role=db.get(Role,m.role_id)
        if m.scope=='ALL' and role and permission_granted(role.permissions,permission):return
    raise HTTPException(403,f'{PROGRESS_PERMISSIONS.get(permission,permission)} permission required')

def require_assigned_reviewer_access(db, user, pid):
    """Revalidate current unrestricted internal membership at decision time.

    Being listed as reviewer/approver is not itself a permission grant.
    """
    allowed(db, user, pid, 'progress.review')

def read_row(db,user,pid,id):
    allowed(db,user,pid,'planning.view')
    row=db.query(ProgressReport).filter_by(id=id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if row is None: raise HTTPException(404,'Progress report not found')
    return row

def serial(row):
    return {k:getattr(row,k) for k in ('id','project_id','report_number','revision','report_type','period_start','period_end','data_date','status','commentary','prepared_by','reviewer_id','approver_id','reason','created_at','updated_at','published_at','source_cutoff')}

def event(db,row,user,action,note=''):
    db.add(ProgressReportEvent(organization_id=row.organization_id,project_id=row.project_id,report_id=row.id,actor_id=user.id,event=action,note=note))

def eligible_snapshot(data):
    # Reports cannot hide invalid quantities, missing mappings, or unavailable baseline.
    if not data.get('publication') or data.get('visibility')!='project': return False
    if data.get('exceptions'): return False
    if not data.get('actuals') or data['stages']['construction']['percent'] is None:return False
    return True

class Create(BaseModel):
    report_number:str=Field(min_length=1,max_length=80)
    report_type:str
    period_start:date
    period_end:date
    data_date:date
    reviewer_id:int=Field(gt=0)
    approver_id:int=Field(gt=0)
    commentary:str=Field(default='',max_length=12000)
    @model_validator(mode='after')
    def validate(self):
        if self.report_type not in ('Daily','Weekly','Monthly'):raise ValueError('Invalid reporting period')
        if not self.period_start<=self.data_date<=self.period_end:raise ValueError('Data date outside period')
        if self.period_end>date.today():raise ValueError('Cannot create future period report')
        return self

class Note(BaseModel):
    note:str=Field(default='',max_length=12000)

@router.get('')
def list_reports(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    allowed(db,user,pid,'planning.view')
    return [serial(r) for r in db.query(ProgressReport).filter_by(project_id=pid,organization_id=user.organization_id).order_by(ProgressReport.id.desc()).limit(200)]

@router.post('',status_code=201)
def create(pid:int,body:Create,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    allowed(db,user,pid,'planning.manage')
    if user.id in (body.reviewer_id,body.approver_id) or body.reviewer_id==body.approver_id:
        raise HTTPException(422,'Preparer, reviewer and approver must be different')
    for uid, required in ((body.reviewer_id,'progress.review'),(body.approver_id,'progress.approve')):
        target=db.get(User,uid)
        if not target or not target.active or target.organization_id!=user.organization_id:
            raise HTTPException(422,'Invalid reviewer or approver')
        if not target.organization_admin:
            memberships=db.query(Membership).filter_by(user_id=uid,project_id=pid,active=True).all()
            if not any(m.scope=='ALL' and permission_granted((db.get(Role,m.role_id).permissions if db.get(Role,m.role_id) else []),required) for m in memberships):
                raise HTTPException(422,f'Assigned user needs unrestricted {required} permission')
    prior=db.query(func.max(ProgressReport.revision)).filter_by(organization_id=user.organization_id,project_id=pid,report_number=body.report_number).scalar()
    if prior is not None:raise HTTPException(409,'Report number exists; create a revision from the existing report')
    row=ProgressReport(organization_id=user.organization_id,project_id=pid,prepared_by=user.id,revision=1,**body.model_dump())
    db.add(row);db.flush();event(db,row,user,'Created');db.commit();db.refresh(row)
    return serial(row)

@router.get('/{id}')
def get_report(pid:int,id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    row=read_row(db,user,pid,id)
    result=serial(row);result['snapshot']=row.snapshot
    result['events']=[{'actor_id':e.actor_id,'event':e.event,'note':e.note,'created_at':e.created_at} for e in db.query(ProgressReportEvent).filter_by(report_id=row.id).order_by(ProgressReportEvent.id)]
    return result

@router.post('/{id}/submit')
def submit(pid:int,id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    row=read_row(db,user,pid,id)
    allowed(db,user,pid,'planning.manage')
    if row.status!='Draft' or row.prepared_by!=user.id:raise HTTPException(409,'Only preparer can submit a draft')
    data=dashboard(pid,None,None,None,user,db)
    # The dashboard represents a live current-state read, not an as-of query.
    # Never freeze today's achievements under a historical report data date.
    if row.data_date != date.today():
        raise HTTPException(422, 'Historical reporting cutoff is not supported by live source APIs; select today as data date or implement source as-of queries')
    if not eligible_snapshot(data):raise HTTPException(422,'Cannot submit: source exceptions, missing approved baseline or incomplete weighted construction data')
    row.snapshot=data;row.source_cutoff=datetime.now(timezone.utc)
    row.status='Pending Review';row.updated_at=datetime.now(timezone.utc)
    event(db,row,user,'Submitted');db.commit();return serial(row)

@router.post('/{id}/review')
def review(pid:int,id:int,body:Note,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    row=read_row(db,user,pid,id)
    require_assigned_reviewer_access(db,user,pid)
    if row.status!='Pending Review' or user.id!=row.reviewer_id:raise HTTPException(403,'Assigned reviewer required for pending review')
    row.status='Reviewed';row.updated_at=datetime.now(timezone.utc)
    event(db,row,user,'Reviewed',body.note);db.commit();return serial(row)

@router.post('/{id}/return')
def return_report(pid:int,id:int,body:Note,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    row=read_row(db,user,pid,id)
    allowed(db,user,pid,'progress.review' if row.status=='Pending Review' else 'progress.approve')
    if not body.note.strip():raise HTTPException(422,'Reason required')
    if row.status=='Pending Review' and row.reviewer_id==user.id or row.status=='Reviewed' and row.approver_id==user.id:
        row.status='Returned';row.updated_at=datetime.now(timezone.utc)
        event(db,row,user,'Returned',body.note);db.commit();return serial(row)
    raise HTTPException(403,'Assigned reviewer or approver required')

@router.post('/{id}/approve')
def approve(pid:int,id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    row=read_row(db,user,pid,id)
    allowed(db,user,pid,'progress.approve')
    if row.status!='Reviewed' or user.id!=row.approver_id:raise HTTPException(403,'Assigned approver required after review')
    row.status='Approved';row.updated_at=datetime.now(timezone.utc)
    event(db,row,user,'Approved');db.commit();return serial(row)

@router.post('/{id}/publish')
def publish(pid:int,id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    row=read_row(db,user,pid,id)
    allowed(db,user,pid,'progress.publish')
    if row.status!='Approved' or user.id!=row.approver_id:raise HTTPException(403,'Assigned approver required to publish')
    row.status='Published';row.published_at=datetime.now(timezone.utc);row.updated_at=row.published_at
    event(db,row,user,'Published');db.commit();return serial(row)

@router.post('/{id}/revise',status_code=201)
def revise(pid:int,id:int,body:Note,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    row=read_row(db,user,pid,id);allowed(db,user,pid,'planning.manage')
    if row.status not in ('Published','Returned') or not body.note.strip():raise HTTPException(422,'A published/returned report and revision reason are required')
    latest=db.query(func.max(ProgressReport.revision)).filter_by(project_id=pid,organization_id=user.organization_id,report_number=row.report_number).scalar()
    if latest!=row.revision:raise HTTPException(409,'Revise only the latest report revision')
    revision=ProgressReport(organization_id=row.organization_id,project_id=pid,report_number=row.report_number,revision=row.revision+1,report_type=row.report_type,period_start=row.period_start,period_end=row.period_end,data_date=row.data_date,prepared_by=user.id,reviewer_id=row.reviewer_id,approver_id=row.approver_id,commentary=row.commentary,reason=body.note,status='Draft')
    db.add(revision);db.flush();event(db,revision,user,'Revised',body.note);db.commit();db.refresh(revision);return serial(revision)


@router.get('/{id}/export/{format}')
def export_report(pid:int,id:int,format:str,sections:list[str]|None=Query(default=None),user:User=Depends(authenticated),db:Session=Depends(get_db)):
    # Re-evaluate project authorization at request time. A report snapshot is
    # full project scope, so filtered users cannot obtain the export.
    row=read_row(db,user,pid,id)
    if row.snapshot is None:
        raise HTTPException(409,'Report has no frozen snapshot yet')
    if format not in ('xlsx','pdf'):
        raise HTTPException(404,'Unsupported report format')
    try:
        parts=check_sections(sections)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    content=xlsx_bytes(row,row.snapshot,parts) if format=='xlsx' else pdf_bytes(row,row.snapshot,parts)
    mimetype=('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if format=='xlsx' else 'application/pdf')
    return Response(content,media_type=mimetype,headers={
        'Content-Disposition':f'attachment; filename="progress-report-{row.id}-rev-{row.revision}.{format}"',
        'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
