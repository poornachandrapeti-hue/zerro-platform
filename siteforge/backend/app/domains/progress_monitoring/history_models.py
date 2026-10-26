"""Append-only source-attributed observations for real Progress history."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, DateTime, Date, Numeric, JSON, ForeignKey, UniqueConstraint
from app.db import Base

class ProgressObservation(Base):
    __tablename__ = 'progress_observations'
    __table_args__ = (UniqueConstraint('project_id','publication_id','data_date',name='uq_progress_observation_day'),)
    id = Column(Integer,primary_key=True)
    organization_id = Column(Integer,nullable=False,index=True)
    project_id = Column(Integer,ForeignKey('projects.id'),nullable=False,index=True)
    publication_id = Column(Integer,ForeignKey('planning_publications.id'),nullable=False)
    data_date = Column(Date,nullable=False)
    captured_at = Column(DateTime(timezone=True),nullable=False,default=lambda: datetime.now(timezone.utc))
    captured_by = Column(Integer,ForeignKey('users.id'),nullable=False)
    verified_percent = Column(Numeric(7,3),nullable=False)
    activity_snapshot = Column(JSON,nullable=False)
