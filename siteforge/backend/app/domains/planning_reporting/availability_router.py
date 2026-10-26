"""Read-only resource evidence for authorized internal project planners."""
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.workforce.models import Deployment
from .workspace_router import access,ref
from .workspace_models import PlanningSchedule,PlanningResourceDemand
from .resource_availability import capacity_evidence,mobilization_summary

router=APIRouter(prefix='/api/projects/{pid}/planning',tags=['Planning Resource Evidence'])

@router.get('/schedules/{schedule_id}/resource-availability-evidence')
def resource_availability_evidence(pid:int,schedule_id:int,data_date:date,
        user:User=Depends(authenticated),db:Session=Depends(get_db)):
    access(db,user,pid,write=True) # internal planning managers only; not partner-facing
    ref(db,PlanningSchedule,schedule_id,pid)
    demands=db.query(PlanningResourceDemand).filter_by(organization_id=user.organization_id,
        project_id=pid,schedule_id=schedule_id).all()
    deployments=db.query(Deployment).filter_by(organization_id=user.organization_id,project_id=pid).all()
    return {'schedule_id':schedule_id,'data_date':data_date.isoformat(),
        'resource_demands':capacity_evidence(demands,as_of=data_date),
        'workforce_mobilization':mobilization_summary(deployments,as_of=data_date),
        'equipment_availability':'unavailable-no-authoritative-allocation-source',
        'confirmed_shift_capacity':False,'suitable_for_resource_leveling':False,
        'basis':'Planning capacity values are unverified references; HR mobilization is not shift availability.'}
