"""Immutable report revisions and append-only decision history."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, JSON, ForeignKey, UniqueConstraint
from app.db import Base

def utcnow(): return datetime.now(timezone.utc)

class ProgressReport(Base):
    __tablename__ = 'progress_monitoring_reports'
    __table_args__ = (UniqueConstraint('project_id','report_number','revision',name='uq_progress_report_revision'),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    report_number = Column(String(80), nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    report_type = Column(String(12), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    status = Column(String(24), nullable=False, default='Draft')
    commentary = Column(Text, nullable=False, default='')
    prepared_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    reviewer_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    approver_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    snapshot = Column(JSON, nullable=True)
    source_cutoff = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    published_at = Column(DateTime(timezone=True), nullable=True)
    reason = Column(Text, nullable=False, default='')

class ProgressReportEvent(Base):
    __tablename__ = 'progress_report_events'
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, nullable=False, index=True)
    report_id = Column(Integer, ForeignKey('progress_monitoring_reports.id'), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    event = Column(String(32), nullable=False)
    note = Column(Text, nullable=False, default='')
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
