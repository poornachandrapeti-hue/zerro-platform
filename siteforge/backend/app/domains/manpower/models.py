from datetime import date, datetime
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.domains.workforce.models import now

ASSIGNMENT_STATES = ("Proposed", "Confirmed", "Released")


class Assignment(Base):
    """A planned allocation of one person to an activity, date, and shift. It is not attendance."""

    __tablename__ = "mp_assignments"
    __table_args__ = (
        CheckConstraint("state IN ('Proposed', 'Confirmed', 'Released')", name="ck_mp_assignment_state"),
        CheckConstraint("planned_minutes > 0", name="ck_mp_assignment_minutes"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("construction_activities.id"), index=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    shift_id: Mapped[int] = mapped_column(ForeignKey("hr_shifts.id"))
    personnel_id: Mapped[int] = mapped_column(ForeignKey("hr_personnel.id"), index=True)
    deployment_id: Mapped[int] = mapped_column(ForeignKey("hr_deployments.id"))
    crew_id: Mapped[int | None] = mapped_column(ForeignKey("hr_crews.id"), nullable=True)
    demand_id: Mapped[int | None] = mapped_column(ForeignKey("hr_requests.id"), nullable=True)
    planned_minutes: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[str] = mapped_column(String(20), default="Proposed")
    release_reason: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


RETURN_STATES = ("Submitted", "Returned", "Accepted")


class DailyReturn(Base):
    """One daily return for a date and shift. It reads HR and Construction; it never edits them."""

    __tablename__ = "mp_daily_returns"
    __table_args__ = (
        UniqueConstraint("project_id", "work_date", "shift_id", name="uq_mp_return_day"),
        CheckConstraint("state IN ('Submitted', 'Returned', 'Accepted')", name="ck_mp_return_state"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    shift_id: Mapped[int] = mapped_column(ForeignKey("hr_shifts.id"))
    state: Mapped[str] = mapped_column(String(20), default="Submitted")
    note: Mapped[str] = mapped_column(Text, default="")
    return_reason: Mapped[str] = mapped_column(Text, default="")
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    accepted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReturnLine(Base):
    """The minutes and flags for one person, frozen when the return is submitted."""

    __tablename__ = "mp_return_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    return_id: Mapped[int] = mapped_column(ForeignKey("mp_daily_returns.id"), index=True)
    personnel_id: Mapped[int] = mapped_column(ForeignKey("hr_personnel.id"))
    planned_minutes: Mapped[int] = mapped_column(Integer, default=0)
    attended_minutes: Mapped[int] = mapped_column(Integer, default=0)
    booked_minutes: Mapped[int] = mapped_column(Integer, default=0)
    attendance: Mapped[str] = mapped_column(String(30), default="")
    flags: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str] = mapped_column(Text, default="")
