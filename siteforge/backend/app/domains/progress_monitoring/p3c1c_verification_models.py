"""P3C1C: verification-attestation persistence schema only.

These records do not replace Planning, Construction or QA source ownership.
No API routes, progress publication, or billing postings are introduced here.
"""
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class ProgressQuantityVerification(Base):
    __tablename__ = 'progress_quantity_verifications'
    __table_args__ = (
        UniqueConstraint('organization_id', 'project_id', 'progress_line_id', 'baseline_revision_id', 'source_revision', name='uq_progress_qty_verification_revision'),
        CheckConstraint("status IN ('Proposed', 'Approved', 'Rejected', 'Revoked')", name='ck_progress_qty_verification_status'),
        CheckConstraint('verified_quantity > 0', name='ck_progress_qty_verification_positive'),
        CheckConstraint('version > 0', name='ck_progress_qty_verification_version'),
        CheckConstraint('reviewer_user_id IS NULL OR reviewer_user_id <> proposer_user_id', name='ck_progress_qty_verification_independent'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False, index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey('progress_reports.id'), nullable=False)
    progress_line_id: Mapped[int] = mapped_column(ForeignKey('progress_lines.id'), nullable=False, index=True)
    activity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_revision_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_revision: Mapped[str] = mapped_column(String(100), nullable=False)
    verification_reference: Mapped[str] = mapped_column(String(240), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    verified_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='Proposed')
    proposer_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    reviewer_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    review_note: Mapped[str] = mapped_column(Text, nullable=False, default='')
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ProgressQuantityVerificationEvent(Base):
    __tablename__ = 'progress_quantity_verification_events'
    __table_args__ = (
        CheckConstraint("action IN ('Proposed', 'Approved', 'Rejected', 'Revoked')", name='ck_progress_qty_verification_event_action'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    verification_id: Mapped[int] = mapped_column(ForeignKey('progress_quantity_verifications.id'), nullable=False, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
