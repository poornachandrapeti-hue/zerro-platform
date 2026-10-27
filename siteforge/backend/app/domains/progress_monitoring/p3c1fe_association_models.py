"""P3C1F-E canonical QA inspection↔stored document association audit records."""
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class ProgressInspectionAttachmentLink(Base):
    __tablename__ = 'progress_inspection_attachment_links'
    __table_args__ = (
        UniqueConstraint('organization_id','project_id','inspection_id','progress_line_id','project_file_id',name='uq_progress_inspection_attachment_scope'),
        CheckConstraint("status IN ('Proposed','Approved','Rejected','Revoked')",name='ck_progress_inspection_attachment_status'),
        CheckConstraint('version > 0',name='ck_progress_inspection_attachment_version'),
        CheckConstraint('reviewer_user_id IS NULL OR reviewer_user_id <> proposer_user_id',name='ck_progress_inspection_attachment_independent'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'),nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'),nullable=False)
    activity_id: Mapped[int] = mapped_column(Integer,nullable=False)
    inspection_id: Mapped[int] = mapped_column(Integer,nullable=False)
    progress_line_id: Mapped[int] = mapped_column(ForeignKey('progress_lines.id'),nullable=False)
    project_file_id: Mapped[int] = mapped_column(ForeignKey('project_files.id'),nullable=False)
    stored_file_id: Mapped[int] = mapped_column(ForeignKey('stored_files.id'),nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64),nullable=False)
    status: Mapped[str] = mapped_column(String(20),nullable=False,default='Proposed')
    proposer_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'),nullable=False)
    reviewer_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    review_note: Mapped[str] = mapped_column(Text,nullable=False,default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False,default=lambda:datetime.now(timezone.utc))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer,nullable=False,default=1)

class ProgressInspectionAttachmentEvent(Base):
    __tablename__ = 'progress_inspection_attachment_events'
    __table_args__ = (CheckConstraint("action IN ('Proposed','Approved','Rejected','Revoked')",name='ck_progress_inspection_attachment_event_action'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey('progress_inspection_attachment_links.id'),nullable=False)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'),nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'),nullable=False)
    action: Mapped[str] = mapped_column(String(20),nullable=False)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'),nullable=False)
    note: Mapped[str] = mapped_column(Text,nullable=False,default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False,default=lambda:datetime.now(timezone.utc))
