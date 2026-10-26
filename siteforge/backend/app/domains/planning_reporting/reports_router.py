"""Planning phase 7: project-scoped reporting and non-mutating CSV import validation."""
import csv
import io
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from .workspace_router import access
from .workspace_models import PlanningSchedule, PlanningActivity, PlanningWBS, PlanningPublication
from .curves_router import get_curves

router = APIRouter(prefix='/api/projects/{pid}/planning', tags=['Planning Reports'])

class CsvPreview(BaseModel):
    schedule_id: int
    csv_text: str = Field(min_length=1, max_length=1500000)

TEMPLATE_COLUMNS = ['activity_code','activity_name','wbs_code','activity_type','duration_hours','source_type','source_id']

def validate_rows(text, existing_codes, wbs_codes):
    reader=csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or set(TEMPLATE_COLUMNS)-set(reader.fieldnames):
        raise ValueError('CSV must include: '+', '.join(TEMPLATE_COLUMNS))
    errors=[]; rows=[]; seen=set()
    for index,row in enumerate(reader,start=2):
        if index>10001: raise ValueError('Maximum 10,000 activity rows per validation')
        code=(row.get('activity_code') or '').strip()
        name=(row.get('activity_name') or '').strip()
        wbs=(row.get('wbs_code') or '').strip()
        kind=(row.get('activity_type') or '').strip()
        duration=(row.get('duration_hours') or '').strip()
        issues=[]
        if not code or len(code)>80:issues.append('Invalid activity_code')
        if not name or len(name)>200:issues.append('Invalid activity_name')
        if code in seen or code in existing_codes:issues.append('Duplicate activity_code')
        if wbs not in wbs_codes:issues.append('Unknown wbs_code')
        if kind not in ('Task','Milestone'):issues.append('Unsupported activity_type')
        try:
            hrs=float(duration)
            if hrs<0 or hrs>100000 or (kind=='Task' and hrs<=0):issues.append('Invalid duration_hours')
        except (TypeError, ValueError):issues.append('Invalid duration_hours')
        source_type=(row.get('source_type') or '').strip()
        source_id=(row.get('source_id') or '').strip()
        if bool(source_type)!=bool(source_id):issues.append('Source type/id must both be present or both blank')
        seen.add(code)
        if issues:errors.append({'row':index,'activity_code':code,'errors':issues})
        rows.append({'row':index,'activity_code':code,'activity_name':name,'wbs_code':wbs,'activity_type':kind})
    if not rows: errors.append({'row':1,'activity_code':'','errors':['No activity rows']})
    return {'total_rows':len(rows),'valid_rows':len(rows)-len(errors),'error_count':len(errors),'errors':errors[:250],
            'preview':rows[:30], 'preview_only':True,'written':0,
            'note':'Validation only; no schedule or baseline records are changed. Import confirmation is not implemented.'}

@router.post('/imports/activities/preview')
def preview(pid:int, body:CsvPreview, user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,True)
    schedule=db.query(PlanningSchedule).filter_by(id=body.schedule_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if not schedule:raise HTTPException(404,'Schedule not found')
    if schedule.status!='Draft':raise HTTPException(409,'Only draft schedules can be imported into')
    existing={x.code for x in db.query(PlanningActivity).filter_by(project_id=pid,schedule_id=schedule.id).all()}
    wbs={x.code for x in db.query(PlanningWBS).filter_by(project_id=pid,organization_id=user.organization_id,active=True).all()}
    try:return validate_rows(body.csv_text,existing,wbs)
    except (ValueError,csv.Error) as exc:raise HTTPException(422,str(exc))

@router.get('/reports/overview')
def overview(pid:int, user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid)
    schedules=db.query(PlanningSchedule).filter_by(project_id=pid,organization_id=user.organization_id).all()
    publications=db.query(PlanningPublication).filter_by(project_id=pid,organization_id=user.organization_id).order_by(PlanningPublication.id.desc()).all()
    current=next((p for p in publications if p.status=='Approved' and p.is_current),None)
    count={}
    for sch in schedules:
        activities=db.query(PlanningActivity).filter_by(project_id=pid,schedule_id=sch.id).all()
        count[sch.id]={'total':len(activities),'tasks':sum(a.activity_type=='Task' for a in activities),
                       'milestones':sum(a.activity_type=='Milestone' for a in activities),
                       'source_linked':sum(bool(a.source_type and a.source_id) for a in activities)}
    curves=get_curves(pid,current.id,user,db) if current else None
    return {'project_id':pid,'generated_at':datetime.now(timezone.utc).isoformat(),
            'approved_baseline':({'id':current.id,'revision':current.revision,'schedule_id':current.schedule_id,
                'submitted_at':current.submitted_at.isoformat() if current.submitted_at else None} if current else None),
            'schedules':[{'id':s.id,'name':s.name,'version':s.version,'status':s.status,'data_date':s.data_date.isoformat() if s.data_date else None,**count[s.id]} for s in schedules],
            'curves':curves,'basis':'Approved explicit cumulative targets and point-in-time verified captures only',
            'warning':None if current else 'No current approved published baseline; project variance is unavailable',
            'command_center_sync':'not_configured'}
