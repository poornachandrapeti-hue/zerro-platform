from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
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

from app.db import Base


def now():
    return datetime.now(timezone.utc)


class ProcurementItem(Base):
    __tablename__ = "procurement_items"
    __table_args__ = (UniqueConstraint("organization_id", "code_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    code_key: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(300))
    item_type: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(120))
    subcategory: Mapped[str] = mapped_column(String(120), default="")
    discipline_ids: Mapped[list] = mapped_column(JSON, default=list)
    specification: Mapped[str] = mapped_column(Text, default="")
    approval_status: Mapped[str] = mapped_column(String(24), default="Draft")
    submitted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    specification_attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    size_rating: Mapped[str] = mapped_column(String(120), default="")
    material_grade: Mapped[str] = mapped_column(String(120), default="")
    applicable_standard: Mapped[str] = mapped_column(String(200), default="")
    base_unit: Mapped[str] = mapped_column(String(20))
    purchase_unit: Mapped[str] = mapped_column(String(20), default="")
    issue_unit: Mapped[str] = mapped_column(String(20), default="")
    approved_make: Mapped[str] = mapped_column(String(200), default="")
    model_number: Mapped[str] = mapped_column(String(120), default="")
    manufacturer_part_number: Mapped[str] = mapped_column(String(120), default="")
    hsn_code: Mapped[str] = mapped_column(String(20), default="")
    inspection_required: Mapped[bool] = mapped_column(Boolean, default=False)
    tracking_required: Mapped[bool] = mapped_column(Boolean, default=False)
    mtc_required: Mapped[bool] = mapped_column(Boolean, default=False)
    calibration_certificate_required: Mapped[bool] = mapped_column(Boolean, default=False)
    shelf_life_applicable: Mapped[bool] = mapped_column(Boolean, default=False)
    shelf_life_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preferred_vendor_id: Mapped[int | None] = mapped_column(ForeignKey("procurement_vendors.id"), nullable=True)
    specification_template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class CatalogueItemAmendment(Base):
    """Isolated proposed technical change; approved item remains unchanged until approval."""
    __tablename__ = "procurement_item_amendments"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("procurement_items.id"), index=True)
    base_version: Mapped[int] = mapped_column(Integer)
    proposed: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="Pending Approval")
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decision_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CatalogueItemSpecificationHistory(Base):
    """Append-only snapshots of catalogue item specifications and approval transitions."""
    __tablename__ = "procurement_item_specification_history"
    __table_args__ = (UniqueConstraint("item_id", "sequence"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("procurement_items.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    item_version: Mapped[int] = mapped_column(Integer)
    event: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text, default="")
    snapshot: Mapped[dict] = mapped_column(JSON)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CatalogueItemReview(Base):
    """Immutable decisions for organization-scoped item approvals."""
    __tablename__ = "procurement_item_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("procurement_items.id"), index=True)
    action: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str] = mapped_column(Text)
    item_version: Mapped[int] = mapped_column(Integer)
    specification_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CatalogueSpecificationTemplate(Base):
    """Organization-scoped specification configuration; does not replace item identities."""
    __tablename__ = "procurement_specification_templates"
    __table_args__ = (UniqueConstraint("organization_id", "discipline", "category"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    discipline: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(120))
    fields: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    modified_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class CatalogueCategory(Base):
    """Organization category master by discipline name. Reuses global Discipline names."""
    __tablename__ = "procurement_catalogue_categories"
    __table_args__ = (UniqueConstraint("organization_id", "discipline", "name_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    discipline: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(120))
    name_key: Mapped[str] = mapped_column(String(120))
    qa_document_types: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    modified_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class CatalogueSubcategory(Base):
    __tablename__ = "procurement_catalogue_subcategories"
    __table_args__ = (UniqueConstraint("organization_id", "category_id", "name_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("procurement_catalogue_categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    name_key: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    modified_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class CatalogueUom(Base):
    """Standardized UOM codes. Conversions remain in procurement_conversions."""
    __tablename__ = "procurement_uoms"
    __table_args__ = (UniqueConstraint("organization_id", "code_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    code_key: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(80), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    modified_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class CatalogueMaterialGrade(Base):
    __tablename__ = "procurement_material_grades"
    __table_args__ = (UniqueConstraint("organization_id", "code_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    code_key: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(120), default="")
    discipline: Mapped[str] = mapped_column(String(100), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    modified_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class CatalogueStandard(Base):
    __tablename__ = "procurement_standards"
    __table_args__ = (UniqueConstraint("organization_id", "code_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    code_key: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(200), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    modified_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class CatalogueManufacturer(Base):
    __tablename__ = "procurement_manufacturers"
    __table_args__ = (UniqueConstraint("organization_id", "code_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    code_key: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    modified_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class CatalogueApprovalConfig(Base):
    """Organization catalogue approval workflow settings. Does not replace RBAC permissions."""
    __tablename__ = "procurement_catalogue_approval_config"
    __table_args__ = (UniqueConstraint("organization_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    stages: Mapped[list] = mapped_column(JSON, default=list)
    submitted_status: Mapped[str] = mapped_column(String(40), default="Under Review")
    approve_permission: Mapped[str] = mapped_column(String(120), default="procurement.catalogue.approve")
    require_decision_reason: Mapped[bool] = mapped_column(Boolean, default=True)
    decision_reason_min_length: Mapped[int] = mapped_column(Integer, default=3)
    enforce_separation_of_duties: Mapped[bool] = mapped_column(Boolean, default=True)
    reviewer_stages: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    modified_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class UnitConversion(Base):
    __tablename__ = "procurement_conversions"
    __table_args__ = (UniqueConstraint("organization_id", "from_unit", "to_unit"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    from_unit: Mapped[str] = mapped_column(String(20))
    to_unit: Mapped[str] = mapped_column(String(20))
    factor: Mapped[Decimal] = mapped_column(Numeric(14, 6))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Vendor(Base):
    __tablename__ = "procurement_vendors"
    __table_args__ = (UniqueConstraint("organization_id", "code_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    code_key: Mapped[str] = mapped_column(String(80))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    categories: Mapped[str] = mapped_column(Text, default="")
    contact_name: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(254), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    tax_details: Mapped[str] = mapped_column(Text, default="")
    approval_status: Mapped[str] = mapped_column(String(20), default="Pending")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Warehouse(Base):
    __tablename__ = "procurement_warehouses"
    __table_args__ = (UniqueConstraint("project_id", "code_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    code_key: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(200))
    location: Mapped[str] = mapped_column(String(200), default="")
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    officer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class MaterialRequirement(Base):
    __tablename__ = "material_requirements"
    __table_args__ = (UniqueConstraint("project_id", "number_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[str] = mapped_column(String(80))
    number_key: Mapped[str] = mapped_column(String(80))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id"), index=True)
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    required_date: Mapped[date] = mapped_column(Date)
    priority: Mapped[str] = mapped_column(String(20), default="Normal")
    purpose: Mapped[str] = mapped_column(Text)
    remarks: Mapped[str] = mapped_column(Text, default="")
    drawing_id: Mapped[int | None] = mapped_column(ForeignKey("drawings.id"), nullable=True)
    drawing_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("drawing_revisions.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(40), default="Draft")
    cancellation_reason: Mapped[str] = mapped_column(Text, default="")
    impact_state: Mapped[str] = mapped_column(String(40), default="")
    impact_detail: Mapped[str] = mapped_column(Text, default="")
    impact_decision: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(20), default="Manual")
    takeoff_id: Mapped[int | None] = mapped_column(ForeignKey("material_takeoffs.id"), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class RequirementLine(Base):
    __tablename__ = "material_requirement_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("material_requirements.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    item_id: Mapped[int] = mapped_column(ForeignKey("procurement_items.id"))
    specification: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit: Mapped[str] = mapped_column(String(20))
    required_date: Mapped[date] = mapped_column(Date)
    tag: Mapped[str] = mapped_column(String(80), default="")
    engineering_reference: Mapped[str] = mapped_column(String(200), default="")
    takeoff_line_id: Mapped[int | None] = mapped_column(
        ForeignKey("material_takeoff_lines.id"), nullable=True, index=True
    )
    drawing_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("drawing_revisions.id"), nullable=True
    )
    planning_wbs_id: Mapped[int | None] = mapped_column(
        ForeignKey("planning_wbs.id"), nullable=True, index=True
    )


class FulfilmentAllocation(Base):
    """Approved requirement quantity covered by project stock before anything is purchased.

    An allocation is a planning hold. It does not move or reserve warehouse stock.
    """

    __tablename__ = "fulfilment_allocations"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    requirement_line_id: Mapped[int] = mapped_column(
        ForeignKey("material_requirement_lines.id"), index=True
    )
    item_id: Mapped[int] = mapped_column(ForeignKey("procurement_items.id"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("procurement_warehouses.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="Active")
    release_reason: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    released_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PurchaseRequisition(Base):
    __tablename__ = "purchase_requisitions"
    __table_args__ = (UniqueConstraint("project_id", "number_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[str] = mapped_column(String(80))
    number_key: Mapped[str] = mapped_column(String(80))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id"), index=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    request_date: Mapped[date] = mapped_column(Date)
    required_delivery: Mapped[date] = mapped_column(Date)
    justification: Mapped[str] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(8), default="")
    status: Mapped[str] = mapped_column(String(40), default="Draft")
    cancellation_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class RequisitionLine(Base):
    __tablename__ = "purchase_requisition_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    requisition_id: Mapped[int] = mapped_column(ForeignKey("purchase_requisitions.id"), index=True)
    requirement_line_id: Mapped[int] = mapped_column(
        ForeignKey("material_requirement_lines.id"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    item_id: Mapped[int] = mapped_column(ForeignKey("procurement_items.id"))
    specification: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit: Mapped[str] = mapped_column(String(20))
    estimated_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)


class ProcurementFile(Base):
    __tablename__ = "procurement_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    resource: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[int] = mapped_column(Integer, index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("stored_files.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RequestForQuotation(Base):
    __tablename__ = "request_for_quotations"
    __table_args__ = (UniqueConstraint("project_id", "number_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    requisition_id: Mapped[int] = mapped_column(ForeignKey("purchase_requisitions.id"), index=True)
    number: Mapped[str] = mapped_column(String(80))
    number_key: Mapped[str] = mapped_column(String(80))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id"), index=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date] = mapped_column(Date)
    delivery_location: Mapped[str] = mapped_column(String(300), default="")
    technical_requirements: Mapped[str] = mapped_column(Text, default="")
    commercial_requirements: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="Draft")
    comparison_currency: Mapped[str] = mapped_column(String(8), default="")
    rate_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    award_reason: Mapped[str] = mapped_column(Text, default="")
    cancellation_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class RfqLine(Base):
    __tablename__ = "rfq_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("request_for_quotations.id"), index=True)
    requisition_line_id: Mapped[int] = mapped_column(ForeignKey("purchase_requisition_lines.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))


class RfqInvite(Base):
    __tablename__ = "rfq_invites"
    __table_args__ = (UniqueConstraint("rfq_id", "vendor_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("request_for_quotations.id"), index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendors.id"))


class VendorQuotation(Base):
    __tablename__ = "vendor_quotations"
    __table_args__ = (UniqueConstraint("rfq_id", "vendor_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("request_for_quotations.id"), index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendors.id"))
    reference: Mapped[str] = mapped_column(String(80))
    quotation_date: Mapped[date] = mapped_column(Date)
    validity_date: Mapped[date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(8))
    freight: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    payment_terms: Mapped[str] = mapped_column(String(300), default="")
    technical_deviations: Mapped[str] = mapped_column(Text, default="")
    conversion_rate: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    technical_decision: Mapped[str] = mapped_column(String(40), default="")
    technical_reason: Mapped[str] = mapped_column(Text, default="")
    technical_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    commercial_note: Mapped[str] = mapped_column(Text, default="")
    commercial_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class QuotationLine(Base):
    __tablename__ = "quotation_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    quotation_id: Mapped[int] = mapped_column(ForeignKey("vendor_quotations.id"), index=True)
    rfq_line_id: Mapped[int] = mapped_column(ForeignKey("rfq_lines.id"), index=True)
    specification: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=0)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (UniqueConstraint("project_id", "number_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("request_for_quotations.id"), index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendors.id"), index=True)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id"), nullable=True)
    number: Mapped[str] = mapped_column(String(80))
    number_key: Mapped[str] = mapped_column(String(80))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id"), index=True)
    currency: Mapped[str] = mapped_column(String(8), default="")
    terms: Mapped[str] = mapped_column(Text, default="")
    delivery_location: Mapped[str] = mapped_column(String(300), default="")
    promised_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="Draft")
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    acknowledgment_note: Mapped[str] = mapped_column(Text, default="")
    amendment_reason: Mapped[str] = mapped_column(Text, default="")
    cancellation_reason: Mapped[str] = mapped_column(Text, default="")
    closure_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    award_id: Mapped[int] = mapped_column(ForeignKey("rfq_awards.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"
    __table_args__ = (UniqueConstraint("project_id", "number_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("procurement_warehouses.id"), nullable=True)
    number: Mapped[str] = mapped_column(String(80))
    number_key: Mapped[str] = mapped_column(String(80))
    receipt_date: Mapped[date] = mapped_column(Date)
    delivery_note: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20), default="Posted")
    cancellation_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class StockBalance(Base):
    __tablename__ = "stock_balances"
    __table_args__ = (UniqueConstraint("project_id", "warehouse_id", "item_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("procurement_warehouses.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("procurement_items.id"), index=True)
    unit: Mapped[str] = mapped_column(String(20), default="")
    on_hand: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    reserved: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)


class StockPosting(Base):
    __tablename__ = "stock_postings"
    __table_args__ = (UniqueConstraint("project_id", "number_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("procurement_warehouses.id"), index=True)
    goods_receipt_id: Mapped[int | None] = mapped_column(ForeignKey("goods_receipts.id"), nullable=True)
    source_posting_id: Mapped[int | None] = mapped_column(ForeignKey("stock_postings.id"), nullable=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("work_packages.id"), nullable=True, index=True)
    number: Mapped[str] = mapped_column(String(80))
    number_key: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="Posted")
    reason: Mapped[str] = mapped_column(Text, default="")
    recipient: Mapped[str] = mapped_column(String(200), default="")
    cancellation_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class StockPostingLine(Base):
    __tablename__ = "stock_posting_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    posting_id: Mapped[int] = mapped_column(ForeignKey("stock_postings.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("procurement_items.id"), index=True)
    goods_receipt_line_id: Mapped[int | None] = mapped_column(ForeignKey("goods_receipt_lines.id"), nullable=True)
    source_line_id: Mapped[int | None] = mapped_column(ForeignKey("stock_posting_lines.id"), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit: Mapped[str] = mapped_column(String(20))


class GoodsReceiptLine(Base):
    __tablename__ = "goods_receipt_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    goods_receipt_id: Mapped[int] = mapped_column(ForeignKey("goods_receipts.id"), index=True)
    purchase_order_line_id: Mapped[int] = mapped_column(ForeignKey("purchase_order_lines.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))


class VendorInvoice(Base):
    __tablename__ = "vendor_invoices"
    __table_args__ = (UniqueConstraint("project_id", "number_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    number: Mapped[str] = mapped_column(String(80))
    number_key: Mapped[str] = mapped_column(String(80))
    vendor_reference: Mapped[str] = mapped_column(String(80))
    invoice_date: Mapped[date] = mapped_column(Date)
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="Draft")
    cancellation_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class VendorInvoiceLine(Base):
    __tablename__ = "vendor_invoice_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("vendor_invoices.id"), index=True)
    purchase_order_line_id: Mapped[int] = mapped_column(ForeignKey("purchase_order_lines.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    billed_unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class RfqAward(Base):
    __tablename__ = "rfq_awards"
    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("request_for_quotations.id"), index=True)
    quotation_line_id: Mapped[int] = mapped_column(ForeignKey("quotation_lines.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    awarded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProcurementEvent(Base):
    __tablename__ = "procurement_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    resource: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[int] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text, default="")
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
