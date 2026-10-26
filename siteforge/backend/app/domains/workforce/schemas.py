from datetime import date, datetime, time
from typing import Literal

from pydantic import Field

from app.domains.identity_projects.schemas import Strict


class MasterIn(Strict):
    kind: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)


class MasterUpdate(Strict):
    name: str = Field(min_length=1, max_length=120)
    active: bool
    version: int = Field(ge=1)


class PersonnelIn(Strict):
    code: str = Field(min_length=1, max_length=40)
    full_name: str = Field(min_length=1, max_length=200)
    company_id: int
    personnel_type: str = Field(min_length=1, max_length=40)
    designation_id: int
    trade_id: int
    grade_id: int | None = None
    discipline_id: int | None = None
    start_date: date
    end_date: date | None = None
    supervisor_id: int | None = None
    status: str = Field(default="Active", max_length=20)
    user_id: int | None = None
    contact_number: str = Field(default="", max_length=40)
    emergency_contact: str = Field(default="", max_length=500)
    date_of_birth: date | None = None
    address: str = Field(default="", max_length=500)
    identity_reference: str = Field(default="", max_length=120)


class PersonnelUpdate(PersonnelIn):
    version: int = Field(ge=1)


class DeploymentIn(Strict):
    personnel_id: int
    discipline_id: int | None = None
    supervisor_id: int | None = None
    area_id: int | None = None
    planned_start: date
    planned_end: date | None = None
    shift: str = Field(default="", max_length=80)
    required_skills: str = Field(default="", max_length=1000)
    checks: list[str] = Field(default_factory=list)


class DeploymentUpdate(Strict):
    discipline_id: int | None = None
    supervisor_id: int | None = None
    area_id: int | None = None
    planned_start: date
    planned_end: date | None = None
    shift: str = Field(default="", max_length=80)
    required_skills: str = Field(default="", max_length=1000)
    version: int = Field(ge=1)


class CheckIn(Strict):
    status: str = Field(min_length=1, max_length=20)
    evidence: str = Field(default="", max_length=1000)
    version: int = Field(ge=1)


class MoveIn(Strict):
    action: str = Field(min_length=1, max_length=40)
    on: date | None = None
    reason: str = Field(default="", max_length=500)
    version: int = Field(ge=1)


class VersionIn(Strict):
    version: int = Field(ge=1)


class RequestIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    discipline_id: int | None = None
    area_id: int | None = None
    package_id: int | None = None
    company_id: int
    trade_id: int
    headcount: int = Field(ge=1, le=10000)
    qualifications: str = Field(default="", max_length=1000)
    start_date: date
    end_date: date | None = None
    shift: str = Field(default="", max_length=80)
    priority: str = Field(default="Normal", max_length=20)
    justification: str = Field(min_length=3, max_length=2000)
    activity_id: int | None = None
    grade_id: int | None = None
    required_hours: int | None = Field(default=None, ge=1, le=1000000)
    required_mobilization: date | None = None


class RequestUpdate(RequestIn):
    version: int = Field(ge=1)


class LineIn(Strict):
    personnel_id: int
    state: str = Field(default="Proposed", max_length=20)
    deployment_id: int | None = None
    version: int = Field(ge=1)


class ForecastIn(Strict):
    expected_mobilization: date | None = None
    version: int = Field(ge=1)


class CloseIn(Strict):
    action: str = Field(min_length=1, max_length=20)
    reason: str = Field(min_length=3, max_length=500)
    version: int = Field(ge=1)


class ShiftIn(Strict):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    start_time: time
    end_time: time
    break_minutes: int = Field(default=0, ge=0, le=720)
    attribution: str = "Start day"
    calendar: str = Field(default="", max_length=120)
    effective_from: date
    effective_to: date | None = None


class ShiftUpdate(ShiftIn):
    active: bool = True
    version: int = Field(ge=1)


class CrewIn(Strict):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(default="", max_length=120)
    company_id: int
    discipline_id: int | None = None
    trade_id: int | None = None
    area_id: int | None = None
    supervisor_id: int | None = None
    lead_id: int | None = None
    shift_id: int | None = None
    effective_from: date
    effective_to: date | None = None


class CrewUpdate(CrewIn):
    active: bool = True
    version: int = Field(ge=1)


class MemberIn(Strict):
    personnel_id: int
    start_date: date
    end_date: date | None = None
    version: int = Field(ge=1)


class MemberEnd(Strict):
    end_date: date
    version: int = Field(ge=1)


class SheetIn(Strict):
    shift_id: int
    crew_id: int | None = None
    attendance_date: date


class SegmentIn(Strict):
    check_in: datetime
    check_out: datetime


class AttendanceIn(Strict):
    personnel_id: int
    status: str
    segments: list[SegmentIn] = Field(default_factory=list, max_length=8)
    remarks: str = Field(default="", max_length=2000)
    version: int = Field(ge=1)


class RemoveIn(Strict):
    personnel_id: int
    version: int = Field(ge=1)


class CorrectionIn(Strict):
    kind: str
    status: str
    segments: list[SegmentIn] = Field(default_factory=list, max_length=8)
    reason: str = Field(min_length=3, max_length=2000)
    evidence: str = Field(min_length=3, max_length=2000)


class LockIn(Strict):
    period_start: date
    period_end: date
    reason: str = Field(default="", max_length=2000)


class ReopenIn(Strict):
    reason: str = Field(min_length=3, max_length=2000)


class LeaveIn(Strict):
    personnel_id: int
    leave_type_id: int
    start_date: date
    end_date: date
    start_time: time | None = None
    end_time: time | None = None
    reason: str = Field(default="", max_length=2000)
    evidence: str = Field(default="", max_length=2000)


class LeaveUpdate(LeaveIn):
    version: int = Field(ge=1)


class CancelIn(Strict):
    reason: str = Field(min_length=3, max_length=2000)
    version: int = Field(ge=1)


class OvertimeIn(Strict):
    personnel_id: int | None = None
    crew_id: int | None = None
    work_date: date
    shift_id: int
    package_id: int | None = None
    requested_minutes: int = Field(ge=15, le=960)
    reason: str = Field(min_length=3, max_length=2000)


class ApprovedHoursIn(Strict):
    approved_minutes: int = Field(ge=0, le=960)
    version: int = Field(ge=1)


class CredentialTypeIn(Strict):
    name: str = Field(min_length=2, max_length=120)
    owner: Literal["HR", "HSE", "QA/QC"]
    requires_expiry: bool = True


class CredentialTypeUpdate(CredentialTypeIn):
    active: bool = True
    version: int = Field(ge=1)


class CredentialIn(Strict):
    personnel_id: int
    type_id: int
    certificate_number: str = Field(default="", max_length=80)
    issuer: str = Field(default="", max_length=200)
    issue_date: date
    expiry_date: date | None = None
    evidence: str = Field(min_length=3, max_length=2000)
    applicable_activities: str = Field(default="", max_length=2000)


class CredentialDecision(Strict):
    action: Literal["verify", "reject"]
    reason: str = Field(default="", max_length=2000)
    version: int = Field(ge=1)


class CredentialRuleIn(Strict):
    type_id: int
    package_id: int | None = None
    activity_id: int | None = None


class OffboardingIn(Strict):
    deployment_id: int
    last_working_date: date
    reason: str = Field(default="", max_length=2000)


class OffboardingItemIn(Strict):
    status: Literal["Pending", "Done", "Not applicable"]
    note: str = Field(default="", max_length=2000)
    version: int = Field(ge=1)


class MonitorIn(Strict):
    enabled: bool = True
    mobilization_grace_days: int = Field(default=2, ge=0, le=60)
    onboarding_lead_days: int = Field(default=3, ge=0, le=60)
    attendance_grace_days: int = Field(default=1, ge=1, le=14)
    escalate_after_days: int = Field(default=3, ge=1, le=60)
    escalation_user_ids: list[int] = Field(default_factory=list, max_length=20)
    version: int | None = None
