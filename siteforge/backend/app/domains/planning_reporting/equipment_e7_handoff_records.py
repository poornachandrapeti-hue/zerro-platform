"""E7B3 auditable verification receipts. Not a stock issue, hire invoice or GL journal."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, UniqueConstraint
from app.db import Base


class EquipmentAuthorityHandoff(Base):
    __tablename__ = 'planning_equipment_authority_handoffs'
    __table_args__ = (
        UniqueConstraint('organization_id', 'request_key', name='uq_equipment_authority_handoff_key'),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey('planning_equipment_assets.id'), nullable=False, index=True)
    authority_kind = Column(String(20), nullable=False)
    authority_id = Column(Integer, nullable=False)
    request_key = Column(String(100), nullable=False)
    evidence_ref = Column(String(240), nullable=False)
    authority_snapshot = Column(JSON, nullable=False)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
