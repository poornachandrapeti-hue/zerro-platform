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


class ConstructionTemplate(Base):
    __tablename__ = "construction_templates"
    __table_args__ = (
        UniqueConstraint("project_id", "code_key", name="uq_construction_template_code"),
        CheckConstraint(
            "progress_method IN ('Quantity', 'Item completion', 'Weighted milestones')",
            name="ck_construction_template_method",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    code_key: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str] = mapped_column(String(40))
    prerequisites: Mapped[str] = mapped_column(Text, default="")
    required_evidence: Mapped[str] = mapped_column(Text, default="")
    checkpoints: Mapped[list] = mapped_column(JSON, default=list)
    progress_method: Mapped[str] = mapped_column(String(40))
    completion_conditions: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WorkPackage(Base):
    __tablename__ = "work_packages"
    __table_args__ = (
        UniqueConstraint("project_id", "code_key", name="uq_work_package_code"),
        CheckConstraint("priority IN ('Normal', 'High', 'Critical')", name="ck_work_package_priority"),
        CheckConstraint(
            "status IN ('Draft', 'Ready', 'In Progress', 'On Hold', 'Physically Complete', "
            "'Accepted', 'Handed Over', 'Cancelled')",
            name="ck_work_package_status",
        ),
        CheckConstraint(
            "release_state IN ('Not Submitted', 'In Review', 'Returned', 'Rejected', 'Released')",
            name="ck_work_package_release_state",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    code_key: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(200))
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id"), index=True)
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id"))
    scope_description: Mapped[str] = mapped_column(Text)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    responsible_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    supervisor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="Normal")
    planning_reference: Mapped[str] = mapped_column(String(120), default="")
    planned_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_finish: Mapped[date | None] = mapped_column(Date, nullable=True)
    remarks: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="Draft")
    release_state: Mapped[str] = mapped_column(String(30), default="Not Submitted")
    cancellation_reason: Mapped[str] = mapped_column(Text, default="")
    impact_state: Mapped[str] = mapped_column(String(30), default="")
    impact_detail: Mapped[str] = mapped_column(Text, default="")
    impact_revision_id: Mapped[int | None] = mapped_column(ForeignKey("drawing_revisions.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReadinessCheck(Base):
    __tablename__ = "construction_readiness"
    __table_args__ = (
        UniqueConstraint("package_id", "check_type", name="uq_construction_readiness_type"),
        CheckConstraint(
            "check_type IN ('Drawing', 'Material', 'Material issue', 'Predecessor', 'Workfront', 'Manpower', "
            "'Procedure', 'Inspection', 'Permit', 'Quality hold')",
            name="ck_construction_readiness_type",
        ),
        CheckConstraint(
            "classification IN ('Mandatory', 'Advisory')",
            name="ck_construction_readiness_class",
        ),
        CheckConstraint(
            "status IN ('Not Checked', 'Pending', 'Satisfied', 'Blocked', 'Not Applicable')",
            name="ck_construction_readiness_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("work_packages.id"), index=True)
    check_type: Mapped[str] = mapped_column(String(40))
    classification: Mapped[str] = mapped_column(String(20))
    source_label: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[str] = mapped_column(Text, default="")
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    required_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="Not Checked")
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReleaseSnapshot(Base):
    __tablename__ = "construction_release_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("work_packages.id"), index=True)
    review_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WorkPackageDrawing(Base):
    __tablename__ = "work_package_drawings"
    __table_args__ = (UniqueConstraint("package_id", "revision_id", name="uq_work_package_revision"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("work_packages.id"), index=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey("drawing_revisions.id"))


class WorkPackageRequirement(Base):
    __tablename__ = "work_package_requirements"
    __table_args__ = (
        UniqueConstraint("package_id", "requirement_id", name="uq_work_package_requirement"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("work_packages.id"), index=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("material_requirements.id"))


class ConstructionActivity(Base):
    __tablename__ = "construction_activities"
    __table_args__ = (
        UniqueConstraint("project_id", "code_key", name="uq_construction_activity_code"),
        CheckConstraint(
            "measurement_method IN ('Quantity', 'Item completion', 'Weighted milestones')",
            name="ck_construction_activity_method",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("work_packages.id"), index=True)
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("construction_templates.id"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(40))
    code_key: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    baseline_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit: Mapped[str] = mapped_column(String(40))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    responsible_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    drawing_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("drawing_revisions.id"), nullable=True
    )
    measurement_method: Mapped[str] = mapped_column(String(40))
    progress_weight: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    target_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_finish: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ConstructionPredecessor(Base):
    __tablename__ = "construction_predecessors"
    __table_args__ = (
        UniqueConstraint("activity_id", "predecessor_id", name="uq_construction_predecessor"),
        CheckConstraint("activity_id <> predecessor_id", name="ck_construction_predecessor_self"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("construction_activities.id"), index=True)
    predecessor_id: Mapped[int] = mapped_column(ForeignKey("construction_activities.id"))


class ConstructionScopeChange(Base):
    __tablename__ = "construction_scope_changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("construction_activities.id"), index=True)
    previous_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    new_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    reason: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ConstructionItem(Base):
    __tablename__ = "construction_items"
    __table_args__ = (
        UniqueConstraint("project_id", "identifier_key", name="uq_construction_item_identifier"),
        CheckConstraint(
            "item_kind IN ('Pile', 'Foundation', 'Equipment', 'Cable', 'Instrument', 'Spool', 'Joint', 'Other')",
            name="ck_construction_item_kind",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("construction_activities.id"), index=True)
    identifier: Mapped[str] = mapped_column(String(80))
    identifier_key: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    item_kind: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    drawing_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("drawing_revisions.id"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ActivityMilestone(Base):
    __tablename__ = "activity_milestones"
    __table_args__ = (
        UniqueConstraint("activity_id", "name_key", name="uq_activity_milestone_name"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("construction_activities.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    name_key: Mapped[str] = mapped_column(String(120))
    weight: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    position: Mapped[int] = mapped_column(Integer, default=1)


class ProgressReport(Base):
    __tablename__ = "progress_reports"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_progress_report_number"),
        CheckConstraint("shift IN ('Day', 'Night', 'General')", name="ck_progress_report_shift"),
        CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Cancelled')",
            name="ck_progress_report_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    report_date: Mapped[date] = mapped_column(Date)
    shift: Mapped[str] = mapped_column(String(20))
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id"))
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    site_engineer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    weather: Mapped[str] = mapped_column(String(120), default="")
    remarks: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="Draft")
    cancellation_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProgressLine(Base):
    __tablename__ = "progress_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("progress_reports.id"), index=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("construction_activities.id"), index=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("construction_items.id"), nullable=True)
    milestone_id: Mapped[int | None] = mapped_column(ForeignKey("activity_milestones.id"), nullable=True)
    reverses_line_id: Mapped[int | None] = mapped_column(ForeignKey("progress_lines.id"), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    unit: Mapped[str] = mapped_column(String(40), default="")
    drawing_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("drawing_revisions.id"), nullable=True
    )
    crew_reference: Mapped[str] = mapped_column(String(200), default="")
    equipment_hours: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    material_reference: Mapped[str] = mapped_column(String(200), default="")
    stock_posting_id: Mapped[int | None] = mapped_column(
        ForeignKey("stock_postings.id"), nullable=True, index=True
    )
    delay_reason: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[str] = mapped_column(Text, default="")
    rework: Mapped[bool] = mapped_column(Boolean, default=False)
    source_note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProgressLabour(Base):
    """Activity hours of one HR person on a daily line. These are not attendance."""

    __tablename__ = "progress_labour"
    __table_args__ = (
        UniqueConstraint("line_id", "personnel_id", name="uq_progress_labour_person"),
        CheckConstraint("productive_minutes >= 0 AND idle_minutes >= 0", name="ck_progress_labour_minutes"),
        CheckConstraint("productive_minutes + idle_minutes > 0", name="ck_progress_labour_total"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("progress_reports.id"), index=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("progress_lines.id"), index=True)
    personnel_id: Mapped[int] = mapped_column(ForeignKey("hr_personnel.id"), index=True)
    productive_minutes: Mapped[int] = mapped_column(Integer, default=0)
    idle_minutes: Mapped[int] = mapped_column(Integer, default=0)
    idle_reason: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WorkHold(Base):
    __tablename__ = "construction_holds"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Open', 'In Review', 'Returned', 'Rejected', 'Closed')",
            name="ck_construction_hold_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("work_packages.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="Open")
    note: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    opened_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ConstructionBlocker(Base):
    __tablename__ = "construction_blockers"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('Delay', 'Obstruction', 'Weather', 'Idle')",
            name="ck_construction_blocker_kind",
        ),
        CheckConstraint(
            "status IN ('Open', 'Resolved')",
            name="ck_construction_blocker_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("work_packages.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recovery_note: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="Open")
    resolution_note: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CompletionDossier(Base):
    __tablename__ = "completion_dossiers"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_completion_dossier_number"),
        CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Cancelled')",
            name="ck_completion_dossier_status",
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
