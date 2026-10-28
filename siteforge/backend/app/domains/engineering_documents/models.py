from datetime import date, datetime, timezone

from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def now():
    return datetime.now(timezone.utc)


class StoredFile(Base):
    __tablename__ = "stored_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String(100))
    original_name: Mapped[str] = mapped_column(String(200))
    storage_name: Mapped[str] = mapped_column(String(80))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    scan_status: Mapped[str] = mapped_column(String(20), default="available")


class ProjectFile(Base):
    __tablename__ = "project_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("stored_files.id"))
    category: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Drawing(Base):
    __tablename__ = "drawings"
    __table_args__ = (UniqueConstraint("project_id", "number_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[str] = mapped_column(String(80))
    number_key: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(200))
    drawing_type: Mapped[str] = mapped_column(String(80), default="General")
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    responsible_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    planned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="Normal")
    preparation: Mapped[str] = mapped_column(String(30), default="Planned")
    work_reference: Mapped[str] = mapped_column(String(80), default="")
    provenance: Mapped[str] = mapped_column(String(20), default="manual")
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("drawing_categories.id"), nullable=True
    )
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    planned_submission: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_approval: Mapped[date | None] = mapped_column(Date, nullable=True)
    remarks: Mapped[str] = mapped_column(Text, default="")
    record_status: Mapped[str] = mapped_column(String(20), default="Active")
    cancellation_reason: Mapped[str] = mapped_column(Text, default="")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    deletion_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DrawingRevision(Base):
    __tablename__ = "drawing_revisions"
    __table_args__ = (UniqueConstraint("drawing_id", "code_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    drawing_id: Mapped[int] = mapped_column(ForeignKey("drawings.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    code_key: Mapped[str] = mapped_column(String(20))
    sequence: Mapped[int] = mapped_column(Integer)
    file_id: Mapped[int] = mapped_column(ForeignKey("stored_files.id"))
    review_state: Mapped[str] = mapped_column(String(40), default="Not Submitted")
    release_state: Mapped[str] = mapped_column(String(30), default="Not Released")
    description: Mapped[str] = mapped_column(Text, default="")
    issue_purpose: Mapped[str] = mapped_column(String(30), default="Review")
    released_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    release_reference: Mapped[str] = mapped_column(String(120), default="")
    client_outcome: Mapped[str] = mapped_column(String(40), default="")
    external_reviewer: Mapped[str] = mapped_column(String(200), default="")
    decision_reference: Mapped[str] = mapped_column(String(200), default="")
    decision_recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    prepared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class DrawingComment(Base):
    __tablename__ = "drawing_comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey("drawing_revisions.id"), index=True)
    page_ref: Mapped[str] = mapped_column(String(80), default="")
    body: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="Minor")
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    response: Mapped[str] = mapped_column(Text, default="")
    closure_evidence: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="Open")
    comment_number: Mapped[int] = mapped_column(Integer, default=1)
    stage: Mapped[str] = mapped_column(String(20), default="Internal")
    closed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Transmittal(Base):
    __tablename__ = "transmittals"
    __table_args__ = (UniqueConstraint("project_id", "number_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[str] = mapped_column(String(80))
    number_key: Mapped[str] = mapped_column(String(80))
    purpose: Mapped[str] = mapped_column(String(200))
    issue_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="Draft")
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    sender_company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    recipient_company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    expected_response: Mapped[date | None] = mapped_column(Date, nullable=True)
    method: Mapped[str] = mapped_column(String(40), default="")
    external_reference: Mapped[str] = mapped_column(String(120), default="")
    version: Mapped[int] = mapped_column(Integer, default=1)


class TransmittalItem(Base):
    __tablename__ = "transmittal_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    transmittal_id: Mapped[int] = mapped_column(ForeignKey("transmittals.id"), index=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey("drawing_revisions.id"))


class TransmittalRecipient(Base):
    __tablename__ = "transmittal_recipients"
    __table_args__ = (UniqueConstraint("transmittal_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    transmittal_id: Mapped[int] = mapped_column(ForeignKey("transmittals.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RevisionEvent(Base):
    __tablename__ = "revision_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    drawing_id: Mapped[int] = mapped_column(ForeignKey("drawings.id"), index=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey("drawing_revisions.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DrawingCategory(Base):
    __tablename__ = "drawing_categories"
    __table_args__ = (UniqueConstraint("discipline_id", "name_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    name_key: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class DrawingLink(Base):
    __tablename__ = "drawing_links"
    __table_args__ = (UniqueConstraint("drawing_id", "related_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    drawing_id: Mapped[int] = mapped_column(ForeignKey("drawings.id"), index=True)
    related_id: Mapped[int] = mapped_column(ForeignKey("drawings.id"))


class EngineeringSetting(Base):
    __tablename__ = "engineering_settings"
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    allow_release_with_comments: Mapped[bool] = mapped_column(Boolean, default=False)


class WrenchSetting(Base):
    __tablename__ = "wrench_settings"
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    specification: Mapped[str] = mapped_column(Text, default="")
    credential_label: Mapped[str] = mapped_column(String(200), default="")


class WrenchLink(Base):
    __tablename__ = "wrench_links"
    __table_args__ = (UniqueConstraint("drawing_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    drawing_id: Mapped[int] = mapped_column(ForeignKey("drawings.id"), index=True)
    external_document_id: Mapped[str] = mapped_column(String(120), default="")
    external_revision_id: Mapped[str] = mapped_column(String(120), default="")
    provenance: Mapped[str] = mapped_column(String(20), default="manual")
    conflict_status: Mapped[str] = mapped_column(String(20), default="none")
    detail: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class MaterialTakeoff(Base):
    """A material take-off (MTO) for one exact drawing revision.

    dedupe_key stops a repeated extraction or import of the same source from creating a second MTO.
    """

    __tablename__ = "material_takeoffs"
    __table_args__ = (UniqueConstraint("revision_id", "dedupe_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    drawing_id: Mapped[int] = mapped_column(ForeignKey("drawings.id"), index=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey("drawing_revisions.id"), index=True)
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id"), index=True)
    number: Mapped[str] = mapped_column(String(80))
    source: Mapped[str] = mapped_column(String(20))
    pages: Mapped[str] = mapped_column(String(80), default="")
    dedupe_key: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), default="Draft")
    note: Mapped[str] = mapped_column(Text, default="")
    return_reason: Mapped[str] = mapped_column(Text, default="")
    previous_id: Mapped[int | None] = mapped_column(ForeignKey("material_takeoffs.id"), nullable=True)
    change_state: Mapped[str] = mapped_column(String(30), default="")
    change_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    submitted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class TakeoffLine(Base):
    """One material line. original keeps the extracted or imported values unchanged."""

    __tablename__ = "material_takeoff_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    takeoff_id: Mapped[int] = mapped_column(ForeignKey("material_takeoffs.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text, default="")
    specification: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    unit: Mapped[str] = mapped_column(String(20), default="")
    item_id: Mapped[int | None] = mapped_column(ForeignKey("procurement_items.id"), nullable=True)
    reference: Mapped[str] = mapped_column(String(80), default="")
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    table_ref: Mapped[str] = mapped_column(String(40), default="")
    row_ref: Mapped[str] = mapped_column(String(40), default="")
    bbox: Mapped[list | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    flags: Mapped[list] = mapped_column(JSON, default=list)
    origin: Mapped[str] = mapped_column(String(20), default="Added")
    original: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)


class TakeoffCorrection(Base):
    __tablename__ = "material_takeoff_corrections"
    id: Mapped[int] = mapped_column(primary_key=True)
    takeoff_id: Mapped[int] = mapped_column(ForeignKey("material_takeoffs.id"), index=True)
    line_id: Mapped[int | None] = mapped_column(ForeignKey("material_takeoff_lines.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(30))
    field: Mapped[str] = mapped_column(String(40), default="")
    old_value: Mapped[str] = mapped_column(Text, default="")
    new_value: Mapped[str] = mapped_column(Text, default="")
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ExtractionJob(Base):
    __tablename__ = "material_extraction_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    takeoff_id: Mapped[int] = mapped_column(ForeignKey("material_takeoffs.id"), index=True)
    provider: Mapped[str] = mapped_column(String(40), default="native-pdf")
    status: Mapped[str] = mapped_column(String(20), default="Queued")
    message: Mapped[str] = mapped_column(Text, default="")
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
