"""Versioned forecast snapshots. Distinct from contractual and approved schedule baselines."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, JSON, Text, UniqueConstraint
from app.db import Base

class PlanningForecastRevision(Base):
    __tablename__ = "planning_forecast_revisions"
    __table_args__ = (UniqueConstraint("schedule_id", "revision", name="uq_planning_forecast_revision"),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    schedule_id = Column(Integer, ForeignKey("planning_schedules.id"), nullable=False)
    revision = Column(Integer, nullable=False)
    data_date = Column(Date, nullable=False)
    status = Column(String(24), nullable=False, default="Draft")
    inputs = Column(JSON, nullable=False)
    result = Column(JSON, nullable=False)
    submitted_by = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    reviewed_by = Column(Integer, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_note = Column(Text, nullable=False, default="")
