from datetime import date
from decimal import Decimal
from typing import Literal, Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, Field, field_validator, StringConstraints


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Strict):
    email: str = Field(max_length=254)
    password: Annotated[str, StringConstraints(strip_whitespace=False)] = Field(
        max_length=128
    )


class ContactIn(Strict):
    name: str = Field(min_length=1, max_length=200)
    function: Literal[
        "Client",
        "PMC",
        "Project manager",
        "Discipline",
        "Procurement",
        "Stores",
        "Site",
        "Safety",
        "Other",
    ]
    company_id: int | None = None
    user_id: int | None = None
    phone: str = Field(default="", max_length=40)
    email: str = Field(default="", max_length=254)
    note: str = Field(default="", max_length=500)

    @field_validator("email")
    @classmethod
    def email_format(cls, value):
        if value and ("@" not in value or "." not in value.split("@")[-1]):
            raise ValueError("Enter a valid email")
        return value

    @field_validator("phone")
    @classmethod
    def phone_format(cls, value):
        if not value:
            return value
        if not any(char.isdigit() for char in value) or any(
            char not in "0123456789+(). -" for char in value
        ):
            raise ValueError("Enter a phone number")
        return value


class ContactUpdateIn(ContactIn):
    active: bool = True
    version: int = Field(ge=1)


class CompanyIn(Strict):
    name: str = Field(min_length=1, max_length=200)
    company_type: Literal[
        "Owner", "Main Contractor", "Subcontractor", "PMC", "Contractor", "Vendor", "Supplier"
    ] = "Contractor"
    active: bool = True


class UserIn(Strict):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(max_length=254)
    password: Annotated[str, StringConstraints(strip_whitespace=False)] = Field(
        min_length=12, max_length=128
    )
    company_id: int | None = None
    organization_admin: bool = False

    @field_validator("email")
    @classmethod
    def email_format(cls, v):
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Enter a valid email")
        return v.lower()


class UserUpdate(Strict):
    name: str = Field(min_length=1, max_length=200)
    active: bool
    organization_admin: bool
    company_id: int | None = None


class CompanyUpdate(Strict):
    name: str = Field(min_length=1, max_length=200)
    company_type: Literal[
        "Owner", "Main Contractor", "Subcontractor", "PMC", "Contractor", "Vendor", "Supplier"
    ]
    active: bool
    version: int = Field(gt=0)


class ParticipationUpdate(Strict):
    participation_type: Literal[
        "Owner", "Main Contractor", "Subcontractor", "PMC", "Contractor"
    ]
    active: bool
    version: int = Field(gt=0)


class AreaUpdate(Strict):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    active: bool
    version: int = Field(gt=0)


class TransitionIn(Strict):
    target: Literal["Planned", "On Hold", "Completed", "Cancelled"]
    reason: str = ""
    version: int = Field(gt=0)


class DisciplineRecord(Strict):
    discipline_id: int
    scope_description: str = ""
    active: bool = True


class ProjectIn(Strict):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    project_type: str = "Industrial Plant"
    status: Literal[
        "Draft", "Planned", "Active", "On Hold", "Completed", "Cancelled"
    ] = "Draft"
    site_name: str = ""
    address: str = ""
    country: str = "India"
    state: str = ""
    city: str = ""
    postal_code: str = ""
    timezone: str = "Asia/Kolkata"
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    planned_start: date | None = None
    planned_finish: date | None = None
    actual_start: date | None = None
    actual_finish: date | None = None
    client_company_id: int | None = None
    main_contractor_company_id: int | None = None
    pmc_company_id: int | None = None
    subcontractor_ids: list[int] = Field(default_factory=list)
    lead_pm_id: int | None = None
    discipline_ids: list[int] = Field(default_factory=list)
    disciplines: list[DisciplineRecord] | None = None
    hold_reason: str = ""
    cancellation_reason: str = ""
    contract_number: str = ""
    contract_date: date | None = None
    contract_value: Decimal | None = None
    currency: str = ""

    @field_validator("timezone")
    @classmethod
    def tz_valid(cls, v):
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError:
            raise ValueError("Unknown timezone")
        return v


class ProjectUpdate(ProjectIn):
    version: int = Field(gt=0)


class MembershipIn(Strict):
    user_id: int
    role_id: int
    company_id: int
    scope: Literal["ALL", "SELECTED"]
    discipline_ids: list[int] = Field(default_factory=list)
    active: bool = True


class ParticipationIn(Strict):
    company_id: int
    participation_type: Literal[
        "Owner", "Main Contractor", "Subcontractor", "PMC", "Contractor"
    ]


class AreaIn(Strict):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    area_type: Literal["Unit", "Area", "Block"]
    parent_id: int | None = None
    description: str = ""
