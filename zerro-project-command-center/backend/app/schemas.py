from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ContractorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    contact_name: str
    phone: str


class ContractorCreate(BaseModel):
    code: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=160)
    contact_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=5, max_length=30)


class ContractorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    contact_name: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = Field(default=None, min_length=5, max_length=30)


class WorkPackageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    area: str
    weight: float
    planned_progress: float
    actual_progress: float
    budget: float
    committed_cost: float
    actual_cost: float
    start_date: date
    target_date: date
    status: str
    contractor: ContractorOut
    sub_tasks: list["SubTaskOut"] = []


class SubTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    owner: str
    weight: float
    planned_progress: float
    actual_progress: float
    status: str
    start_date: date | None = None
    target_date: date | None = None
    notes: str = ""


class SubTaskCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=160)
    owner: str = Field(default="", max_length=100)
    weight: Decimal = Field(gt=0, le=100)
    planned_progress: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    actual_progress: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    status: str = Field(default="On Track", min_length=2, max_length=30)
    start_date: date | None = None
    target_date: date | None = None
    notes: str = Field(default="", max_length=500)


class SubTaskUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    owner: str | None = Field(default=None, max_length=100)
    weight: Decimal | None = Field(default=None, gt=0, le=100)
    planned_progress: Decimal | None = Field(default=None, ge=0, le=100)
    actual_progress: Decimal | None = Field(default=None, ge=0, le=100)
    status: str | None = Field(default=None, min_length=2, max_length=30)
    start_date: date | None = None
    target_date: date | None = None
    notes: str | None = Field(default=None, max_length=500)


class WorkPackageCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=160)
    area: str = Field(min_length=2, max_length=120)
    contractor_id: int
    weight: Decimal = Field(gt=0, le=100)
    planned_progress: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    actual_progress: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    budget: Decimal = Field(ge=0)
    committed_cost: Decimal = Field(default=Decimal("0"), ge=0)
    actual_cost: Decimal = Field(default=Decimal("0"), ge=0)
    start_date: date
    target_date: date
    status: str = Field(default="On Track", min_length=2, max_length=30)


class WorkPackageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    area: str | None = Field(default=None, min_length=2, max_length=120)
    contractor_id: int | None = None
    weight: Decimal | None = Field(default=None, gt=0, le=100)
    planned_progress: Decimal | None = Field(default=None, ge=0, le=100)
    actual_progress: Decimal | None = Field(default=None, ge=0, le=100)
    budget: Decimal | None = Field(default=None, ge=0)
    committed_cost: Decimal | None = Field(default=None, ge=0)
    actual_cost: Decimal | None = Field(default=None, ge=0)
    start_date: date | None = None
    target_date: date | None = None
    status: str | None = Field(default=None, min_length=2, max_length=30)


class DisciplineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    weight: float
    planned_progress: float
    actual_progress: float
    budget: float
    target_date: date
    work_packages: list[WorkPackageOut] = []


class ProjectListItem(BaseModel):
    id: int
    code: str
    name: str
    client: str
    location: str
    status: str
    overall_progress: float
    planned_progress: float
    planned_finish: date
    forecast_finish: date


class ProjectCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=180)
    client: str = Field(min_length=2, max_length=120)
    location: str = Field(min_length=2, max_length=160)
    start_date: date
    planned_finish: date
    forecast_finish: date
    approved_budget: Decimal = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=8)
    status: str = Field(default="Active", min_length=2, max_length=30)


class MilestoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    discipline_code: str
    planned_date: date
    forecast_date: date
    status: str


class RiskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    discipline_code: str
    severity: str
    owner: str
    due_date: date
    mitigation: str
    status: str


class ProjectDashboard(BaseModel):
    id: int
    code: str
    name: str
    client: str
    location: str
    status: str
    start_date: date
    planned_finish: date
    forecast_finish: date
    approved_budget: float
    currency: str
    main_contractor: str = ""
    overall_progress: float
    planned_progress: float
    budget_committed: float
    actual_cost: float
    disciplines: list[DisciplineOut]
    milestones: list[MilestoneOut]
    risks: list[RiskOut]


class ProgressUpdate(BaseModel):
    actual_progress: Decimal = Field(ge=0, le=100)
    actual_cost: Decimal = Field(ge=0)
    status: str = Field(min_length=2, max_length=30)


WorkPackageOut.model_rebuild()
