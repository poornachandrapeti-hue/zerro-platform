"""Versioned approval records; approved weights are immutable."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, UniqueConstraint
from app.db import Base
class ProgressStageScheme(Base):
    __tablename__ = 'progress_stage_schemes'
    __table_args__ = (UniqueConstraint('project_id', 'version', name='uq_progress_stage_scheme_version'),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default='Draft')
    weights = Column(JSON, nullable=False)
    planning_publication_id = Column(Integer, ForeignKey('planning_publications.id'), nullable=False)
    approval_reference = Column(String(160), nullable=True)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    approved_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    approved_at = Column(DateTime(timezone=True), nullable=True)
