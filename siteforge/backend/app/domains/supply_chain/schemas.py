from datetime import date
from decimal import Decimal

from pydantic import Field

from app.domains.identity_projects.schemas import Strict

ITEM_TYPES = ("Material", "Equipment", "Consumable", "Spare", "Tool")
PRIORITIES = ("Normal", "High", "Critical")
VENDOR_STATES = ("Pending", "Approved", "Suspended")


class ItemIn(Strict):
    code: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=300)
    item_type: str
    category: str = Field(min_length=1, max_length=120)
    subcategory: str = Field(default="", max_length=120)
    discipline_ids: list[int] = Field(min_length=1)
    specification: str = ""
    size_rating: str = ""
    material_grade: str = Field(default="", max_length=120)
    applicable_standard: str = Field(default="", max_length=200)
    specification_discipline: str = ""
    specification_attributes: dict[str, str | int | float | bool | list[str]] = Field(default_factory=dict)
    base_unit: str = Field(min_length=1, max_length=20)
    purchase_unit: str = Field(default="", max_length=20)
    issue_unit: str = Field(default="", max_length=20)
    approved_make: str = ""
    model_number: str = Field(default="", max_length=120)
    manufacturer_part_number: str = Field(default="", max_length=120)
    hsn_code: str = Field(default="", max_length=20)
    inspection_required: bool = False
    tracking_required: bool = False
    mtc_required: bool = False
    calibration_certificate_required: bool = False
    shelf_life_applicable: bool = False
    shelf_life_days: int | None = Field(default=None, ge=1, le=36500)
    preferred_vendor_id: int | None = Field(default=None, gt=0)
    active: bool = True
    version: int | None = Field(default=None, gt=0)
    allow_duplicate: bool = False


class ConversionIn(Strict):
    from_unit: str = Field(min_length=1, max_length=20)
    to_unit: str = Field(min_length=1, max_length=20)
    factor: Decimal = Field(gt=0, max_digits=14, decimal_places=6)


class VendorIn(Strict):
    code: str = Field(min_length=1, max_length=80)
    company_id: int
    categories: str = ""
    contact_name: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    tax_details: str = ""
    approval_status: str = "Pending"
    active: bool = True
    version: int | None = Field(default=None, gt=0)


class WarehouseIn(Strict):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    location: str = ""
    area_id: int | None = None
    officer_id: int
    active: bool = True
    version: int | None = Field(default=None, gt=0)


class LineIn(Strict):
    id: int | None = None
    item_id: int
    specification: str = ""
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit: str = Field(min_length=1, max_length=20)
    required_date: date
    tag: str = ""
    engineering_reference: str = ""
    planning_wbs_id: int | None = Field(default=None, gt=0)


class RequirementIn(Strict):
    number: str = Field(min_length=1, max_length=80)
    company_id: int
    discipline_id: int
    area_id: int | None = None
    requested_by: int
    required_date: date
    priority: str = "Normal"
    purpose: str = Field(min_length=1, max_length=2000)
    remarks: str = ""
    drawing_id: int | None = None
    drawing_revision_id: int | None = None
    work_package_ids: list[int] | None = None
    lines: list[LineIn] = Field(min_length=1)
    version: int | None = Field(default=None, gt=0)


class VersionIn(Strict):
    version: int = Field(gt=0)


class ReasonIn(Strict):
    reason: str = Field(min_length=1, max_length=2000)
    version: int = Field(gt=0)


class ResubmitIn(Strict):
    version: int = Field(gt=0)
    review_version: int = Field(gt=0)


class ImpactIn(Strict):
    decision: str = Field(min_length=1, max_length=2000)
    affected_quantity: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    version: int = Field(gt=0)


class RequisitionLineIn(Strict):
    requirement_line_id: int
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    estimated_price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)


class RfqLineIn(Strict):
    requisition_line_id: int
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class RfqIn(Strict):
    number: str = Field(min_length=1, max_length=80)
    requisition_id: int
    due_date: date
    delivery_location: str = ""
    technical_requirements: str = Field(min_length=1, max_length=4000)
    commercial_requirements: str = ""
    vendor_ids: list[int] = Field(min_length=1)
    lines: list[RfqLineIn] = Field(min_length=1)


class QuoteLineIn(Strict):
    rfq_line_id: int
    specification: str = ""
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    discount: Decimal = Field(default=0, ge=0, max_digits=14, decimal_places=2)
    tax: Decimal = Field(default=0, ge=0, max_digits=14, decimal_places=2)
    lead_time_days: int = Field(default=0, ge=0)


class QuoteIn(Strict):
    vendor_id: int
    reference: str = Field(min_length=1, max_length=80)
    quotation_date: date
    validity_date: date
    currency: str = Field(min_length=1, max_length=8)
    freight: Decimal = Field(default=0, ge=0, max_digits=14, decimal_places=2)
    payment_terms: str = ""
    technical_deviations: str = ""
    lines: list[QuoteLineIn] = Field(min_length=1)
    version: int = Field(gt=0)


class TechnicalIn(Strict):
    quotation_id: int
    decision: str
    reason: str = ""
    version: int = Field(gt=0)


class CommercialNoteIn(Strict):
    quotation_id: int
    commercial_note: str = Field(min_length=1, max_length=2000)
    conversion_rate: Decimal = Field(gt=0, max_digits=14, decimal_places=6)


class CommercialIn(Strict):
    comparison_currency: str = Field(min_length=1, max_length=8)
    rate_date: date
    notes: list[CommercialNoteIn] = Field(min_length=1)
    version: int = Field(gt=0)


class PoLineIn(Strict):
    award_id: int
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class PoIn(Strict):
    number: str = Field(min_length=1, max_length=80)
    lines: list[PoLineIn] = Field(min_length=1)
    terms: str = ""
    delivery_location: str = ""
    promised_date: date


class PoUpdateIn(PoIn):
    version: int = Field(gt=0)


class PoAmendIn(PoIn):
    reason: str = Field(min_length=1, max_length=2000)


class AcknowledgeIn(Strict):
    note: str = Field(min_length=1, max_length=2000)
    version: int = Field(gt=0)


class StockQtyIn(Strict):
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class AcceptLineIn(StockQtyIn):
    goods_receipt_line_id: int


class ItemQtyIn(StockQtyIn):
    item_id: int


class ReturnLineIn(StockQtyIn):
    source_line_id: int


class AcceptIn(Strict):
    number: str = Field(min_length=1, max_length=80)
    warehouse_id: int
    goods_receipt_id: int
    lines: list[AcceptLineIn] = Field(min_length=1)


class ReservationIn(Strict):
    number: str = Field(min_length=1, max_length=80)
    warehouse_id: int
    reason: str = Field(min_length=1, max_length=2000)
    lines: list[ItemQtyIn] = Field(min_length=1)
    package_id: int | None = None


class IssueIn(ReservationIn):
    recipient: str = Field(min_length=1, max_length=200)
    reservation_id: int | None = None


class ReturnIn(Strict):
    number: str = Field(min_length=1, max_length=80)
    issue_id: int
    reason: str = Field(min_length=1, max_length=2000)
    lines: list[ReturnLineIn] = Field(min_length=1)


class ReceiptLineIn(Strict):
    purchase_order_line_id: int
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class ReceiptIn(Strict):
    number: str = Field(min_length=1, max_length=80)
    purchase_order_id: int
    receipt_date: date
    delivery_note: str = ""
    warehouse_id: int | None = None
    lines: list[ReceiptLineIn] = Field(min_length=1)


class InvoiceLineIn(Strict):
    purchase_order_line_id: int
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    billed_unit_price: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class InvoiceIn(Strict):
    number: str = Field(min_length=1, max_length=80)
    purchase_order_id: int
    vendor_reference: str = Field(min_length=1, max_length=80)
    invoice_date: date
    note: str = ""
    lines: list[InvoiceLineIn] = Field(min_length=1)


class InvoiceUpdateIn(InvoiceIn):
    version: int = Field(gt=0)


class AwardLineIn(Strict):
    quotation_line_id: int
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class AwardIn(Strict):
    reason: str = Field(min_length=1, max_length=2000)
    lines: list[AwardLineIn] = Field(min_length=1)
    version: int = Field(gt=0)


class RequisitionIn(Strict):
    number: str = Field(min_length=1, max_length=80)
    request_date: date
    required_delivery: date
    justification: str = Field(min_length=1, max_length=2000)
    currency: str = ""
    lines: list[RequisitionLineIn] = Field(min_length=1)
    version: int | None = Field(default=None, gt=0)


class AllocationLineIn(Strict):
    line_id: int
    warehouse_id: int
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class AllocateIn(Strict):
    lines: list[AllocationLineIn] = Field(min_length=1)


class ReleaseIn(Strict):
    reason: str = Field(min_length=1, max_length=2000)


class UncoveredIn(Strict):
    number: str = Field(min_length=1, max_length=80)
    request_date: date
    required_delivery: date
    justification: str = Field(min_length=1, max_length=2000)
