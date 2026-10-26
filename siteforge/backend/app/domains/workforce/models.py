from datetime import date, datetime, time, timezone

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def now():
    return datetime.now(timezone.utc)


MASTER_KINDS = ("Designation", "Trade", "Skill grade", "Training type", "Document requirement", "Leave type")
REQUEST_FLOW = ("Draft", "Pending Approval", "Approved", "Returned", "Rejected", "Cancelled")
CREDENTIAL_OWNERS = ("HR", "HSE", "QA/QC")
CREDENTIAL_STATUSES = ("Pending Verification", "Verified", "Rejected", "Withdrawn")
PERSONNEL_TYPES = ("Employee", "Contract Worker", "Temporary Worker", "Consultant")
PERSONNEL_STATUSES = ("Active", "Inactive", "Separated")
DEPLOYMENT_STATUSES = (
    "Proposed",
    "Pending Approval",
    "Approved for Mobilization",
    "Mobilized",
    "Temporarily Unavailable",
    "Demobilized",
    "Cancelled",
)
CHECK_TYPES = ("Personnel documents", "Qualifications", "Site induction", "Work eligibility", "Access arrangements")
CHECK_STATUSES = ("Pending", "Verified", "Not required")
REQUEST_STATUSES = (
    "Draft",
    "Pending Review",
    "Returned",
    "Rejected",
    "Open",
    "Partially Allocated",
    "Allocated",
    "Closed",
    "Cancelled",
)
PRIORITIES = ("Low", "Normal", "High", "Urgent")
LINE_STATES = ("Proposed", "Allocated", "Released")
ATTRIBUTIONS = ("Start day", "End day")
SHEET_STATUSES = ("Draft", "Pending Review", "Returned", "Rejected", "Approved")
ATTENDANCE_STATUSES = ("Present", "Absent", "On Leave", "Weekly Off/Holiday", "Partial Attendance")
ATTENDANCE_SOURCES = ("Manual", "Excel Import", "Approved Device/System Integration")
CORRECTION_KINDS = ("Missing punch", "Attendance dispute", "Late submission", "Authorized adjustment")
CORRECTION_STATUSES = ("Pending Review", "Returned", "Approved", "Rejected")


class WorkforceMaster(Base):
    """Organization list values. Designation, trade, grade, and discipline stay separate fields."""

    __tablename__ = "hr_masters"
    __table_args__ = (
        UniqueConstraint("organization_id", "kind", "name_key", name="uq_hr_master_name"),
        CheckConstraint(
            "kind IN ('Designation', 'Trade', 'Skill grade', 'Training type', 'Document requirement', 'Leave type')",
            name="ck_hr_master_kind",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    name_key: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Personnel(Base):
    """A worker. A row here never grants a login, a membership, or a project role."""

    __tablename__ = "hr_personnel"
    __table_args__ = (
        UniqueConstraint("company_id", "code_key", name="uq_hr_personnel_code"),
        UniqueConstraint("user_id", name="uq_hr_personnel_user"),
        CheckConstraint(
            "personnel_type IN ('Employee', 'Contract Worker', 'Temporary Worker', 'Consultant')",
            name="ck_hr_personnel_type",
        ),
        CheckConstraint("status IN ('Active', 'Inactive', 'Separated')", name="ck_hr_personnel_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    code_key: Mapped[str] = mapped_column(String(40))
    full_name: Mapped[str] = mapped_column(String(200))
    personnel_type: Mapped[str] = mapped_column(String(40))
    designation_id: Mapped[int] = mapped_column(ForeignKey("hr_masters.id"))
    trade_id: Mapped[int] = mapped_column(ForeignKey("hr_masters.id"))
    grade_id: Mapped[int | None] = mapped_column(ForeignKey("hr_masters.id"), nullable=True)
    discipline_id: Mapped[int | None] = mapped_column(ForeignKey("disciplines.id"), nullable=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    supervisor_id: Mapped[int | None] = mapped_column(ForeignKey("hr_personnel.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="Active")
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # Restricted section. Returned only with hr.restricted.
    contact_number: Mapped[str] = mapped_column(String(40), default="")
    emergency_contact: Mapped[str] = mapped_column(Text, default="")
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    address: Mapped[str] = mapped_column(Text, default="")
    identity_reference: Mapped[str] = mapped_column(String(120), default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Deployment(Base):
    """A person placed on one project. It does not grant a login, membership, or role."""

    __tablename__ = "hr_deployments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Proposed', 'Pending Approval', 'Approved for Mobilization', 'Mobilized', 'Temporarily Unavailable', 'Demobilized', 'Cancelled')",
            name="ck_hr_deployment_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    personnel_id: Mapped[int] = mapped_column(ForeignKey("hr_personnel.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    discipline_id: Mapped[int | None] = mapped_column(ForeignKey("disciplines.id"), nullable=True)
    supervisor_id: Mapped[int | None] = mapped_column(ForeignKey("hr_personnel.id"), nullable=True)
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    planned_start: Mapped[date] = mapped_column(Date)
    planned_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    shift: Mapped[str] = mapped_column(String(80), default="")
    required_skills: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="Proposed")
    status_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class OnboardingCheck(Base):
    """One mobilization prerequisite. HR, HSE, or QA/QC verifies its own check."""

    __tablename__ = "hr_onboarding_checks"
    __table_args__ = (
        UniqueConstraint("deployment_id", "check_type", name="uq_hr_onboarding_check"),
        CheckConstraint("status IN ('Pending', 'Verified', 'Not required')", name="ck_hr_onboarding_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    deployment_id: Mapped[int] = mapped_column(ForeignKey("hr_deployments.id"), index=True)
    check_type: Mapped[str] = mapped_column(String(40))
    owner: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="Pending")
    evidence: Mapped[str] = mapped_column(Text, default="")
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class WorkforceRequest(Base):
    __tablename__ = "hr_requests"
    __table_args__ = (
        UniqueConstraint("project_id", "number_key", name="uq_hr_request_number"),
        CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned', 'Rejected', 'Open', 'Partially Allocated', 'Allocated', 'Closed', 'Cancelled')",
            name="ck_hr_request_status",
        ),
        CheckConstraint("priority IN ('Low', 'Normal', 'High', 'Urgent')", name="ck_hr_request_priority"),
        CheckConstraint("headcount > 0", name="ck_hr_request_headcount"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[str] = mapped_column(String(40))
    number_key: Mapped[str] = mapped_column(String(40))
    discipline_id: Mapped[int | None] = mapped_column(ForeignKey("disciplines.id"), nullable=True)
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("work_packages.id"), nullable=True)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("construction_activities.id"), nullable=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    trade_id: Mapped[int] = mapped_column(ForeignKey("hr_masters.id"))
    grade_id: Mapped[int | None] = mapped_column(ForeignKey("hr_masters.id"), nullable=True)
    headcount: Mapped[int] = mapped_column(Integer)
    required_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    required_mobilization: Mapped[date | None] = mapped_column(Date, nullable=True)
    qualifications: Mapped[str] = mapped_column(Text, default="")
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    shift: Mapped[str] = mapped_column(String(80), default="")
    priority: Mapped[str] = mapped_column(String(20), default="Normal")
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    justification: Mapped[str] = mapped_column(Text, default="")
    expected_mobilization: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="Draft")
    status_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RequestLine(Base):
    """A person proposed or allocated against a request. Allocated needs a live deployment."""

    __tablename__ = "hr_request_lines"
    __table_args__ = (
        UniqueConstraint("request_id", "personnel_id", name="uq_hr_request_person"),
        CheckConstraint("state IN ('Proposed', 'Allocated', 'Released')", name="ck_hr_request_line_state"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("hr_requests.id"), index=True)
    personnel_id: Mapped[int] = mapped_column(ForeignKey("hr_personnel.id"))
    deployment_id: Mapped[int | None] = mapped_column(ForeignKey("hr_deployments.id"), nullable=True)
    state: Mapped[str] = mapped_column(String(20), default="Proposed")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Shift(Base):
    """A project shift. End at or before start means the shift runs overnight."""

    __tablename__ = "hr_shifts"
    __table_args__ = (
        UniqueConstraint("project_id", "code_key", name="uq_hr_shift_code"),
        CheckConstraint("attribution IN ('Start day', 'End day')", name="ck_hr_shift_attribution"),
        CheckConstraint("break_minutes >= 0", name="ck_hr_shift_break"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    code_key: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    break_minutes: Mapped[int] = mapped_column(Integer, default=0)
    attribution: Mapped[str] = mapped_column(String(20), default="Start day")
    calendar: Mapped[str] = mapped_column(String(120), default="")
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Crew(Base):
    """A project crew. Membership is not attendance or toolbox-talk participation."""

    __tablename__ = "hr_crews"
    __table_args__ = (UniqueConstraint("project_id", "code_key", name="uq_hr_crew_code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    code_key: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120), default="")
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    discipline_id: Mapped[int | None] = mapped_column(ForeignKey("disciplines.id"), nullable=True)
    trade_id: Mapped[int | None] = mapped_column(ForeignKey("hr_masters.id"), nullable=True)
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    supervisor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("hr_personnel.id"), nullable=True)
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("hr_shifts.id"), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CrewMember(Base):
    """A dated crew membership through a deployment. Removal keeps the row."""

    __tablename__ = "hr_crew_members"
    id: Mapped[int] = mapped_column(primary_key=True)
    crew_id: Mapped[int] = mapped_column(ForeignKey("hr_crews.id"), index=True)
    personnel_id: Mapped[int] = mapped_column(ForeignKey("hr_personnel.id"), index=True)
    deployment_id: Mapped[int] = mapped_column(ForeignKey("hr_deployments.id"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    removed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AttendanceSheet(Base):
    """One supervisor submission for a date and shift, optionally for one crew."""

    __tablename__ = "hr_attendance_sheets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned', 'Rejected', 'Approved')",
            name="ck_hr_sheet_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    shift_id: Mapped[int] = mapped_column(ForeignKey("hr_shifts.id"))
    crew_id: Mapped[int | None] = mapped_column(ForeignKey("hr_crews.id"), nullable=True)
    attendance_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(20), default="Draft")
    late: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AttendanceRecord(Base):
    """One person, one date, one shift. Approved values change only through a correction."""

    __tablename__ = "hr_attendance"
    __table_args__ = (
        UniqueConstraint("project_id", "personnel_id", "attendance_date", "shift_id", name="uq_hr_attendance_day"),
        CheckConstraint(
            "status IN ('Present', 'Absent', 'On Leave', 'Weekly Off/Holiday', 'Partial Attendance')",
            name="ck_hr_attendance_status",
        ),
        CheckConstraint(
            "source IN ('Manual', 'Excel Import', 'Approved Device/System Integration')",
            name="ck_hr_attendance_source",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    sheet_id: Mapped[int] = mapped_column(ForeignKey("hr_attendance_sheets.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    personnel_id: Mapped[int] = mapped_column(ForeignKey("hr_personnel.id"), index=True)
    deployment_id: Mapped[int] = mapped_column(ForeignKey("hr_deployments.id"))
    shift_id: Mapped[int] = mapped_column(ForeignKey("hr_shifts.id"))
    attendance_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(40), default="Manual")
    worked_minutes: Mapped[int] = mapped_column(Integer, default=0)
    regular_minutes: Mapped[int] = mapped_column(Integer, default=0)
    overtime_minutes: Mapped[int] = mapped_column(Integer, default=0)
    remarks: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AttendanceSegment(Base):
    """A check-in/check-out pair in project local time. A record can hold several."""

    __tablename__ = "hr_attendance_segments"
    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_id: Mapped[int] = mapped_column(ForeignKey("hr_attendance.id"), index=True)
    check_in: Mapped[datetime] = mapped_column(DateTime)
    check_out: Mapped[datetime] = mapped_column(DateTime)


class AttendanceCorrection(Base):
    """Original and proposed values stay on the correction after it is applied."""

    __tablename__ = "hr_attendance_corrections"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('Missing punch', 'Attendance dispute', 'Late submission', 'Authorized adjustment')",
            name="ck_hr_correction_kind",
        ),
        CheckConstraint(
            "status IN ('Pending Review', 'Returned', 'Approved', 'Rejected')",
            name="ck_hr_correction_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    attendance_id: Mapped[int] = mapped_column(ForeignKey("hr_attendance.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    original: Mapped[dict] = mapped_column(JSON, default=dict)
    proposed: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="Pending Review")
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AttendanceLock(Base):
    """A locked attendance period. Reopening keeps the row and records who and why."""

    __tablename__ = "hr_attendance_locks"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text, default="")
    locked_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    reopened_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reopen_reason: Mapped[str] = mapped_column(Text, default="")


class Leave(Base):
    """Leave or temporary unavailability. The reason is restricted."""

    __tablename__ = "hr_leaves"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Draft', 'Pending Approval', 'Approved', 'Returned', 'Rejected', 'Cancelled')",
            name="ck_hr_leave_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    personnel_id: Mapped[int] = mapped_column(ForeignKey("hr_personnel.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    leave_type_id: Mapped[int] = mapped_column(ForeignKey("hr_masters.id"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[str] = mapped_column(Text, default="")
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="Draft")
    status_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Overtime(Base):
    """Requested and approved overtime. Attended and payable come from approved attendance."""

    __tablename__ = "hr_overtime"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Draft', 'Pending Approval', 'Approved', 'Returned', 'Rejected', 'Cancelled')",
            name="ck_hr_overtime_status",
        ),
        CheckConstraint("requested_minutes > 0", name="ck_hr_overtime_requested"),
        CheckConstraint("(personnel_id IS NULL) <> (crew_id IS NULL)", name="ck_hr_overtime_target"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    personnel_id: Mapped[int | None] = mapped_column(ForeignKey("hr_personnel.id"), nullable=True)
    crew_id: Mapped[int | None] = mapped_column(ForeignKey("hr_crews.id"), nullable=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    work_date: Mapped[date] = mapped_column(Date)
    shift_id: Mapped[int] = mapped_column(ForeignKey("hr_shifts.id"))
    package_id: Mapped[int | None] = mapped_column(ForeignKey("work_packages.id"), nullable=True)
    requested_minutes: Mapped[int] = mapped_column(Integer)
    approved_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="Draft")
    status_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CredentialType(Base):
    """An organization qualification type. The owner verifies every record of this type."""

    __tablename__ = "hr_credential_types"
    __table_args__ = (
        UniqueConstraint("organization_id", "name_key", name="uq_hr_credential_type_name"),
        CheckConstraint("owner IN ('HR', 'HSE', 'QA/QC')", name="ck_hr_credential_type_owner"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    name_key: Mapped[str] = mapped_column(String(120))
    owner: Mapped[str] = mapped_column(String(10))
    requires_expiry: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Credential(Base):
    """A person's qualification or training record. HR keeps it; the type owner verifies it."""

    __tablename__ = "hr_credentials"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Pending Verification', 'Verified', 'Rejected', 'Withdrawn')",
            name="ck_hr_credential_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    personnel_id: Mapped[int] = mapped_column(ForeignKey("hr_personnel.id"), index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("hr_credential_types.id"), index=True)
    certificate_number: Mapped[str] = mapped_column(String(80), default="")
    certificate_key: Mapped[str] = mapped_column(String(80), default="")
    issuer: Mapped[str] = mapped_column(String(200), default="")
    issue_date: Mapped[date] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    evidence: Mapped[str] = mapped_column(Text, default="")
    applicable_activities: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="Pending Verification")
    decision_reason: Mapped[str] = mapped_column(Text, default="")
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CredentialRule(Base):
    """A project requirement: a qualification type needed project-wide, for a package, or for one activity."""

    __tablename__ = "hr_credential_rules"
    __table_args__ = (UniqueConstraint("project_id", "type_id", "scope_key", name="uq_hr_credential_rule"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("hr_credential_types.id"))
    package_id: Mapped[int | None] = mapped_column(ForeignKey("work_packages.id"), nullable=True)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("construction_activities.id"), nullable=True)
    scope_key: Mapped[str] = mapped_column(String(40))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


OFFBOARDING_ITEMS = (
    "Project assignment closure",
    "Open task reassignment",
    "Access pass closure",
    "Company asset return",
    "Outstanding timesheet review",
    "Personnel document completion",
    "Login access review",
)


class Offboarding(Base):
    """Demobilization of one deployment: last working date, checklist, and approval. History is kept."""

    __tablename__ = "hr_offboardings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Draft', 'Pending Approval', 'Returned', 'Rejected', 'Approved', 'Cancelled')",
            name="ck_hr_offboarding_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    deployment_id: Mapped[int] = mapped_column(ForeignKey("hr_deployments.id"), index=True)
    personnel_id: Mapped[int] = mapped_column(ForeignKey("hr_personnel.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    last_working_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="Draft")
    status_reason: Mapped[str] = mapped_column(Text, default="")
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class OffboardingItem(Base):
    __tablename__ = "hr_offboarding_items"
    __table_args__ = (
        UniqueConstraint("offboarding_id", "item", name="uq_hr_offboarding_item"),
        CheckConstraint("status IN ('Pending', 'Done', 'Not applicable')", name="ck_hr_offboarding_item_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    offboarding_id: Mapped[int] = mapped_column(ForeignKey("hr_offboardings.id"), index=True)
    item: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="Pending")
    note: Mapped[str] = mapped_column(Text, default="")
    done_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class MonitorSetting(Base):
    """Per-project HR alert thresholds and escalation recipients. Without a saved row nothing is sent."""

    __tablename__ = "hr_monitor_settings"
    __table_args__ = (UniqueConstraint("project_id", name="uq_hr_monitor_project"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    mobilization_grace_days: Mapped[int] = mapped_column(Integer, default=2)
    onboarding_lead_days: Mapped[int] = mapped_column(Integer, default=3)
    attendance_grace_days: Mapped[int] = mapped_column(Integer, default=1)
    escalate_after_days: Mapped[int] = mapped_column(Integer, default=3)
    escalation_user_ids: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    modified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
