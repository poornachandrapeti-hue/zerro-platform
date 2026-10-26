"""Approved project schedule baseline revisions, separate from construction date references."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, ForeignKey, JSON, DateTime, UniqueConstraint
from app.db import Base

class PlanningBaseline(Base):
    __tablename__ = "planning_baseline_revisions"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, nullable=False, index=True)
    revision = Column(String(80), nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    document = Column(JSON, nullable=False)
    created_by = Column(Integer, nullable=False)
    approved_by = Column(Integer, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    __table_args__ = (UniqueConstraint("project_id", "revision", name="uq_planning_baseline_project_revision"),)
