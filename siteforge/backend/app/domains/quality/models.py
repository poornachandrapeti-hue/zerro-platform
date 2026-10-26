from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base


def now():
    return datetime.now(timezone.utc)


class QualityOffer(Base):
    __tablename__ = "quality_offers"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_quality_offer_number"),
        CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Cancelled')",
            name="ck_quality_offer_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("work_packages.id"), index=True)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("construction_activities.id"), nullable=True)
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="Draft")
    statement: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    cancellation_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class QualityOfferLine(Base):
    __tablename__ = "quality_offer_lines"
    __table_args__ = (UniqueConstraint("offer_id", "activity_id", name="uq_quality_offer_activity"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("quality_offers.id"), index=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("construction_activities.id"), index=True)
    offered_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    offered_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    accepted_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    accepted_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)


DOCUMENT_KINDS = (
    "Project Quality Plan",
    "ITP",
    "Inspection Procedure",
    "Test Procedure",
    "Acceptance Criteria",
    "Checklist",
    "Report Template",
)
POINT_TYPES = ("Review", "Witness", "Hold", "Surveillance")
PLAN_STATUSES = (
    "Draft",
    "Pending Review",
    "Returned for Correction",
    "Approved",
    "Rejected",
    "Superseded",
    "Cancelled",
)


class QualityDocument(Base):
    __tablename__ = "quality_documents"
    __table_args__ = (
        UniqueConstraint("project_id", "kind", "number_key", "revision_key", name="uq_quality_document_revision"),
        CheckConstraint(
            "kind IN ('Project Quality Plan', 'ITP', 'Inspection Procedure', 'Test Procedure', 'Acceptance Criteria', 'Checklist', 'Report Template')",
            name="ck_quality_document_kind",
        ),
        CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Superseded', 'Cancelled')",
            name="ck_quality_document_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    revision_label: Mapped[str] = mapped_column(String(20))
    revision_key: Mapped[str] = mapped_column(String(20))
    discipline_id: Mapped[int | None] = mapped_column(ForeignKey("disciplines.id"), nullable=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="Draft")
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    engineering_reference: Mapped[str] = mapped_column(Text, default="")
    applicable_activities: Mapped[str] = mapped_column(Text, default="")
    template_ids: Mapped[list] = mapped_column(JSON, default=list)
    statement: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    cancellation_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class QualityCheckpoint(Base):
    __tablename__ = "quality_checkpoints"
    __table_args__ = (
        UniqueConstraint("document_id", "sequence", name="uq_quality_checkpoint_sequence"),
        CheckConstraint(
            "point_type IN ('Review', 'Witness', 'Hold', 'Surveillance')",
            name="ck_quality_checkpoint_point",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("quality_documents.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    criteria_reference: Mapped[str] = mapped_column(Text, default="")
    responsible_parties: Mapped[str] = mapped_column(Text, default="")
    point_type: Mapped[str] = mapped_column(String(20))
    notice_hours: Mapped[int] = mapped_column(Integer, default=0)
    required_evidence: Mapped[str] = mapped_column(Text, default="")
    required_signatories: Mapped[str] = mapped_column(Text, default="")
    partial_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    next_release_conditions: Mapped[str] = mapped_column(Text, default="")


class QualityForm(Base):
    __tablename__ = "quality_forms"
    __table_args__ = (
        UniqueConstraint("project_id", "code_key", "revision_key", name="uq_quality_form_revision"),
        CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Superseded', 'Cancelled')",
            name="ck_quality_form_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    code_key: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    revision_label: Mapped[str] = mapped_column(String(20))
    revision_key: Mapped[str] = mapped_column(String(20))
    criteria_document_id: Mapped[int | None] = mapped_column(ForeignKey("quality_documents.id"), nullable=True)
    units: Mapped[str] = mapped_column(String(80), default="")
    prerequisites: Mapped[str] = mapped_column(Text, default="")
    required_attachments: Mapped[str] = mapped_column(Text, default="")
    items: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(40), default="Draft")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("quality_forms.id"), nullable=True)
    cancellation_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class MaterialInspection(Base):
    __tablename__ = "quality_material_inspections"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_quality_material_number"),
        CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Cancelled')",
            name="ck_quality_material_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    goods_receipt_id: Mapped[int] = mapped_column(ForeignKey("goods_receipts.id"), index=True)
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="Draft")
    inspector_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    requested_on: Mapped[date] = mapped_column(Date)
    inspected_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    certificate_reference: Mapped[str] = mapped_column(String(200), default="")
    findings: Mapped[str] = mapped_column(Text, default="")
    statement: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    cancellation_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class MaterialDisposition(Base):
    __tablename__ = "quality_material_dispositions"
    __table_args__ = (
        CheckConstraint("from_state IN ('Pending', 'Quarantined')", name="ck_quality_material_from"),
        CheckConstraint(
            "to_state IN ('Accepted', 'Rejected', 'Quarantined')",
            name="ck_quality_material_to",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(ForeignKey("quality_material_inspections.id"), index=True)
    goods_receipt_line_id: Mapped[int] = mapped_column(ForeignKey("goods_receipt_lines.id"), index=True)
    from_state: Mapped[str] = mapped_column(String(20))
    to_state: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    batch_number: Mapped[str] = mapped_column(String(80), default="")
    heat_number: Mapped[str] = mapped_column(String(80), default="")
    serial_number: Mapped[str] = mapped_column(String(80), default="")


class ConstructionRequest(Base):
    __tablename__ = "quality_construction_requests"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_quality_construction_number"),
        CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Cancelled')",
            name="ck_quality_construction_status",
        ),
        CheckConstraint(
            "outcome IN ('Pending', 'Accepted', 'Partially Accepted', 'Rejected')",
            name="ck_quality_construction_outcome",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("work_packages.id"), index=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("construction_activities.id"), index=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("quality_forms.id"), index=True)
    checkpoint_id: Mapped[int | None] = mapped_column(ForeignKey("quality_checkpoints.id"), nullable=True)
    follows_id: Mapped[int | None] = mapped_column(ForeignKey("quality_construction_requests.id"), nullable=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="Draft")
    outcome: Mapped[str] = mapped_column(String(40), default="Pending")
    location: Mapped[str] = mapped_column(String(200), default="")
    requested_on: Mapped[date] = mapped_column(Date)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    inspector_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    attendees: Mapped[str] = mapped_column(Text, default="")
    findings: Mapped[str] = mapped_column(Text, default="")
    offered_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    offered_percent: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    accepted_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    accepted_percent: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    rejected_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    statement: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    cancellation_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ConstructionResult(Base):
    __tablename__ = "quality_construction_results"
    __table_args__ = (
        UniqueConstraint("request_id", "position", name="uq_quality_construction_result"),
        CheckConstraint(
            "result IN ('', 'Pass', 'Fail', 'Not applicable')",
            name="ck_quality_construction_result",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("quality_construction_requests.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    item: Mapped[str] = mapped_column(String(300))
    result: Mapped[str] = mapped_column(String(20), default="")
    measurement: Mapped[str] = mapped_column(String(80), default="")


class Nonconformance(Base):
    __tablename__ = "quality_ncrs"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_quality_ncr_number"),
        CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', "
            "'Cancelled', 'Pending Verification', 'Verification Returned', 'Closed')",
            name="ck_quality_ncr_status",
        ),
        CheckConstraint("severity IN ('Minor', 'Major', 'Critical')", name="ck_quality_ncr_severity"),
        CheckConstraint(
            "disposition IN ('Rework', 'Repair', 'Reject/Return', 'Use-As-Is')",
            name="ck_quality_ncr_disposition",
        ),
        CheckConstraint(
            "source_kind IN ('activity', 'request', 'material', 'offer')",
            name="ck_quality_ncr_source",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    source_kind: Mapped[str] = mapped_column(String(20))
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("construction_activities.id"), nullable=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("quality_construction_requests.id"), nullable=True)
    material_id: Mapped[int | None] = mapped_column(ForeignKey("quality_material_inspections.id"), nullable=True)
    offer_id: Mapped[int | None] = mapped_column(ForeignKey("quality_offers.id"), nullable=True)
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="Draft")
    location: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    requirement: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(20))
    affected_scope: Mapped[str] = mapped_column(Text, default="")
    containment: Mapped[str] = mapped_column(Text, default="")
    raised_on: Mapped[date] = mapped_column(Date)
    target_on: Mapped[date] = mapped_column(Date)
    root_cause: Mapped[str] = mapped_column(Text, default="")
    corrective_action: Mapped[str] = mapped_column(Text, default="")
    disposition: Mapped[str] = mapped_column(String(20))
    evidence: Mapped[str] = mapped_column(Text, default="")
    verification: Mapped[str] = mapped_column(Text, default="")
    statement: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    cancellation_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Concession(Base):
    __tablename__ = "quality_concessions"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_quality_concession_number"),
        CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Cancelled')",
            name="ck_quality_concession_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    ncr_id: Mapped[int] = mapped_column(ForeignKey("quality_ncrs.id"), index=True)
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="Draft")
    proposal: Mapped[str] = mapped_column(Text, default="")
    technical_note: Mapped[str] = mapped_column(Text, default="")
    statement: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    cancellation_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class QualityHold(Base):
    __tablename__ = "quality_holds"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_quality_hold_number"),
        CheckConstraint(
            "status IN ('Active', 'Pending Release', 'Release Returned', 'Released')",
            name="ck_quality_hold_status",
        ),
        CheckConstraint("scope_kind IN ('package', 'activity', 'receipt')", name="ck_quality_hold_scope"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    scope_kind: Mapped[str] = mapped_column(String(20))
    package_id: Mapped[int | None] = mapped_column(ForeignKey("work_packages.id"), nullable=True)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("construction_activities.id"), nullable=True)
    receipt_line_id: Mapped[int | None] = mapped_column(ForeignKey("goods_receipt_lines.id"), nullable=True)
    checkpoint_id: Mapped[int | None] = mapped_column(ForeignKey("quality_checkpoints.id"), nullable=True)
    ncr_id: Mapped[int | None] = mapped_column(ForeignKey("quality_ncrs.id"), nullable=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="Active")
    reason: Mapped[str] = mapped_column(Text, default="")
    conditions: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[str] = mapped_column(Text, default="")
    blocks_issue: Mapped[bool] = mapped_column(Boolean, default=False)
    blocks_work: Mapped[bool] = mapped_column(Boolean, default=False)
    blocks_handover: Mapped[bool] = mapped_column(Boolean, default=False)
    statement: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    released_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    released_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Qualification(Base):
    __tablename__ = "quality_qualifications"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_quality_qualification_number"),
        CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Cancelled', 'Withdrawn')",
            name="ck_quality_qualification_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="Draft")
    qualification_type: Mapped[str] = mapped_column(String(120))
    applicable_activities: Mapped[str] = mapped_column(Text, default="")
    issuer: Mapped[str] = mapped_column(String(200), default="")
    certificate_number: Mapped[str] = mapped_column(String(80), default="")
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date] = mapped_column(Date)
    evidence: Mapped[str] = mapped_column(Text, default="")
    statement: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    withdrawal_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Calibration(Base):
    __tablename__ = "quality_calibrations"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_quality_calibration_number"),
        CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Cancelled', 'Withdrawn')",
            name="ck_quality_calibration_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="Draft")
    equipment_code: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(200), default="")
    serial_number: Mapped[str] = mapped_column(String(80), default="")
    certificate_reference: Mapped[str] = mapped_column(String(200), default="")
    calibrated_on: Mapped[date] = mapped_column(Date)
    due_on: Mapped[date] = mapped_column(Date)
    use_range: Mapped[str] = mapped_column(String(200), default="")
    evidence: Mapped[str] = mapped_column(Text, default="")
    statement: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    withdrawal_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class QualityPunch(Base):
    __tablename__ = "quality_punches"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_quality_punch_number"),
        CheckConstraint("issue_type IN ('Observation', 'Punch')", name="ck_quality_punch_type"),
        CheckConstraint("severity IN ('Minor', 'Major', 'Critical')", name="ck_quality_punch_severity"),
        CheckConstraint(
            "status IN ('Open', 'Pending Closure', 'Closure Returned', 'Closed', 'Cancelled')",
            name="ck_quality_punch_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("work_packages.id"), index=True)
    blocker_id: Mapped[int | None] = mapped_column(ForeignKey("construction_blockers.id"), nullable=True)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("construction_activities.id"), nullable=True)
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    issue_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(40), default="Open")
    description: Mapped[str] = mapped_column(Text, default="")
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    severity: Mapped[str] = mapped_column(String(20))
    blocking: Mapped[bool] = mapped_column(Boolean, default=False)
    due_on: Mapped[date] = mapped_column(Date)
    evidence: Mapped[str] = mapped_column(Text, default="")
    verification: Mapped[str] = mapped_column(Text, default="")
    statement: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class QualityDossier(Base):
    __tablename__ = "quality_dossiers"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_quality_dossier_number"),
        CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Cancelled')",
            name="ck_quality_dossier_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("work_packages.id"), index=True)
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="Draft")
    statement: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    cancellation_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
