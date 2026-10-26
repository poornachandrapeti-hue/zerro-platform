from datetime import date

from pydantic import Field

from app.domains.identity_projects.schemas import Strict


class AssignmentIn(Strict):
    activity_id: int
    work_date: date
    shift_id: int
    personnel_id: int | None = None
    crew_id: int | None = None
    demand_id: int | None = None
    planned_minutes: int = Field(ge=30, le=1440)
    note: str = Field(default="", max_length=500)


class AssignmentRelease(Strict):
    reason: str = Field(min_length=3, max_length=500)
    version: int = Field(ge=1)


class ReturnReason(Strict):
    personnel_id: int
    reason: str = Field(default="", max_length=500)


class ReturnSubmit(Strict):
    work_date: date
    shift_id: int
    note: str = Field(default="", max_length=1000)
    reasons: list[ReturnReason] = Field(default_factory=list)
    version: int | None = None


class ReturnBack(Strict):
    reason: str = Field(min_length=3, max_length=500)
    version: int = Field(ge=1)
