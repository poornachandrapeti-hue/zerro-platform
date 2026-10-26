"""Progress-owned rules and alert lifecycle; no external delivery assumptions."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, UniqueConstraint, Text, Boolean, JSON
from app.db import Base

class ProgressAlertPolicy(Base):
    __tablename__ = 'progress_alert_policies'
    id = Column(Integer,primary_key=True)
    organization_id = Column(Integer,nullable=False)
    project_id = Column(Integer,ForeignKey('projects.id'),nullable=False,unique=True)
    warning_pp = Column(Numeric(6,2),nullable=False,default=5)
    critical_pp = Column(Numeric(6,2),nullable=False,default=10)
    enabled = Column(Boolean,nullable=False,default=False)
    recipient_ids = Column(JSON,nullable=False,default=list)
    escalate_after_hours = Column(Integer,nullable=False,default=24)
    last_scanned_at = Column(DateTime(timezone=True),nullable=True)
    updated_by = Column(Integer,ForeignKey('users.id'),nullable=False)
    updated_at = Column(DateTime(timezone=True),nullable=False,default=lambda: datetime.now(timezone.utc))

class ProgressAlertEvent(Base):
    __tablename__ = 'progress_alert_events'
    __table_args__ = (UniqueConstraint('project_id','fingerprint',name='uq_progress_alert_fingerprint'),)
    id = Column(Integer,primary_key=True)
    organization_id = Column(Integer,nullable=False,index=True)
    project_id = Column(Integer,ForeignKey('projects.id'),nullable=False,index=True)
    fingerprint = Column(String(160),nullable=False)
    kind = Column(String(60),nullable=False)
    severity = Column(String(20),nullable=False)
    message = Column(Text,nullable=False)
    state = Column(String(24),nullable=False,default='Open')
    first_seen = Column(DateTime(timezone=True),nullable=False,default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime(timezone=True),nullable=False,default=lambda: datetime.now(timezone.utc))
    acknowledged_by = Column(Integer,ForeignKey('users.id'),nullable=True)
    acknowledged_at = Column(DateTime(timezone=True),nullable=True)
    escalated_by = Column(Integer,ForeignKey('users.id'),nullable=True)
    escalated_at = Column(DateTime(timezone=True),nullable=True)
