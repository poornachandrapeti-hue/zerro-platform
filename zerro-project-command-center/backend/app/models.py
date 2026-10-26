from datetime import date
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    client: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(160))
    start_date: Mapped[date] = mapped_column(Date)
    planned_finish: Mapped[date] = mapped_column(Date)
    forecast_finish: Mapped[date] = mapped_column(Date)
    approved_budget: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    status: Mapped[str] = mapped_column(String(30), default="Active")

    disciplines: Mapped[list["Discipline"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    milestones: Mapped[list["Milestone"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    risks: Mapped[list["Risk"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Discipline(Base):
    __tablename__ = "disciplines"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(80))
    weight: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    planned_progress: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    actual_progress: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    budget: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    target_date: Mapped[date] = mapped_column(Date)

    project: Mapped[Project] = relationship(back_populates="disciplines")
    work_packages: Mapped[list["WorkPackage"]] = relationship(back_populates="discipline", cascade="all, delete-orphan")


class Contractor(Base):
    __tablename__ = "contractors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    contact_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(30))

    work_packages: Mapped[list["WorkPackage"]] = relationship(back_populates="contractor")


class WorkPackage(Base):
    __tablename__ = "work_packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id"), index=True)
    contractor_id: Mapped[int] = mapped_column(ForeignKey("contractors.id"), index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    area: Mapped[str] = mapped_column(String(120))
    weight: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    planned_progress: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    actual_progress: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    budget: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    committed_cost: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    actual_cost: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    start_date: Mapped[date] = mapped_column(Date)
    target_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30))

    discipline: Mapped[Discipline] = relationship(back_populates="work_packages")
    contractor: Mapped[Contractor] = relationship(back_populates="work_packages")
    sub_tasks: Mapped[list["SubTask"]] = relationship(back_populates="work_package", cascade="all, delete-orphan")


class SubTask(Base):
    __tablename__ = "sub_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_package_id: Mapped[int] = mapped_column(ForeignKey("work_packages.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(160))
    owner: Mapped[str] = mapped_column(String(100), default="")
    weight: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    planned_progress: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    actual_progress: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="On Track")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    work_package: Mapped[WorkPackage] = relationship(back_populates="sub_tasks")


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    discipline_code: Mapped[str] = mapped_column(String(30))
    planned_date: Mapped[date] = mapped_column(Date)
    forecast_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30))

    project: Mapped[Project] = relationship(back_populates="milestones")


class Risk(Base):
    __tablename__ = "risks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    discipline_code: Mapped[str] = mapped_column(String(30))
    severity: Mapped[str] = mapped_column(String(20))
    owner: Mapped[str] = mapped_column(String(100))
    due_date: Mapped[date] = mapped_column(Date)
    mitigation: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="Open")

    project: Mapped[Project] = relationship(back_populates="risks")



class ConsumedSSOTicket(Base):
    """Atomic, cross-worker replay protection for short-lived SSO handoff tokens."""
    __tablename__ = "consumed_sso_tickets"

    ticket_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[int] = mapped_column()
