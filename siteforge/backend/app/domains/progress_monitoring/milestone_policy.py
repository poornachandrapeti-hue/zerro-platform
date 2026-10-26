"""Approved immutable per-stage milestone rule sets."""
from datetime import datetime,timezone
from sqlalchemy import Column,Integer,String,DateTime,ForeignKey,JSON,UniqueConstraint
from app.db import Base
from .milestone_calculation import policy_errors
REQUIRED={'engineering':('prepared','released'),'procurement':('ordered','received','accepted')}
class ProgressMilestonePolicy(Base):
    __tablename__='progress_milestone_policies'
    __table_args__=(UniqueConstraint('project_id','stage','version',name='uq_progress_milestone_policy_version'),)
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False)
    project_id=Column(Integer,ForeignKey('projects.id'),nullable=False,index=True)
    stage=Column(String(30),nullable=False)
    version=Column(Integer,nullable=False)
    status=Column(String(20),nullable=False,default='Draft')
    milestone_weights=Column(JSON,nullable=False)
    line_allocations=Column(JSON,nullable=True)
    planning_publication_id=Column(Integer,ForeignKey('planning_publications.id'),nullable=False)
    approval_reference=Column(String(160))
    created_by=Column(Integer,ForeignKey('users.id'),nullable=False)
    approved_by=Column(Integer,ForeignKey('users.id'))
    created_at=Column(DateTime(timezone=True),nullable=False,default=lambda:datetime.now(timezone.utc))
    approved_at=Column(DateTime(timezone=True))

def validate_policy(stage,weights):
    if stage not in REQUIRED:return ['Unsupported milestone stage']
    return policy_errors(weights,REQUIRED[stage])

def approved_result(preview,policy,full_scope,baseline_id):
    errors=list(preview.get('errors') or [])
    if policy is None or policy.status!='Approved':errors.append('Approved milestone policy unavailable')
    elif policy.planning_publication_id != baseline_id:errors.append('Approved policy baseline does not match requested baseline')
    if not full_scope:errors.append('Complete authorized project scope required')
    return {'earned_percent':preview.get('preview_percent') if not errors else None,
            'policy_status':'APPROVED_EARNED_PROGRESS' if not errors else 'UNAVAILABLE',
            'policy_version':policy.version if policy else None,'errors':list(dict.fromkeys(errors))}
