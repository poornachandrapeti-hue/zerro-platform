"""P2C2A persisted evidence binding proposals and append-only decision history.

No source ownership changes, earned-progress postings, or billing postings.
"""
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def now():
    return datetime.now(timezone.utc)


class ProgressEvidenceLink(Base):
    __tablename__ = "progress_evidence_links"
    __table_args__ = (
        UniqueConstraint("organization_id", "project_id", "progress_line_id", "inspection_request_id", name="uq_progress_evidence_pair"),
        CheckConstraint("status IN ('Proposed', 'Approved', 'Rejected', 'Revoked')", name="ck_progress_evidence_link_status"),
        CheckConstraint("accepted_quantity >= 0", name="ck_progress_evidence_accepted_qty"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("progress_reports.id"), nullable=False)
    progress_line_id: Mapped[int] = mapped_column(ForeignKey("progress_lines.id"), nullable=False, index=True)
    inspection_request_id: Mapped[int] = mapped_column(ForeignKey("quality_construction_requests.id"), nullable=False, index=True)
    accepted_quantity: Mapped[object] = mapped_column(Numeric(14, 3), nullable=False)
    binding_evidence_ref: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Proposed")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ProgressEvidenceLinkEvent(Base):
    __tablename__ = "progress_evidence_link_events"
    __table_args__ = (CheckConstraint("action IN ('Proposed', 'Approved', 'Rejected', 'Revoked')", name="ck_progress_evidence_link_action"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("progress_evidence_links.id"), nullable=False, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now)
