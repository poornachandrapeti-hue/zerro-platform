from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator

from app.domains.identity_projects.schemas import Strict

Method = Literal["Quantity", "Item completion", "Weighted milestones"]
Kind = Literal["Pile", "Foundation", "Equipment", "Cable", "Instrument", "Spool", "Joint", "Other"]


class TemplateIn(Strict):
    discipline_id: int
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=40)
    prerequisites: str = Field(default="", max_length=1000)
    required_evidence: str = Field(default="", max_length=1000)
    checkpoints: list[str] = Field(min_length=1)
    progress_method: Method
    completion_conditions: str = Field(default="", max_length=1000)

    @field_validator("checkpoints")
    @classmethod
    def checkpoint_text(cls, values):
        cleaned = []
        for value in values:
            text = value.strip()
            if not text or len(text) > 120:
                raise ValueError("Each checkpoint needs a short name")
            cleaned.append(text)
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Checkpoints must be different")
        return cleaned


class TemplateUpdateIn(TemplateIn):
    active: bool = True
    version: int = Field(ge=1)


class PackageIn(Strict):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    discipline_id: int
    area_id: int
    scope_description: str = Field(min_length=1, max_length=4000)
    company_id: int
    responsible_user_id: int | None = None
    supervisor_user_id: int | None = None
    priority: Literal["Normal", "High", "Critical"] = "Normal"
    planning_reference: str = Field(default="", max_length=120)
    planned_start: date | None = None
    planned_finish: date | None = None
    remarks: str = Field(default="", max_length=2000)
    revision_ids: list[int] = Field(default_factory=list)
    requirement_ids: list[int] = Field(default_factory=list)


class PackageUpdateIn(PackageIn):
    version: int = Field(ge=1)


class CancelIn(Strict):
    reason: str = Field(min_length=3, max_length=500)
    version: int = Field(ge=1)


class ActivityIn(Strict):
    package_id: int
    template_id: int | None = None
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=40)
    company_id: int
    responsible_user_id: int | None = None
    drawing_revision_id: int | None = None
    predecessor_ids: list[int] = Field(default_factory=list)
    measurement_method: Method
    progress_weight: Decimal | None = Field(default=None, gt=0, le=100)
    target_start: date | None = None
    target_finish: date | None = None


class ActivityUpdateIn(ActivityIn):
    active: bool = True
    version: int = Field(ge=1)
    quantity_reason: str = Field(default="", max_length=500)


class ItemIn(Strict):
    activity_id: int
    identifier: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=2000)
    item_kind: Kind
    quantity: Decimal | None = Field(default=None, gt=0)
    drawing_revision_id: int | None = None


class ItemUpdateIn(ItemIn):
    active: bool = True
    version: int = Field(ge=1)


CheckType = Literal[
    "Drawing",
    "Material",
    "Material issue",
    "Predecessor",
    "Workfront",
    "Manpower",
    "Procedure",
    "Inspection",
    "Permit",
    "Quality hold",
]
CheckStatus = Literal["Not Checked", "Pending", "Satisfied", "Blocked", "Not Applicable"]


class ReadinessIn(Strict):
    check_type: CheckType
    classification: Literal["Mandatory", "Advisory"]
    owner_user_id: int | None = None
    required_date: date | None = None


class ReadinessUpdateIn(Strict):
    status: CheckStatus
    evidence: str = Field(default="", max_length=2000)
    version: int = Field(ge=1)


class ImpactIn(Strict):
    version: int = Field(ge=1)
    action: Literal["relink", "accept"]
    revision_id: int | None = None
    reason: str = Field(default="", max_length=2000)


class ReleaseIn(Strict):
    version: int = Field(ge=1)


class VersionIn(Strict):
    version: int = Field(ge=1)


class LabourIn(Strict):
    personnel_id: int
    productive_minutes: int = Field(default=0, ge=0, le=1440)
    idle_minutes: int = Field(default=0, ge=0, le=1440)
    idle_reason: str = Field(default="", max_length=500)


class HoldIn(Strict):
    reason: str = Field(min_length=3, max_length=500)
    version: int = Field(ge=1)


class DossierIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    package_id: int


class BlockerIn(Strict):
    package_id: int
    kind: Literal["Delay", "Obstruction", "Weather", "Idle"]
    description: str = Field(min_length=3, max_length=2000)
    owner_user_id: int
    recovery_note: str = Field(min_length=3, max_length=2000)


class BlockerResolveIn(Strict):
    resolution_note: str = Field(min_length=3, max_length=2000)
    version: int = Field(ge=1)


class ReportIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    report_date: date
    shift: Literal["Day", "Night", "General"]
    discipline_id: int
    area_id: int
    company_id: int
    site_engineer_id: int
    weather: str = Field(default="", max_length=120)
    remarks: str = Field(default="", max_length=2000)


class ReportUpdateIn(ReportIn):
    version: int = Field(ge=1)


class MilestoneIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    weight: Decimal = Field(gt=0, le=100)


class MilestonesIn(Strict):
    milestones: list[MilestoneIn] = Field(min_length=1)


class LineIn(Strict):
    activity_id: int
    item_id: int | None = None
    milestone_id: int | None = None
    reverses_line_id: int | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    drawing_revision_id: int | None = None
    crew_reference: str = Field(default="", max_length=200)
    equipment_hours: Decimal | None = Field(default=None, ge=0)
    material_reference: str = Field(default="", max_length=200)
    stock_posting_id: int | None = None
    delay_reason: str = Field(default="", max_length=500)
    evidence: str = Field(default="", max_length=2000)
    rework: bool = False
