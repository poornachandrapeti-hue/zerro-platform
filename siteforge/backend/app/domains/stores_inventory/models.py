from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import CheckConstraint, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Date, JSON, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class StoreLocation(Base):
    """Bins extend the existing procurement_warehouses master; no duplicate warehouse ownership."""
    __tablename__ = "stores_locations"
    __table_args__ = (UniqueConstraint("warehouse_id", "code_key", name="uq_stores_locations_warehouse_code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("procurement_warehouses.id"), nullable=False, index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("stores_locations.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    code_key: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    location_type: Mapped[str] = mapped_column(String(20), nullable=False, default="Bin")
    restrictions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class StoresDeliveryNotice(Base):
    """Pre-receipt supplier notice; does NOT create a GRN or inventory movement."""
    __tablename__ = "stores_delivery_notices"
    __table_args__ = (UniqueConstraint("project_id", "number_key", name="uq_stores_asn_project_number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False, index=True)
    vendor_company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(80), nullable=False)
    number_key: Mapped[str] = mapped_column(String(80), nullable=False)
    expected_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    delivery_note: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    lines: Mapped[list] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Submitted")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StoresExceptionalIntake(Base):
    """Approval-gated intake request; cannot be posted to inventory until future ledger release."""
    __tablename__ = "stores_exceptional_intakes"
    __table_args__ = (UniqueConstraint("project_id", "number_key", name="uq_stores_intake_project_number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(80), nullable=False)
    number_key: Mapped[str] = mapped_column(String(80), nullable=False)
    intake_type: Mapped[str] = mapped_column(String(30), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("procurement_warehouses.id"), nullable=False)
    owner_company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    source_company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    lines: Mapped[list] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Pending Review")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StoresEvidence(Base):
    """Private evidence link for a specific stores document, not an inventory transaction."""
    __tablename__ = "stores_evidence"
    __table_args__ = (UniqueConstraint("document_type", "document_id", "file_id", name="uq_stores_evidence_document_file"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(20), nullable=False)
    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    file_id: Mapped[int] = mapped_column(ForeignKey("stored_files.id"), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StoresInspectionCase(Base):
    """QA tracking only; never alters legacy stock_balances or posts stock."""
    __tablename__ = "stores_inspection_cases"
    __table_args__ = (UniqueConstraint("goods_receipt_line_id", name="uq_stores_inspection_grn_line"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    goods_receipt_line_id: Mapped[int] = mapped_column(ForeignKey("goods_receipt_lines.id"), nullable=False)
    pending_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    accepted_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    rejected_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    quarantined_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Pending Inspection")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StoresInspectionDecision(Base):
    """Append-only QA disposition record for partial acceptance and rejection."""
    __tablename__ = "stores_inspection_decisions"
    __table_args__ = (UniqueConstraint("case_id", "idempotency_key", name="uq_stores_inspection_decision_retry"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("stores_inspection_cases.id"), nullable=False, index=True)
    disposition: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StoresReceiptLot(Base):
    """Immutable intake provenance; not a physical balance or issue authorization."""
    __tablename__ = "stores_receipt_lots"
    __table_args__ = (
        UniqueConstraint("goods_receipt_line_id", "lot_code", name="uq_stores_receipt_line_lot"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    goods_receipt_line_id: Mapped[int] = mapped_column(ForeignKey("goods_receipt_lines.id"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("procurement_warehouses.id"), nullable=False)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("stores_locations.id"), nullable=True)
    owner_company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    custodian_company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    lot_code: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_number: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    heat_number: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    serial_number: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    expiry_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class StoresPostingLotAllocation(Base):
    """Explicit audit mapping of an EXISTING posting line to receipt provenance.

    This is not an additional physical posting or a release authorization.
    A line may be allocated across lots only by a privileged reconciler.
    """
    __tablename__ = "stores_posting_lot_allocations"
    __table_args__ = (
        UniqueConstraint("stock_posting_line_id", "receipt_lot_id", name="uq_stores_posting_lot_allocation"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    stock_posting_line_id: Mapped[int] = mapped_column(ForeignKey("stock_posting_lines.id"), nullable=False, index=True)
    receipt_lot_id: Mapped[int] = mapped_column(ForeignKey("stores_receipt_lots.id"), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StoresLotQAAttribution(Base):
    """Append-only attribution of receipt-line QA decisions to specific receipt lots."""
    __tablename__ = "stores_lot_qa_attributions"
    __table_args__ = (
        UniqueConstraint("inspection_case_id", "idempotency_key", name="uq_stores_lot_qa_retry"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    inspection_case_id: Mapped[int] = mapped_column(ForeignKey("stores_inspection_cases.id"), nullable=False, index=True)
    receipt_lot_id: Mapped[int] = mapped_column(ForeignKey("stores_receipt_lots.id"), nullable=False, index=True)
    disposition: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    case_version_at_entry: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StoresOutboundLotAllocation(Base):
    """Audited provenance mapping for posted outbound lines; NOT an inventory movement."""
    __tablename__ = "stores_outbound_lot_allocations"
    __table_args__ = (UniqueConstraint("stock_posting_line_id", "receipt_lot_id", name="uq_stores_outbound_line_lot"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    stock_posting_line_id: Mapped[int] = mapped_column(ForeignKey("stock_posting_lines.id"), nullable=False, index=True)
    receipt_lot_id: Mapped[int] = mapped_column(ForeignKey("stores_receipt_lots.id"), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StoresLotReservation(Base):
    """Active allocation of an eligible receipt lot; not a physical stock movement."""
    __tablename__ = "stores_lot_reservations"
    __table_args__ = (UniqueConstraint("project_id", "request_key", name="uq_stores_lot_reservation_request"),
        CheckConstraint("(receipt_lot_id IS NOT NULL AND transfer_destination_lot_id IS NULL) OR (receipt_lot_id IS NULL AND transfer_destination_lot_id IS NOT NULL)", name="ck_stores_reservation_exactly_one_lot"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    receipt_lot_id: Mapped[int | None] = mapped_column(ForeignKey("stores_receipt_lots.id"), nullable=True, index=True)
    transfer_destination_lot_id: Mapped[int | None] = mapped_column(ForeignKey("stores_transfer_destination_lots.id"), nullable=True, index=True)
    request_key: Mapped[str] = mapped_column(String(120), nullable=False)
    requirement_line_id: Mapped[int | None] = mapped_column(ForeignKey("material_requirement_lines.id"), nullable=True, index=True)
    material_request_id: Mapped[int | None] = mapped_column(ForeignKey("stores_material_requests.id"), nullable=True, index=True)
    work_package_id: Mapped[int | None] = mapped_column(ForeignKey("work_packages.id"), nullable=True, index=True)
    planning_wbs_id: Mapped[int | None] = mapped_column(ForeignKey("planning_wbs.id"), nullable=True, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Active")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StoresLotReservationAction(Base):
    """Immutable audit of reservation releases; not an inventory posting."""
    __tablename__ = "stores_lot_reservation_actions"
    __table_args__ = (UniqueConstraint("project_id", "action_key", name="uq_stores_reservation_action_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("stores_lot_reservations.id"), nullable=False)
    action_key: Mapped[str] = mapped_column(String(120), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StoresReservationReassignment(Base):
    """Immutable reference reassignment audit; no movement or physical quantity change."""
    __tablename__ = "stores_reservation_reassignments"
    __table_args__ = (UniqueConstraint("project_id", "action_key", name="uq_stores_reservation_reassign_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("stores_lot_reservations.id"), nullable=False)
    action_key: Mapped[str] = mapped_column(String(120), nullable=False)
    old_work_package_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_work_package_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    old_planning_wbs_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_planning_wbs_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StoresMaterialRequest(Base):
    """Stock issue request against an approved canonical requirement line; no new demand."""
    __tablename__ = "stores_material_requests"
    __table_args__ = (UniqueConstraint("project_id", "request_key", name="uq_stores_material_request_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    request_key: Mapped[str] = mapped_column(String(120), nullable=False)
    requirement_line_id: Mapped[int | None] = mapped_column(ForeignKey("material_requirement_lines.id"), nullable=True, index=True)
    requester_company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    work_package_id: Mapped[int | None] = mapped_column(ForeignKey("work_packages.id"), nullable=True)
    planning_wbs_id: Mapped[int | None] = mapped_column(ForeignKey("planning_wbs.id"), nullable=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("procurement_items.id"), nullable=False)
    requested_quantity: Mapped[Decimal] = mapped_column(Numeric(14,3), nullable=False)
    base_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    required_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

class StoresContractObligationLink(Base):
    """Explicit Stores-to-Contracts obligation reference; no entitlement or recovery posting."""
    __tablename__ = 'stores_contract_obligation_links'
    __table_args__ = (UniqueConstraint('material_request_id', name='uq_stores_one_contract_obligation_per_request'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False, index=True)
    material_request_id: Mapped[int] = mapped_column(ForeignKey('stores_material_requests.id'), nullable=False)
    contract_id: Mapped[int] = mapped_column(ForeignKey('contract_register.id'), nullable=False)
    obligation_id: Mapped[int] = mapped_column(ForeignKey('contract_obligations.id'), nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StoresMaterialHandover(Base):
    """Non-ledger evidence of contractor receipt for one posted Issue line."""
    __tablename__ = 'stores_material_handovers'
    __table_args__ = (UniqueConstraint('stock_posting_line_id', name='uq_stores_handover_issue_line'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False, index=True)
    stock_posting_line_id: Mapped[int] = mapped_column(ForeignKey('stock_posting_lines.id'), nullable=False)
    material_request_id: Mapped[int] = mapped_column(ForeignKey('stores_material_requests.id'), nullable=False)
    dispatched_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    received_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    damaged_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='Awaiting Acknowledgment')
    handover_reference: Mapped[str] = mapped_column(String(120), nullable=False)
    dispatch_evidence: Mapped[str] = mapped_column(Text, nullable=False)
    discrepancy_note: Mapped[str] = mapped_column(Text, nullable=False, default='')
    acknowledgment_evidence: Mapped[str] = mapped_column(Text, nullable=False, default='')
    dispatched_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str] = mapped_column(Text, nullable=False, default='')
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)



class StoresMaterialReturn(Base):
    """Return custody and QA evidence; the existing stock ledger is the only posting authority."""
    __tablename__ = 'stores_material_returns'
    __table_args__ = (UniqueConstraint('handover_id', name='uq_stores_return_handover'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False, index=True)
    handover_id: Mapped[int] = mapped_column(ForeignKey('stores_material_handovers.id'), nullable=False)
    requested_quantity: Mapped[Decimal] = mapped_column(Numeric(14,3), nullable=False)
    condition: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='Submitted')
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    received_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14,3), nullable=True)
    receipt_evidence: Mapped[str] = mapped_column(Text, nullable=False, default='')
    received_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    qa_decision: Mapped[str | None] = mapped_column(String(24), nullable=True)
    qa_evidence: Mapped[str] = mapped_column(Text, nullable=False, default='')
    qa_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    stock_posting_id: Mapped[int | None] = mapped_column(ForeignKey('stock_postings.id'), nullable=True, unique=True)
    return_location_id: Mapped[int | None] = mapped_column(ForeignKey('stores_locations.id'), nullable=True)
    placement_evidence: Mapped[str] = mapped_column(Text, nullable=False, default='')
    placement_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StoresConstructionMaterialUsage(Base):
    """Material-specific construction evidence; NOT an inventory stock ledger."""
    __tablename__ = 'stores_construction_material_usages'
    __table_args__ = (UniqueConstraint('project_id', 'evidence_key', name='uq_stores_usage_project_key'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False, index=True)
    handover_id: Mapped[int] = mapped_column(ForeignKey('stores_material_handovers.id'), nullable=False, index=True)
    work_package_id: Mapped[int] = mapped_column(ForeignKey('work_packages.id'), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('procurement_items.id'), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14,3), nullable=False)
    usage_type: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_key: Mapped[str] = mapped_column(String(120), nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='Pending QA')
    submitted_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    verified_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    verification_note: Mapped[str] = mapped_column(Text, nullable=False, default='')
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class StoresTransfer(Base):
    """Phase 6 custody transfer; NOT a stock posting or ownership/title transfer."""
    __tablename__ = 'stores_transfers'
    __table_args__ = (UniqueConstraint('project_id', 'reference', name='uq_stores_transfer_project_reference'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False, index=True)
    destination_project_id: Mapped[int | None] = mapped_column(ForeignKey('projects.id'), nullable=True, index=True)
    destination_accepted_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    destination_acceptance_evidence: Mapped[str] = mapped_column(Text, nullable=False, default='')
    # Transfer-level declarations only; authoritative lot ownership remains on receipt provenance.
    declared_owner_company_id: Mapped[int | None] = mapped_column(ForeignKey('companies.id'), nullable=True)
    source_custodian_company_id: Mapped[int | None] = mapped_column(ForeignKey('companies.id'), nullable=True)
    destination_custodian_company_id: Mapped[int | None] = mapped_column(ForeignKey('companies.id'), nullable=True)
    custody_confirmed_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    custody_confirmation_evidence: Mapped[str] = mapped_column(Text, nullable=False, default='')
    custody_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reference: Mapped[str] = mapped_column(String(120), nullable=False)
    source_warehouse_id: Mapped[int] = mapped_column(ForeignKey('procurement_warehouses.id'), nullable=False)
    destination_warehouse_id: Mapped[int] = mapped_column(ForeignKey('procurement_warehouses.id'), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey('procurement_items.id'), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14,3), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='Draft')
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    dispatched_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    received_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    dispatched_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14,3), nullable=True)
    received_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14,3), nullable=True)
    damaged_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14,3), nullable=True)
    approval_evidence: Mapped[str] = mapped_column(Text, nullable=False, default='')
    dispatch_evidence: Mapped[str] = mapped_column(Text, nullable=False, default='')
    receipt_evidence: Mapped[str] = mapped_column(Text, nullable=False, default='')
    discrepancy_note: Mapped[str] = mapped_column(Text, nullable=False, default='')
    discrepancy_status: Mapped[str] = mapped_column(String(32), nullable=False, default='Not Required')
    discrepancy_resolution: Mapped[str] = mapped_column(Text, nullable=False, default='')
    discrepancy_resolved_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class StoresTransferLotLineage(Base):
    """One-to-one planned physical lot move, NOT an inventory posting.

    Source lot is tied to its original GRN warehouse. The destination must
    obtain a separate QA-valid lineage before any physical posting may run.
    This durable row prevents pretending the source receipt lot has moved.
    """
    __tablename__ = 'stores_transfer_lot_lineage'
    __table_args__ = (
        UniqueConstraint('transfer_id', name='uq_stores_transfer_lineage_transfer'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False, index=True)
    transfer_id: Mapped[int] = mapped_column(ForeignKey('stores_transfers.id'), nullable=False, index=True)
    source_receipt_lot_id: Mapped[int] = mapped_column(ForeignKey('stores_receipt_lots.id'), nullable=False)
    destination_receipt_lot_id: Mapped[int | None] = mapped_column(ForeignKey('stores_receipt_lots.id'), nullable=True)
    source_posting_id: Mapped[int | None] = mapped_column(ForeignKey('stock_postings.id'), nullable=True)
    destination_posting_id: Mapped[int | None] = mapped_column(ForeignKey('stock_postings.id'), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='Planned')
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class StoresTransferDestinationLot(Base):
    """Transfer-derived destination provenance; NOT stock or QA authorization."""
    __tablename__ = 'stores_transfer_destination_lots'
    __table_args__ = (
        UniqueConstraint('transfer_id', name='uq_stores_destination_lot_transfer'),
        UniqueConstraint('destination_warehouse_id', 'lot_code', name='uq_stores_destination_lot_code'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, index=True)
    source_project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False)
    destination_project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False)
    transfer_id: Mapped[int] = mapped_column(ForeignKey('stores_transfers.id'), nullable=False, index=True)
    lineage_id: Mapped[int] = mapped_column(ForeignKey('stores_transfer_lot_lineage.id'), nullable=False)
    source_receipt_lot_id: Mapped[int] = mapped_column(ForeignKey('stores_receipt_lots.id'), nullable=False)
    destination_warehouse_id: Mapped[int] = mapped_column(ForeignKey('procurement_warehouses.id'), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey('procurement_items.id'), nullable=False)
    lot_code: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='PendingPostingAndQA')
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class StoresTransferIssueAllocation(Base):
    """Issue-line provenance for transfer-derived destination lots; not a second ledger."""
    __tablename__ = 'stores_transfer_issue_allocations'
    __table_args__ = (UniqueConstraint('stock_posting_line_id', name='uq_transfer_issue_posting_line'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False, index=True)
    stock_posting_line_id: Mapped[int] = mapped_column(ForeignKey('stock_posting_lines.id'), nullable=False)
    transfer_destination_lot_id: Mapped[int] = mapped_column(ForeignKey('stores_transfer_destination_lots.id'), nullable=False, index=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey('stores_lot_reservations.id'), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class StoresTransferReturnAllocation(Base):
    """Return posting line provenance for transfer-derived material (same stock ledger)."""
    __tablename__ = 'stores_transfer_return_allocations'
    __table_args__ = (UniqueConstraint('stock_posting_line_id', name='uq_transfer_return_posting_line'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False, index=True)
    stock_posting_line_id: Mapped[int] = mapped_column(ForeignKey('stock_posting_lines.id'), nullable=False)
    transfer_destination_lot_id: Mapped[int] = mapped_column(ForeignKey('stores_transfer_destination_lots.id'), nullable=False, index=True)
    original_issue_line_id: Mapped[int] = mapped_column(ForeignKey('stock_posting_lines.id'), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class StoresVendorReturn(Base):
    """Vendor return custody/evidence only; never mutates stock or PO liabilities."""
    __tablename__ = 'stores_vendor_returns'
    __table_args__ = (UniqueConstraint('project_id', 'reference', name='uq_stores_vendor_return_project_ref'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(120), nullable=False)
    vendor_id: Mapped[int] = mapped_column(ForeignKey('procurement_vendors.id'), nullable=False)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey('purchase_orders.id'), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey('procurement_items.id'), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey('procurement_warehouses.id'), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14,3), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default='Requested')
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    dispatched_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    vendor_ack_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    replacement_recorded_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    approval_evidence: Mapped[str] = mapped_column(Text, nullable=False, default='')
    dispatch_evidence: Mapped[str] = mapped_column(Text, nullable=False, default='')
    vendor_ack_evidence: Mapped[str] = mapped_column(Text, nullable=False, default='')
    replacement_reference: Mapped[str] = mapped_column(String(120), nullable=False, default='')
    replacement_evidence: Mapped[str] = mapped_column(Text, nullable=False, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StoresPreservationPlan(Base):
    """Preservation schedule for an existing GRN receipt lot; not an inventory balance."""
    __tablename__ = 'stores_preservation_plans'
    __table_args__ = (UniqueConstraint('project_id', 'receipt_lot_id', name='uq_stores_preservation_project_lot'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False, index=True)
    receipt_lot_id: Mapped[int] = mapped_column(ForeignKey('stores_receipt_lots.id'), nullable=False, index=True)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    frequency_days: Mapped[int] = mapped_column(Integer, nullable=False)
    next_due_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    responsible_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    condition: Mapped[str] = mapped_column(String(20), nullable=False, default='Unverified')
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

class StoresPreservationCheck(Base):
    """Append-only preservation inspection evidence; never posts stock."""
    __tablename__ = 'stores_preservation_checks'
    __table_args__ = (UniqueConstraint('plan_id', 'request_key', name='uq_stores_preservation_check_retry'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey('stores_preservation_plans.id'), nullable=False, index=True)
    request_key: Mapped[str] = mapped_column(String(120), nullable=False)
    condition: Mapped[str] = mapped_column(String(20), nullable=False)
    findings: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    checked_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StoresCycleCount(Base):
    """Physical count workflow. Verification does not post a stock adjustment."""
    __tablename__ = 'stores_cycle_counts'
    __table_args__ = (UniqueConstraint('project_id', 'reference', name='uq_stores_cycle_count_ref'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey('procurement_warehouses.id'), nullable=False)
    reference: Mapped[str] = mapped_column(String(120), nullable=False)
    scheduled_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='Draft')
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    submitted_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    verified_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    review_evidence: Mapped[str] = mapped_column(Text, nullable=False, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StoresCycleCountLine(Base):
    """Receipt lot physical observation and a stock snapshot, never a ledger writer."""
    __tablename__ = 'stores_cycle_count_lines'
    __table_args__ = (UniqueConstraint('count_id', 'receipt_lot_id', name='uq_stores_cycle_count_lot'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    count_id: Mapped[int] = mapped_column(ForeignKey('stores_cycle_counts.id'), nullable=False, index=True)
    receipt_lot_id: Mapped[int] = mapped_column(ForeignKey('stores_receipt_lots.id'), nullable=False)
    observed_quantity: Mapped[Decimal] = mapped_column(Numeric(14,3), nullable=False)
    recorded_lot_quantity: Mapped[Decimal] = mapped_column(Numeric(14,3), nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    counted_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    counted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StoresStockAdjustmentRequest(Base):
    """Count-linked discrepancy review; deliberately not a stock posting or book variance."""
    __tablename__ = 'stores_stock_adjustment_requests'
    __table_args__ = (UniqueConstraint('project_id','reference',name='uq_stores_adjustment_reference'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False, index=True)
    count_id: Mapped[int] = mapped_column(ForeignKey('stores_cycle_counts.id'), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='PendingReconciliation')
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    review_evidence: Mapped[str] = mapped_column(Text, nullable=False, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

class StoresScrapCase(Base):
    """Quarantine/disposal evidence only; no stock write-off or ownership transfer."""
    __tablename__ = 'stores_scrap_cases'
    __table_args__ = (UniqueConstraint('project_id','reference',name='uq_stores_scrap_project_reference'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'),nullable=False,index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'),nullable=False,index=True)
    reference: Mapped[str] = mapped_column(String(120),nullable=False)
    receipt_lot_id: Mapped[int] = mapped_column(ForeignKey('stores_receipt_lots.id'),nullable=False,index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14,3),nullable=False)
    classification: Mapped[str] = mapped_column(String(30),nullable=False)
    reason: Mapped[str] = mapped_column(Text,nullable=False)
    evidence: Mapped[str] = mapped_column(Text,nullable=False)
    status: Mapped[str] = mapped_column(String(32),nullable=False,default='Proposed')
    version: Mapped[int] = mapped_column(Integer,nullable=False,default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'),nullable=False)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    review_evidence: Mapped[str] = mapped_column(Text,nullable=False,default='')
    disposal_reference: Mapped[str] = mapped_column(String(120),nullable=False,default='')
    disposal_evidence: Mapped[str] = mapped_column(Text,nullable=False,default='')
    disposal_recorded_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)
