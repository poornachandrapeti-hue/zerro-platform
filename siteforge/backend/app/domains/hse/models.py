from datetime import date, datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base


def now():
    return datetime.now(timezone.utc)


DOCUMENT_KINDS = (
    "HSE Plan",
    "Emergency Response Plan",
    "Safe Work Procedure",
    "Risk Assessment Template",
    "Permit Template",
    "Inspection Checklist",
    "Environmental Control Plan",
)
DOCUMENT_STATUSES = (
    "Draft",
    "Pending Review",
    "Returned for Correction",
    "Approved",
    "Rejected",
    "Superseded",
    "Withdrawn",
)
ASSESSMENT_STATUSES = DOCUMENT_STATUSES


class HseDocument(Base):
    __tablename__ = "hse_documents"
    __table_args__ = (
        UniqueConstraint("project_id", "kind", "number_key", "revision_key", name="uq_hse_document_revision"),
        CheckConstraint(
            "kind IN ('HSE Plan', 'Emergency Response Plan', 'Safe Work Procedure', 'Risk Assessment Template', 'Permit Template', 'Inspection Checklist', 'Environmental Control Plan')",
            name="ck_hse_document_kind",
        ),
        CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Superseded', 'Withdrawn')",
            name="ck_hse_document_status",
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
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(40), default="Draft")
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    applicability: Mapped[str] = mapped_column(Text, default="")
    engineering_reference: Mapped[str] = mapped_column(Text, default="")
    statement: Mapped[str] = mapped_column(Text, default="")
    withdrawal_reason: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseAssessment(Base):
    __tablename__ = "hse_assessments"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_hse_assessment_number"),
        CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Superseded', 'Withdrawn')",
            name="ck_hse_assessment_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    discipline_id: Mapped[int | None] = mapped_column(ForeignKey("disciplines.id"), nullable=True)
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("work_packages.id"), nullable=True)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("construction_activities.id"), nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("hse_documents.id"), nullable=True)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("hse_assessments.id"), nullable=True)
    task_description: Mapped[str] = mapped_column(Text)
    steps: Mapped[str] = mapped_column(Text, default="")
    hazards: Mapped[str] = mapped_column(Text, default="")
    exposed: Mapped[str] = mapped_column(Text, default="")
    existing_controls: Mapped[str] = mapped_column(Text, default="")
    initial_rating: Mapped[str] = mapped_column(String(80), default="")
    additional_controls: Mapped[str] = mapped_column(Text, default="")
    residual_rating: Mapped[str] = mapped_column(String(80), default="")
    control_owners: Mapped[str] = mapped_column(Text, default="")
    required_permits: Mapped[str] = mapped_column(Text, default="")
    required_competencies: Mapped[str] = mapped_column(Text, default="")
    prepared_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    review_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="Draft")
    statement: Mapped[str] = mapped_column(Text, default="")
    withdrawal_reason: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


PERMIT_STATUSES = (
    "Draft",
    "Pending Review",
    "Returned for Correction",
    "Authorized",
    "Active",
    "Suspended",
    "Expired",
    "Closed",
    "Cancelled",
    "Rejected",
)
ISOLATION_KINDS = (
    "Isolation Certificate",
    "Lockout/Tagout",
    "Gas Test",
    "Lifting Plan",
    "Equipment Check",
    "Rescue Arrangement",
    "Access Control",
)
EVENT_KINDS = ("Extension", "Revalidation", "Suspension", "Activation", "Handover", "Condition change", "Closure", "Cancellation")
SUGGESTED_PERMIT_TYPES = (
    "Hot Work",
    "Confined Space",
    "Work at Height",
    "Excavation",
    "Electrical Work",
    "Lifting",
    "Isolation/Lockout-Tagout",
)


class HsePermitType(Base):
    __tablename__ = "hse_permit_types"
    __table_args__ = (UniqueConstraint("project_id", "name_key", name="uq_hse_permit_type_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    name_key: Mapped[str] = mapped_column(String(80))
    physical_required: Mapped[bool] = mapped_column(Boolean, default=False)
    handover_required: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HsePermit(Base):
    __tablename__ = "hse_permits"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_hse_permit_number"),
        CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Authorized', 'Active', 'Suspended', 'Expired', 'Closed', 'Cancelled', 'Rejected')",
            name="ck_hse_permit_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("hse_permit_types.id"))
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    discipline_id: Mapped[int | None] = mapped_column(ForeignKey("disciplines.id"), nullable=True)
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("work_packages.id"), nullable=True, index=True)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("construction_activities.id"), nullable=True)
    assessment_id: Mapped[int | None] = mapped_column(ForeignKey("hse_assessments.id"), nullable=True)
    task_description: Mapped[str] = mapped_column(Text)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    performing_authority_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    area_owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    issuer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    crew_note: Mapped[str] = mapped_column(Text, default="")
    equipment_note: Mapped[str] = mapped_column(Text, default="")
    conditions: Mapped[str] = mapped_column(Text, default="")
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40), default="Draft")
    external_reference: Mapped[str] = mapped_column(String(80), default="")
    external_evidence: Mapped[str] = mapped_column(Text, default="")
    work_status: Mapped[str] = mapped_column(Text, default="")
    site_condition: Mapped[str] = mapped_column(Text, default="")
    statement: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HsePermitCheck(Base):
    __tablename__ = "hse_permit_checks"
    id: Mapped[int] = mapped_column(primary_key=True)
    permit_id: Mapped[int] = mapped_column(ForeignKey("hse_permits.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    evidence: Mapped[str] = mapped_column(Text, default="")
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class HsePermitEvent(Base):
    __tablename__ = "hse_permit_events"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('Extension', 'Revalidation', 'Suspension', 'Activation', 'Handover', 'Condition change', 'Closure', 'Cancellation')",
            name="ck_hse_permit_event_kind",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    permit_id: Mapped[int] = mapped_column(ForeignKey("hse_permits.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    note: Mapped[str] = mapped_column(Text, default="")
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseIsolation(Base):
    __tablename__ = "hse_isolations"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_hse_isolation_number"),
        CheckConstraint(
            "kind IN ('Isolation Certificate', 'Lockout/Tagout', 'Gas Test', 'Lifting Plan', 'Equipment Check', 'Rescue Arrangement', 'Access Control')",
            name="ck_hse_isolation_kind",
        ),
        CheckConstraint("status IN ('Draft', 'Approved', 'In Force', 'Removed')", name="ck_hse_isolation_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    authority_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="Draft")
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence: Mapped[str] = mapped_column(Text, default="")
    removal_reason: Mapped[str] = mapped_column(Text, default="")
    allow_removal_with_active_permit: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    removed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HsePermitIsolation(Base):
    __tablename__ = "hse_permit_isolations"
    __table_args__ = (UniqueConstraint("permit_id", "isolation_id", name="uq_hse_permit_isolation"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    permit_id: Mapped[int] = mapped_column(ForeignKey("hse_permits.id"), index=True)
    isolation_id: Mapped[int] = mapped_column(ForeignKey("hse_isolations.id"), index=True)


class HseConflictRule(Base):
    __tablename__ = "hse_conflict_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    type_a_id: Mapped[int] = mapped_column(ForeignKey("hse_permit_types.id"))
    type_b_id: Mapped[int] = mapped_column(ForeignKey("hse_permit_types.id"))
    same_area: Mapped[bool] = mapped_column(Boolean, default=True)
    require_decision: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(Text, default="")


class HseCoordination(Base):
    __tablename__ = "hse_coordinations"
    __table_args__ = (UniqueConstraint("permit_id", "other_permit_id", "rule_id", name="uq_hse_coordination"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    permit_id: Mapped[int] = mapped_column(ForeignKey("hse_permits.id"), index=True)
    other_permit_id: Mapped[int] = mapped_column(ForeignKey("hse_permits.id"))
    rule_id: Mapped[int] = mapped_column(ForeignKey("hse_conflict_rules.id"))
    decision: Mapped[str] = mapped_column(Text, default="")
    controls: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="Open")
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


SUGGESTED_ELIGIBILITY = (
    "Site Induction",
    "Task-Specific Training",
    "Required Certification",
    "Authorized Work Category",
)
ELIGIBILITY_STATUSES = ("Recorded", "Verified", "Expired", "Withdrawn")
INSPECTION_TYPES = ("Routine", "Workfront", "Equipment", "Environmental", "Other")
OBSERVATION_TYPES = (
    "Unsafe Condition",
    "Unsafe Act",
    "Positive Observation",
    "Environmental Concern",
    "Other",
)


class HseEligibilityRule(Base):
    __tablename__ = "hse_eligibility_rules"
    __table_args__ = (UniqueConstraint("project_id", "category_key", "scope_key", name="uq_hse_eligibility_rule"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    category: Mapped[str] = mapped_column(String(80))
    category_key: Mapped[str] = mapped_column(String(80))
    package_id: Mapped[int | None] = mapped_column(ForeignKey("work_packages.id"), nullable=True)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("construction_activities.id"), nullable=True)
    scope_key: Mapped[str] = mapped_column(String(40))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseEligibility(Base):
    __tablename__ = "hse_eligibility"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Recorded', 'Verified', 'Expired', 'Withdrawn')",
            name="ck_hse_eligibility_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(80))
    category_key: Mapped[str] = mapped_column(String(80))
    evidence: Mapped[str] = mapped_column(Text)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="Recorded")
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawal_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseToolboxRule(Base):
    __tablename__ = "hse_toolbox_rules"
    __table_args__ = (UniqueConstraint("project_id", "scope_key", name="uq_hse_toolbox_rule"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("work_packages.id"), nullable=True)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("construction_activities.id"), nullable=True)
    scope_key: Mapped[str] = mapped_column(String(40))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseToolboxTalk(Base):
    __tablename__ = "hse_toolbox_talks"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_hse_toolbox_number"),
        CheckConstraint("status IN ('Draft', 'Held')", name="ck_hse_toolbox_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    talk_on: Mapped[date] = mapped_column(Date)
    shift: Mapped[str] = mapped_column(String(40), default="")
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("work_packages.id"), nullable=True)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("construction_activities.id"), nullable=True)
    topic: Mapped[str] = mapped_column(Text)
    assessment_id: Mapped[int | None] = mapped_column(ForeignKey("hse_assessments.id"), nullable=True)
    permit_id: Mapped[int | None] = mapped_column(ForeignKey("hse_permits.id"), nullable=True)
    presenter_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    issues: Mapped[str] = mapped_column(Text, default="")
    follow_up: Mapped[str] = mapped_column(Text, default="")
    attachment_reference: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="Draft")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseToolboxAck(Base):
    __tablename__ = "hse_toolbox_acks"
    __table_args__ = (UniqueConstraint("talk_id", "member_id", name="uq_hse_toolbox_ack"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    talk_id: Mapped[int] = mapped_column(ForeignKey("hse_toolbox_talks.id"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    evidence: Mapped[str] = mapped_column(Text, default="")
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseFindingRule(Base):
    __tablename__ = "hse_finding_rules"
    __table_args__ = (UniqueConstraint("project_id", "severity_key", name="uq_hse_finding_rule"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    severity: Mapped[str] = mapped_column(String(80))
    severity_key: Mapped[str] = mapped_column(String(80))
    blocks_work: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseInspection(Base):
    __tablename__ = "hse_inspections"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_hse_inspection_number"),
        CheckConstraint(
            "inspection_type IN ('Routine', 'Workfront', 'Equipment', 'Environmental', 'Other')",
            name="ck_hse_inspection_type",
        ),
        CheckConstraint("status IN ('Draft', 'Recorded')", name="ck_hse_inspection_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    inspection_type: Mapped[str] = mapped_column(String(20))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    discipline_id: Mapped[int | None] = mapped_column(ForeignKey("disciplines.id"), nullable=True)
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("work_packages.id"), nullable=True)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("construction_activities.id"), nullable=True)
    inspector_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    inspected_on: Mapped[date] = mapped_column(Date)
    checklist_document_id: Mapped[int | None] = mapped_column(ForeignKey("hse_documents.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="Recorded")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseFinding(Base):
    __tablename__ = "hse_findings"
    __table_args__ = (CheckConstraint("status IN ('Open', 'Closed')", name="ck_hse_finding_status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(ForeignKey("hse_inspections.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(80))
    severity_key: Mapped[str] = mapped_column(String(80))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    target_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    action: Mapped[str] = mapped_column(Text, default="")
    photo_reference: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="Open")
    close_evidence: Mapped[str] = mapped_column(Text, default="")
    closed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseObservation(Base):
    __tablename__ = "hse_observations"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_hse_observation_number"),
        CheckConstraint(
            "observation_type IN ('Unsafe Condition', 'Unsafe Act', 'Positive Observation', 'Environmental Concern', 'Other')",
            name="ck_hse_observation_type",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    observation_type: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("work_packages.id"), nullable=True)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("construction_activities.id"), nullable=True)
    evidence: Mapped[str] = mapped_column(Text, default="")
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="Reported")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


SUGGESTED_INCIDENT_CATEGORIES = (
    "Near Miss",
    "Injury/Illness Event",
    "Property Damage",
    "Environmental Event",
    "Fire",
)
INCIDENT_STATUSES = (
    "Reported",
    "Under Investigation",
    "Pending Closure",
    "Returned for Correction",
    "Closed",
    "Cancelled",
    "Rejected",
)
ACTION_STATUSES = ("Open", "In Progress", "Pending Verification", "Closed", "Cancelled")
ACTION_SOURCES = ("", "hse.incident", "hse.observation", "hse.inspection", "hse.talk")


class HseIncidentCategory(Base):
    __tablename__ = "hse_incident_categories"
    __table_args__ = (UniqueConstraint("project_id", "name_key", name="uq_hse_incident_category"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    name_key: Mapped[str] = mapped_column(String(80))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseIncidentRule(Base):
    __tablename__ = "hse_incident_rules"
    __table_args__ = (UniqueConstraint("project_id", "severity_key", name="uq_hse_incident_rule"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    severity: Mapped[str] = mapped_column(String(80))
    severity_key: Mapped[str] = mapped_column(String(80))
    requires_investigation: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseIncident(Base):
    __tablename__ = "hse_incidents"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_hse_incident_number"),
        CheckConstraint(
            "status IN ('Reported', 'Under Investigation', 'Pending Closure', 'Returned for Correction', 'Closed', 'Cancelled', 'Rejected')",
            name="ck_hse_incident_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("hse_incident_categories.id"))
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    timezone_name: Mapped[str] = mapped_column(String(64))
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    location: Mapped[str] = mapped_column(Text, default="")
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    package_id: Mapped[int | None] = mapped_column(ForeignKey("work_packages.id"), nullable=True)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("construction_activities.id"), nullable=True)
    involved: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text)
    immediate_actions: Mapped[str] = mapped_column(Text, default="")
    emergency_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    initial_severity: Mapped[str] = mapped_column(String(80), default="")
    evidence: Mapped[str] = mapped_column(Text, default="")
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    verified_classification: Mapped[str] = mapped_column(String(80), default="")
    contributing_factors: Mapped[str] = mapped_column(Text, default="")
    root_causes: Mapped[str] = mapped_column(Text, default="")
    lessons: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="Reported")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseIncidentMember(Base):
    __tablename__ = "hse_incident_members"
    __table_args__ = (UniqueConstraint("incident_id", "user_id", name="uq_hse_incident_member"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("hse_incidents.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class HseActionRule(Base):
    __tablename__ = "hse_action_rules"
    __table_args__ = (UniqueConstraint("project_id", name="uq_hse_action_rule"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    effectiveness_required: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseAction(Base):
    __tablename__ = "hse_actions"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_hse_action_number"),
        CheckConstraint(
            "status IN ('Open', 'In Progress', 'Pending Verification', 'Closed', 'Cancelled')",
            name="ck_hse_action_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    source_type: Mapped[str] = mapped_column(String(40), default="")
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(80), default="")
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    verifier_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    interim_controls: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[str] = mapped_column(Text, default="")
    effectiveness: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="Open")
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


HOLD_SCOPES = ("package", "activity", "area", "equipment", "work")
HOLD_STATUSES = ("Reported", "Active", "Release Requested", "Returned", "Released", "Rejected")


class HseHoldIssuer(Base):
    __tablename__ = "hse_hold_issuers"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_hse_hold_issuer"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseHoldRule(Base):
    __tablename__ = "hse_hold_rules"
    __table_args__ = (UniqueConstraint("project_id", name="uq_hse_hold_rule"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    separate_release: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseHold(Base):
    __tablename__ = "hse_holds"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_hse_hold_number"),
        CheckConstraint(
            "status IN ('Reported', 'Active', 'Release Requested', 'Returned', 'Released', 'Rejected')",
            name="ck_hse_hold_status",
        ),
        CheckConstraint(
            "scope_kind IN ('package', 'activity', 'area', 'equipment', 'work', '')",
            name="ck_hse_hold_scope",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(20), default="Hold")
    reason: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(80), default="")
    severity: Mapped[str] = mapped_column(String(80), default="")
    scope_kind: Mapped[str] = mapped_column(String(20), default="")
    package_id: Mapped[int | None] = mapped_column(ForeignKey("work_packages.id"), nullable=True)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("construction_activities.id"), nullable=True)
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    equipment_note: Mapped[str] = mapped_column(Text, default="")
    affected_work: Mapped[str] = mapped_column(Text, default="")
    restricted_actions: Mapped[str] = mapped_column(Text, default="")
    immediate_controls: Mapped[str] = mapped_column(Text, default="")
    release_conditions: Mapped[str] = mapped_column(Text, default="")
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    issued_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="Reported")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseHoldEvent(Base):
    __tablename__ = "hse_hold_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    hold_id: Mapped[int] = mapped_column(ForeignKey("hse_holds.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    note: Mapped[str] = mapped_column(Text, default="")
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseEmergencyRule(Base):
    __tablename__ = "hse_emergency_rules"
    __table_args__ = (UniqueConstraint("project_id", name="uq_hse_emergency_rule"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    procedure: Mapped[str] = mapped_column(Text, default="")
    review_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseEmergencyContact(Base):
    __tablename__ = "hse_emergency_contacts"
    __table_args__ = (
        UniqueConstraint("project_id", "contact_id", name="uq_hse_emergency_contact"),
        CheckConstraint("status IN ('Recorded', 'Verified')", name="ck_hse_emergency_contact_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("project_contacts.id"))
    response_role: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="Recorded")
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseMusterPoint(Base):
    __tablename__ = "hse_muster_points"
    __table_args__ = (UniqueConstraint("project_id", "name_key", name="uq_hse_muster_point"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    name_key: Mapped[str] = mapped_column(String(80))
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseEmergencyGear(Base):
    __tablename__ = "hse_emergency_gear"
    __table_args__ = (UniqueConstraint("project_id", "name_key", name="uq_hse_emergency_gear"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    name_key: Mapped[str] = mapped_column(String(80))
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    location: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseEmergencyPlan(Base):
    __tablename__ = "hse_emergency_plans"
    __table_args__ = (UniqueConstraint("project_id", "number_key", name="uq_hse_emergency_plan"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    engineering_reference: Mapped[str] = mapped_column(Text, default="")
    document_id: Mapped[int | None] = mapped_column(ForeignKey("hse_documents.id"), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseDrill(Base):
    __tablename__ = "hse_drills"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_hse_drill_number"),
        CheckConstraint("status IN ('Planned', 'Held', 'Cancelled')", name="ck_hse_drill_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    planned_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="Planned")
    findings: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseDrillAck(Base):
    __tablename__ = "hse_drill_acks"
    __table_args__ = (UniqueConstraint("drill_id", "member_id", name="uq_hse_drill_ack"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    drill_id: Mapped[int] = mapped_column(ForeignKey("hse_drills.id"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    evidence: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


ENVIRONMENT_KINDS = ("Waste inspection", "Spill", "Dust/noise", "Discharge check", "Monitoring evidence")
ENVIRONMENT_RESULTS = ("Not assessed", "Within criteria", "Outside criteria")


class HseEnvironmentCriterion(Base):
    __tablename__ = "hse_environment_criteria"
    __table_args__ = (UniqueConstraint("project_id", "name_key", name="uq_hse_environment_criterion"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    name_key: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(40), default="")
    threshold: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HseEnvironmentRecord(Base):
    __tablename__ = "hse_environment_records"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_hse_environment_number"),
        CheckConstraint(
            "kind IN ('Waste inspection', 'Spill', 'Dust/noise', 'Discharge check', 'Monitoring evidence')",
            name="ck_hse_environment_kind",
        ),
        CheckConstraint(
            "result IN ('Not assessed', 'Within criteria', 'Outside criteria')",
            name="ck_hse_environment_result",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    recorded_on: Mapped[date] = mapped_column(Date)
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("work_packages.id"), nullable=True)
    criterion_id: Mapped[int | None] = mapped_column(ForeignKey("hse_environment_criteria.id"), nullable=True)
    reading: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[str] = mapped_column(String(40), default="Not assessed")
    evidence: Mapped[str] = mapped_column(Text, default="")
    action_id: Mapped[int | None] = mapped_column(ForeignKey("hse_actions.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
