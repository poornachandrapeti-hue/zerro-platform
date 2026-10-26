"""Phase 4: read-only, source-owned execution measures linked to planning activities.

No fake history or contractual planned curves are calculated here. Source IDs must
be explicit and checked against project, organization, company and discipline.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.construction.models import ConstructionActivity, WorkPackage
from app.domains.construction.progress import activity_measures
from .workspace_router import access, ref
from .workspace_models import PlanningSchedule, PlanningActivity

router = APIRouter(prefix='/api/projects/{pid}/planning',tags=['Planning Actual Progress'])


def assemble(rows, source_lookup, meter):
    """Pure-ish composition helper: never count a duplicated source twice."""
    used=set()
    output=[]
    for plan in rows:
        status='unmapped'
        value=None
        source=None
        stype=(plan.source_type or '').strip().lower()
        sid=str(plan.source_id or '').strip()
        if stype in ('construction_activity','construction.activity') and sid.isdecimal():
            record=source_lookup.get(int(sid))
            if record is None:
                status='source_not_found'
            elif record['project_id']!=plan.project_id or record['company_id']!=plan.company_id or (plan.discipline_id is not None and record['discipline_id']!=plan.discipline_id):
                status='source_mismatch'
            elif int(sid) in used:
                status='duplicate_source_mapping'
            else:
                used.add(int(sid))
                value=meter(int(sid))
                status='linked' if value['verified_percent'] is not None else 'measurement_unavailable'
                source={'construction_activity_id':int(sid),'package_id':record['package_id']}
        elif stype or sid:
            status='unsupported_source_type'
        output.append({'activity_id':plan.id,'activity_code':plan.code,'activity_name':plan.name,
            'wbs_id':plan.wbs_id,'discipline_id':plan.discipline_id,'company_id':plan.company_id,
            'link_status':status,'source':source,'measurement':value})
    return output


@router.get('/schedules/{schedule_id}/actual-progress')
def actual_progress(pid:int,schedule_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid)
    schedule=ref(db,PlanningSchedule,schedule_id,pid)
    rows=db.query(PlanningActivity).filter_by(project_id=pid,schedule_id=schedule_id,organization_id=user.organization_id).order_by(PlanningActivity.code).all()
    if len(rows)>2000:raise HTTPException(503,'Schedule exceeds progress report limit')
    ids={int(a.source_id) for a in rows if (a.source_type or '').strip().lower() in ('construction_activity','construction.activity') and str(a.source_id or '').isdecimal()}
    matching=db.query(ConstructionActivity,WorkPackage).join(WorkPackage,WorkPackage.id==ConstructionActivity.package_id).filter(
        ConstructionActivity.id.in_(ids),ConstructionActivity.project_id==pid,
        ConstructionActivity.organization_id==user.organization_id,ConstructionActivity.active==True,
        WorkPackage.project_id==pid,WorkPackage.organization_id==user.organization_id,WorkPackage.status!="Cancelled").all() if ids else []
    lookup={a.id:{'project_id':a.project_id,'company_id':a.company_id,'discipline_id':p.discipline_id,'package_id':p.id} for a,p in matching}
    activity_map={a.id:a for a,p in matching}
    measured={}
    def measure(id):
        if id not in measured:
            raw=activity_measures(db,activity_map[id])
            measured[id]={k:raw.get(k) for k in ('method','scope_quantity','unit','reported_quantity','verified_quantity','accepted_quantity','reported_percent','verified_percent','accepted_percent')}
        return measured[id]
    result=assemble(rows,lookup,measure)
    statuses={name:sum(1 for r in result if r['link_status']==name) for name in sorted({r['link_status'] for r in result})}
    return {'schedule_id':schedule.id,'schedule_version':schedule.version,'schedule_status':schedule.status,
        'data_date':schedule.data_date.isoformat(),'retrieved_at':datetime.now(timezone.utc).isoformat(),
        'actuals_as_of_data_date':False,'basis':'Current authoritative execution totals; NOT historical as-of data date',
        'planned_curve_available':False,'historical_s_curve_available':False,
        'rollup_percent':None,'rollup_note':'No weighted total computed without approved nonduplicated activity weights',
        'link_counts':statuses,'activities':result}
