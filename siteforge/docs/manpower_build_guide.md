# ZerroBuild — Manpower build guide (slices 4–6)

This guide lets you build the remaining Manpower slices yourself. Slice 4 has
complete, copy-ready code. Slices 5 and 6 follow the same pattern with a plan.

All paths below are relative to the `siteforge` folder:
`C:\Users\vihaan\Desktop\SiteForge_Foundation_Source_v0.1\siteforge`

---

## 0. Before you start (every slice)

1. Open PowerShell in the `siteforge` folder.
2. Make sure the app is running: `docker compose ps` (db, backend, frontend should be "Up").
3. If you use git, save a checkpoint: `git add -A; git commit -m "before slice 4"`.
   If you don't, copy the `siteforge` folder somewhere as a backup.
4. Check the current database migration (you will need it for `down_revision`):

```powershell
docker compose exec -T db psql -U siteforge -d siteforge -c "select version_num from alembic_version;"
```

Right now it is `f6a2d8e41c93`.

### Rules that must never be broken

- Never run `docker compose down -v` (it deletes the database and uploaded files).
- Never edit an old migration file. Always add a new one. Its `downgrade()` is just `pass`.
- In `seed.py`, only ADD permissions. Never remove one.
- Never store or show salary, bank, identity, or medical details.
- Manpower only READS HR attendance, HR deployments, and Construction progress. It never edits them.
- Don't create test records in the live app on project FLOW-01. Use the automated tests instead.
- Don't start the compose `worker` service.

---

## 1. The order of work for any slice

| Step | File | What you do |
|---|---|---|
| 1 | `backend/app/domains/manpower/models.py` | Add the table classes |
| 2 | `backend/migrations/versions/<newid>_<name>.py` | New migration that creates the tables |
| 3 | `backend/app/domains/identity_projects/seed.py` | Add new permission (if any) |
| 4 | `backend/app/domains/manpower/schemas.py` | Add input classes |
| 5 | `backend/app/domains/manpower/<slice>.py` | New module with the business rules |
| 6 | `backend/app/domains/manpower/router.py` | Add API routes |
| 7 | `backend/tests/test_manpower.py` | Add a test |
| 8 | Run tests | Fix until green |
| 9 | `frontend/src/manpower.tsx` | Add the tab and component |
| 10 | `frontend/src/style.css` | Append styles at the end |
| 11 | Deploy | Build, migrate, check in browser |
| 12 | `docs/*.md` | Update the status docs |

---

## 2. Slice 4 — Daily returns and hour reconciliation

### What it does

For one date and one HR shift, it compares each person's:

- **Planned** minutes: confirmed Manpower assignments (`mp_assignments`, slice 3)
- **Attended** minutes: HR attendance (`hr_attendance.worked_minutes`)
- **Booked** minutes: Construction progress labour (`progress_labour`, productive + idle) on approved daily reports

It flags problems:

- assigned but no attendance recorded
- attendance not approved yet
- assigned but absent / on leave
- attended without an assignment
- attended differs from planned by more than 30 minutes
- booked on activities more than attended that day

A Supervisor / Site Engineer / Manpower Coordinator **submits** the return,
giving a reason for every flagged person. The lines are saved as a snapshot.
HR or a Manpower Coordinator **accepts** it or **sends it back** with a reason.
Nobody accepts their own return. If HR attendance or progress changes after
submission, the screen shows "Source records changed since submission"; the
return is never rewritten automatically.

### Step 1 — Models

Open `backend/app/domains/manpower/models.py`.

Change the first sqlalchemy import line to include `UniqueConstraint`:

```python
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
```

Add at the end of the file:

```python
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
```

### Step 2 — Migration

1. Make a new 12-character id. In PowerShell:

```powershell
-join ((48..57) + (97..102) | Get-Random -Count 12 | ForEach-Object { [char]$_ })
```

   Say it prints `a1b2c3d4e5f6`. Use your own value everywhere below.

2. Create `backend/migrations/versions/a1b2c3d4e5f6_manpower_daily_returns.py`:

```python
"""Manpower daily returns and the manpower.returns permission. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "f6a2d8e41c93"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mp_daily_returns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("shift_id", sa.Integer(), sa.ForeignKey("hr_shifts.id"), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="Submitted"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("return_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("accepted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "work_date", "shift_id", name="uq_mp_return_day"),
        sa.CheckConstraint("state IN ('Submitted', 'Returned', 'Accepted')", name="ck_mp_return_state"),
    )
    for column in ("organization_id", "project_id", "work_date"):
        op.create_index(f"ix_mp_daily_returns_{column}", "mp_daily_returns", [column])

    op.create_table(
        "mp_return_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("return_id", sa.Integer(), sa.ForeignKey("mp_daily_returns.id"), nullable=False),
        sa.Column("personnel_id", sa.Integer(), sa.ForeignKey("hr_personnel.id"), nullable=False),
        sa.Column("planned_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attended_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("booked_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attendance", sa.String(30), nullable=False, server_default=""),
        sa.Column("flags", sa.Text(), nullable=False, server_default=""),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_mp_return_lines_return_id", "mp_return_lines", ["return_id"])

    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    pass
```

### Step 3 — Permission

Open `backend/app/domains/identity_projects/seed.py`. Find these lines (around line 172):

```python
    if name in ("Manpower Coordinator", "Supervisor", "Construction Manager", "Site Engineer"):
        permissions += ["manpower.allocate"]
    return permissions
```

Add two lines **before** `return permissions`:

```python
    if name in ("Manpower Coordinator", "Supervisor", "Site Engineer"):
        permissions += ["manpower.returns"]
```

Accepting a return uses the existing `manpower.coordinate` (HR and Manpower Coordinator).

### Step 4 — Schemas

Open `backend/app/domains/manpower/schemas.py` and add at the end:

```python
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
```

### Step 5 — Business logic

Create a new file `backend/app/domains/manpower/returns.py`:

```python
"""Daily returns: planned work against HR attendance and Construction labour.

A return compares, for one date and shift, each person's confirmed assignment
minutes with the minutes HR attendance recorded and the minutes approved
Construction progress booked. It never edits attendance, assignments, or progress.
"""

from datetime import date

from fastapi import HTTPException

from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import holds
from app.domains.workforce.attendance import _hm, _shift
from app.domains.workforce.deployments import _bump
from app.domains.workforce.models import AttendanceRecord, AttendanceSheet, Personnel, now

from .models import Assignment, DailyReturn, ReturnLine

TOLERANCE = 30
RETURN_NOTE = (
    "A daily return compares confirmed assignments with HR attendance and approved Construction labour for one "
    "date and shift. It does not change attendance, assignments, or progress. Every flagged person needs a "
    "reason before submission, and the person who submits cannot accept."
)


def _planned(db, project, day, shift_id):
    totals = {}
    for row in db.query(Assignment).filter(
        Assignment.project_id == project.id,
        Assignment.work_date == day,
        Assignment.shift_id == shift_id,
        Assignment.state == "Confirmed",
    ):
        totals[row.personnel_id] = totals.get(row.personnel_id, 0) + row.planned_minutes
    return totals


def _attended(db, project, day, shift_id):
    out = {}
    rows = (
        db.query(AttendanceRecord, AttendanceSheet.status)
        .join(AttendanceSheet, AttendanceSheet.id == AttendanceRecord.sheet_id)
        .filter(
            AttendanceRecord.project_id == project.id,
            AttendanceRecord.attendance_date == day,
            AttendanceRecord.shift_id == shift_id,
        )
    )
    for record, sheet_status in rows:
        out[record.personnel_id] = {
            "minutes": record.worked_minutes,
            "status": record.status,
            "approved": sheet_status == "Approved",
        }
    return out


def _attended_day(db, project, day):
    totals = {}
    for row in db.query(AttendanceRecord).filter(
        AttendanceRecord.project_id == project.id, AttendanceRecord.attendance_date == day
    ):
        totals[row.personnel_id] = totals.get(row.personnel_id, 0) + row.worked_minutes
    return totals


def _booked(db, project, day):
    from app.domains.construction.models import ProgressLabour, ProgressReport

    totals = {}
    rows = (
        db.query(ProgressLabour)
        .join(ProgressReport, ProgressReport.id == ProgressLabour.report_id)
        .filter(
            ProgressReport.project_id == project.id,
            ProgressReport.report_date == day,
            ProgressReport.status == "Approved",
        )
    )
    for row in rows:
        totals[row.personnel_id] = totals.get(row.personnel_id, 0) + row.productive_minutes + row.idle_minutes
    return totals


def reconcile(db, project, day, shift):
    """Live lines for every person planned or attended on this date and shift."""
    planned = _planned(db, project, day, shift.id)
    attended = _attended(db, project, day, shift.id)
    booked = _booked(db, project, day)
    day_total = _attended_day(db, project, day)
    ids = set(planned) | set(attended)
    lines = []
    for pid in ids:
        plan = planned.get(pid, 0)
        seen = attended.get(pid)
        worked = seen["minutes"] if seen else 0
        flags = []
        if plan and not seen:
            flags.append("no attendance recorded")
        elif seen and not seen["approved"]:
            flags.append("attendance not approved yet")
        if plan and seen and seen["status"] in ("Absent", "On Leave"):
            flags.append(f"assigned but {seen['status'].lower()}")
        if worked and not plan:
            flags.append("attended without an assignment")
        if plan and worked and abs(worked - plan) > TOLERANCE:
            flags.append(f"attended {_hm(worked)} against {_hm(plan)} planned")
        if booked.get(pid, 0) > day_total.get(pid, 0):
            flags.append(
                f"booked {_hm(booked[pid])} on activities, more than {_hm(day_total.get(pid, 0))} attended that day"
            )
        lines.append(
            {
                "personnel_id": pid,
                "planned_minutes": plan,
                "attended_minutes": worked,
                "booked_minutes": booked.get(pid, 0),
                "attendance": seen["status"] if seen else "",
                "flags": flags,
            }
        )
    return lines


def _stored(db, row):
    return [
        {
            "personnel_id": line.personnel_id,
            "planned_minutes": line.planned_minutes,
            "attended_minutes": line.attended_minutes,
            "booked_minutes": line.booked_minutes,
            "attendance": line.attendance,
            "flags": [text for text in line.flags.split("; ") if text],
            "reason": line.reason,
        }
        for line in db.query(ReturnLine).filter(ReturnLine.return_id == row.id).order_by(ReturnLine.id)
    ]


def _key(lines):
    return sorted(
        (line["personnel_id"], line["planned_minutes"], line["attended_minutes"], line["booked_minutes"])
        for line in lines
    )


def _name(db, user_id):
    user = db.get(User, user_id) if user_id else None
    return user.name if user else ""


def view(db, user, project, names, day, shift_id):
    shift = _shift(db, project, shift_id)
    row = db.query(DailyReturn).filter_by(project_id=project.id, work_date=day, shift_id=shift.id).one_or_none()
    live = reconcile(db, project, day, shift)
    stored = _stored(db, row) if row else []
    frozen = row is not None and row.state in ("Submitted", "Accepted")
    reasons = {line["personnel_id"]: line["reason"] for line in stored}
    lines = stored if frozen else [{**line, "reason": reasons.get(line["personnel_id"], "")} for line in live]
    people = {p.id: p for p in db.query(Personnel).filter(Personnel.id.in_({l["personnel_id"] for l in lines} or {-1}))}
    out = []
    for line in sorted(lines, key=lambda item: people[item["personnel_id"]].code):
        person = people[line["personnel_id"]]
        out.append(
            {
                **line,
                "person": f"{person.code} · {person.full_name}",
                "trade": names["master"].get(person.trade_id, ""),
                "planned": _hm(line["planned_minutes"]),
                "attended": _hm(line["attended_minutes"]),
                "booked": _hm(line["booked_minutes"]),
            }
        )
    return {
        "note": RETURN_NOTE,
        "work_date": day.isoformat(),
        "shift": shift.code,
        "record": (
            {
                "id": row.id,
                "state": row.state,
                "note": row.note,
                "return_reason": row.return_reason,
                "submitted_by": _name(db, row.submitted_by),
                "submitted_at": row.submitted_at.isoformat() if row.submitted_at else "",
                "accepted_by": _name(db, row.accepted_by),
                "version": row.version,
            }
            if row
            else None
        ),
        "lines": out,
        "changed": frozen and _key(live) != _key(stored),
        "flagged": sum(1 for line in out if line["flags"]),
        "can_submit": holds(db, user, project, "manpower.returns"),
        "can_accept": holds(db, user, project, "manpower.coordinate"),
    }


def submit(db, user, project, data):
    shift = _shift(db, project, data.shift_id, on=data.work_date)
    if data.work_date > date.today():
        raise HTTPException(422, "A return can only cover today or an earlier date")
    row = (
        db.query(DailyReturn)
        .filter_by(project_id=project.id, work_date=data.work_date, shift_id=shift.id)
        .with_for_update()
        .one_or_none()
    )
    if row and row.state != "Returned":
        raise HTTPException(409, "This return is already submitted")
    lines = reconcile(db, project, data.work_date, shift)
    if not lines:
        raise HTTPException(422, "Nothing to return: no confirmed assignments or attendance on this shift")
    reasons = {item.personnel_id: item.reason.strip() for item in data.reasons}
    missing = [line["personnel_id"] for line in lines if line["flags"] and len(reasons.get(line["personnel_id"], "")) < 3]
    if missing:
        codes = [p.code for p in db.query(Personnel).filter(Personnel.id.in_(missing)).order_by(Personnel.code)]
        raise HTTPException(422, f"Give a reason for every flagged person: {', '.join(codes)}")
    values = {
        "state": "Submitted",
        "note": data.note.strip(),
        "return_reason": "",
        "submitted_by": user.id,
        "submitted_at": now(),
        "modified_at": now(),
    }
    if row is None:
        row = DailyReturn(
            organization_id=project.organization_id,
            project_id=project.id,
            work_date=data.work_date,
            shift_id=shift.id,
            created_by=user.id,
            **values,
        )
        db.add(row)
        db.flush()
    else:
        if data.version is None:
            raise HTTPException(409, "This record changed. Reload it and try again")
        _bump(db, DailyReturn, row, data.version, values)
        db.query(ReturnLine).filter(ReturnLine.return_id == row.id).delete()
    for line in lines:
        db.add(
            ReturnLine(
                return_id=row.id,
                personnel_id=line["personnel_id"],
                planned_minutes=line["planned_minutes"],
                attended_minutes=line["attended_minutes"],
                booked_minutes=line["booked_minutes"],
                attendance=line["attendance"],
                flags="; ".join(line["flags"]),
                reason=reasons.get(line["personnel_id"], ""),
            )
        )
    db.flush()
    return row


def accept(db, user, project, row, version):
    if row.state != "Submitted":
        raise HTTPException(409, "Only a submitted return can be accepted")
    if row.submitted_by == user.id:
        raise HTTPException(403, "You cannot accept a return you submitted")
    _bump(db, DailyReturn, row, version, {"state": "Accepted", "accepted_by": user.id, "accepted_at": now(), "modified_at": now()})
    return row


def send_back(db, user, project, row, data):
    if row.state != "Submitted":
        raise HTTPException(409, "Only a submitted return can be sent back")
    if row.submitted_by == user.id:
        raise HTTPException(403, "You cannot send back a return you submitted")
    _bump(db, DailyReturn, row, data.version, {"state": "Returned", "return_reason": data.reason.strip(), "modified_at": now()})
    return row
```

### Step 6 — Routes

Open `backend/app/domains/manpower/router.py`.

Change these three import lines:

```python
from . import allocation, availability, returns, service
from .models import Assignment, DailyReturn
from .schemas import AssignmentIn, AssignmentRelease, ReturnBack, ReturnSubmit
```

Add at the end of the file:

```python
@router.get("/projects/{pid}/manpower/returns")
def manpower_return(pid: int, work_date: date, shift_id: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.view")
    return returns.view(db, u, project, _names(db, project), work_date, shift_id)


@router.post("/projects/{pid}/manpower/returns", status_code=201)
def submit_return(pid: int, data: ReturnSubmit, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.returns")
    row = returns.submit(db, u, project, data)
    _audit(
        db, u, "manpower.return.submit", "mp_daily_return", row.id, project.id,
        {"work_date": row.work_date.isoformat(), "shift_id": row.shift_id},
    )
    _commit(db)
    return {"id": row.id, "state": row.state, "version": row.version}


@router.post("/projects/{pid}/manpower/returns/{rid}/accept")
def accept_return(pid: int, rid: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.coordinate")
    row = returns.accept(db, u, project, _owned(db, DailyReturn, project, rid, "Daily return"), data.version)
    _audit(db, u, "manpower.return.accept", "mp_daily_return", row.id, project.id)
    _commit(db)
    return {"id": row.id, "state": row.state, "version": row.version}


@router.post("/projects/{pid}/manpower/returns/{rid}/return")
def send_back_return(pid: int, rid: int, data: ReturnBack, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    project = _project(db, u, pid)
    permitted(db, u, project, "manpower.coordinate")
    row = returns.send_back(db, u, project, _owned(db, DailyReturn, project, rid, "Daily return"), data)
    _audit(db, u, "manpower.return.send_back", "mp_daily_return", row.id, project.id, {"reason": data.reason})
    _commit(db)
    return {"id": row.id, "state": row.state, "version": row.version}
```

### Step 7 — Test

Open `backend/tests/test_manpower.py`.

Change the workforce import line (line 4) to:

```python
from app.domains.workforce.models import AttendanceRecord, AttendanceSheet, Credential, Deployment, Leave, WorkforceRequest
```

Add this test at the end of the file:

```python
def test_daily_returns_reconcile_plan_attendance_and_block_self_accept(env):
    c, maker = env
    sign_in(c)
    roles, _disciplines, me = _ids(c)
    company = me["company_id"]
    today = date.today()
    day = lambda offset: (today + timedelta(days=offset)).isoformat()  # noqa: E731
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    pid = new_project(
        c,
        code="MP-04",
        client_company_id=company,
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    ).json()["id"]
    area = c.post(f"/api/projects/{pid}/areas", json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""}).json()["id"]
    designation = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Designation", "name": "Rigger"}).json()["id"]
    trade = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Trade", "name": "Rigger"}).json()["id"]
    first = c.post(f"/api/projects/{pid}/hr/personnel", json=_person(company, designation, trade, start_date=day(-60))).json()["id"]
    users = {}
    for key, role in (("hr", "HR"), ("pm", "Project Manager"), ("mc", "Manpower Coordinator"), ("sup", "Supervisor"), ("cm", "Commercial Manager")):
        users[key] = _user(c, f"{key}-ret@alpha.test", f"{key.upper()} Ret", company)
        _member(c, pid, users[key], roles[role], company, [])
    _route(c, pid, "hr.deployment", users["pm"])
    package = c.post(f"/api/projects/{pid}/construction/packages", json=_package(area, company, civil, code="WP-R"))
    assert package.status_code == 201, package.text
    activity = c.post(
        f"/api/projects/{pid}/construction/activities",
        json={"package_id": package.json()["id"], "code": "LIFT", "name": "Lift", "quantity": "10", "unit": "nos", "company_id": company, "measurement_method": "Quantity", "predecessor_ids": []},
    ).json()["id"]

    sign_in(c, "hr-ret@alpha.test")
    shift = c.post(f"/api/projects/{pid}/hr/shifts", json={"code": "DAY", "name": "Day", "start_time": "08:00", "end_time": "17:00", "break_minutes": 60, "effective_from": day(-30)}).json()["id"]
    assert c.post(f"/api/projects/{pid}/hr/deployments", json={"personnel_id": first, "planned_start": day(-5), "checks": []}).status_code == 201
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/submit", json={"version": deployment["version"]}).status_code == 200
    sign_in(c, "pm-ret@alpha.test")
    assert _decide(c, c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]["review"]).status_code == 200
    sign_in(c)
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    moved = c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/move", json={"action": "mobilize", "on": day(-3), "version": deployment["version"]})
    assert moved.status_code == 200, moved.text

    # Plan 4 hours and confirm it.
    sign_in(c, "sup-ret@alpha.test")
    made = c.post(f"/api/projects/{pid}/manpower/assignments", json={"activity_id": activity, "work_date": day(0), "shift_id": shift, "personnel_id": first, "planned_minutes": 240})
    assert made.status_code == 201, made.text
    assert c.post(f"/api/projects/{pid}/manpower/assignments/{made.json()['created'][0]}/confirm", json={"version": 1}).status_code == 200

    # HR attendance says 7 hours (inserted directly; the HR attendance flow has its own tests).
    with maker() as db:
        org = db.get(Deployment, deployment["id"]).organization_id
        sheet = AttendanceSheet(organization_id=org, project_id=pid, shift_id=shift, attendance_date=today, status="Approved", created_by=users["hr"])
        db.add(sheet)
        db.flush()
        record = AttendanceRecord(
            sheet_id=sheet.id, project_id=pid, personnel_id=first, deployment_id=deployment["id"], shift_id=shift,
            attendance_date=today, status="Present", worked_minutes=420, regular_minutes=420, created_by=users["hr"],
        )
        db.add(record)
        db.commit()
        record_id = record.id

    url = f"/api/projects/{pid}/manpower/returns"
    view = c.get(f"{url}?work_date={day(0)}&shift_id={shift}").json()
    assert len(view["lines"]) == 1 and "attended 7:00 against 4:00 planned" in view["lines"][0]["flags"]
    assert view["record"] is None and view["can_submit"] is True and view["can_accept"] is False

    body = {"work_date": day(0), "shift_id": shift, "reasons": []}
    sign_in(c, "cm-ret@alpha.test")
    assert c.post(url, json=body).status_code == 403
    sign_in(c, "sup-ret@alpha.test")
    missing = c.post(url, json=body)
    assert missing.status_code == 422 and "Give a reason" in missing.text
    assert c.post(url, json={**body, "work_date": day(1)}).status_code == 422
    body["reasons"] = [{"personnel_id": first, "reason": "Extra lifting after rain delay"}]
    sent = c.post(url, json=body)
    assert sent.status_code == 201, sent.text
    rid = sent.json()["id"]
    assert c.post(url, json=body).status_code == 409
    assert c.post(f"{url}/{rid}/accept", json={"version": 1}).status_code == 403

    # Sent back, resubmitted by the coordinator, who then cannot accept their own return.
    sign_in(c, "mc-ret@alpha.test")
    assert c.post(f"{url}/{rid}/return", json={"reason": "No", "version": 1}).status_code == 422
    back = c.post(f"{url}/{rid}/return", json={"reason": "Check the overtime", "version": 1})
    assert back.status_code == 200 and back.json()["state"] == "Returned"
    again = c.post(url, json={**body, "version": 2})
    assert again.status_code == 201, again.text
    assert c.post(f"{url}/{rid}/accept", json={"version": 3}).status_code == 403
    sign_in(c, "hr-ret@alpha.test")
    accepted = c.post(f"{url}/{rid}/accept", json={"version": 3})
    assert accepted.status_code == 200 and accepted.json()["state"] == "Accepted"
    assert c.post(f"{url}/{rid}/accept", json={"version": 4}).status_code == 409

    # A later attendance change is shown, not written into the accepted return.
    with maker() as db:
        db.get(AttendanceRecord, record_id).worked_minutes = 240
        db.commit()
    view = c.get(f"{url}?work_date={day(0)}&shift_id={shift}").json()
    assert view["record"]["state"] == "Accepted" and view["changed"] is True
    assert view["lines"][0]["attended_minutes"] == 420
```

> Note: `submit` returns 201 even on resubmission because the route has `status_code=201`. That is fine.

### Step 8 — Run the tests

```powershell
docker compose run --rm --build --no-deps backend pytest -q tests/test_manpower.py
```

Expected: `4 passed`. If something fails, read the error from the bottom up. The
first `assert` that failed shows the response text (`made.text` etc.).

Then run everything (about 3 minutes) to make sure nothing else broke:

```powershell
docker compose run --rm --build --no-deps backend pytest -q
```

Expected: `72 passed`.

### Step 9 — Frontend tab

Open `frontend/src/manpower.tsx`.

**9a.** Line 3 — add `ClipboardCheck` to the lucide import (keep alphabetical):

```tsx
import { CalendarCheck, CalendarClock, CalendarRange, ClipboardCheck, ClipboardList, HardHat, IdCard, LayoutDashboard, Pencil, Plus, Search, UserRound, UsersRound } from "lucide-react";
```

**9b.** Lines 9–26 — add `"Daily returns"` to the three lists:

```tsx
const TABS = ["Dashboard", "Workforce demand", "Crews", "Availability", "Allocation", "Daily returns", "HR references"] as const;
```

In `TAB_ICON` add after `Allocation: CalendarCheck,`:

```tsx
  "Daily returns": ClipboardCheck,
```

In `TAB_TONE` add after `Allocation: "tone-malloc",`:

```tsx
  "Daily returns": "tone-mreturn",
```

**9c.** Around line 230, below the Allocation line, add:

```tsx
      {tab === "Daily returns" && board ? <DailyReturns pid={pid} board={board} onError={setError} /> : null}
```

**9d.** Add at the very end of the file:

```tsx
type ReturnLineRow = {
  personnel_id: number;
  person: string;
  trade: string;
  planned: string;
  attended: string;
  booked: string;
  attendance: string;
  flags: string[];
  reason: string;
};
type ReturnView = {
  note: string;
  work_date: string;
  shift: string;
  record: { id: number; state: string; note: string; return_reason: string; submitted_by: string; submitted_at: string; accepted_by: string; version: number } | null;
  lines: ReturnLineRow[];
  changed: boolean;
  flagged: number;
  can_submit: boolean;
  can_accept: boolean;
};

function DailyReturns({ pid, board, onError }: { pid: number; board: Board; onError: (text: string) => void }) {
  const shifts = board.shift_options.filter((item) => item.active);
  const [day, setDay] = useState(board.today);
  const [shiftId, setShiftId] = useState(shifts[0] ? String(shifts[0].id) : "");
  const [data, setData] = useState<ReturnView | null>(null);
  const [reasons, setReasons] = useState<Record<number, string>>({});
  const [note, setNote] = useState("");
  const [back, setBack] = useState("");

  async function load() {
    if (!shiftId) return;
    const view = await api<ReturnView>(`/projects/${pid}/manpower/returns?work_date=${day}&shift_id=${shiftId}`);
    setData(view);
    setReasons(Object.fromEntries(view.lines.map((line) => [line.personnel_id, line.reason])));
    setNote(view.record?.note || "");
  }
  useEffect(() => {
    setData(null);
    load().catch((err) => onError((err as Error).message));
  }, [pid, day, shiftId]);

  async function send(path: string, body: object) {
    onError("");
    try {
      await api(`/projects/${pid}/manpower/returns${path}`, "POST", body);
      setBack("");
      await load();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  const record = data?.record || null;
  const editable = !record || record.state === "Returned";
  const ready = (data?.lines || []).every((line) => !line.flags.length || (reasons[line.personnel_id] || "").trim().length >= 3);

  return (
    <>
      <div className="hr-toolbar">
        <h3 className="section-mark mp-mark">
          <ClipboardCheck size={18} strokeWidth={2.4} /> Daily returns
        </h3>
        <div className="mp-range mp-range-return">
          <label>
            Date
            <input type="date" value={day} max={board.today} onChange={(event) => event.target.value && setDay(event.target.value)} />
          </label>
          <label>
            Shift
            <select value={shiftId} onChange={(event) => setShiftId(event.target.value)}>
              {shifts.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      {!shifts.length ? <p className="muted">No active shift yet. HR adds shifts on the HR screen.</p> : null}
      {data ? <p className="muted">{data.note}</p> : null}
      {record ? (
        <div className={`mp-return-state mp-return-${record.state.toLowerCase()}`}>
          <span className={`mp-pill mp-state-${record.state.toLowerCase()}`}>{record.state}</span>
          <span>
            Submitted by {record.submitted_by}
            {record.accepted_by ? ` · accepted by ${record.accepted_by}` : ""}
          </span>
          {record.return_reason ? <span className="mp-return-why">Sent back: {record.return_reason}</span> : null}
        </div>
      ) : null}
      {data?.changed ? <p className="mp-return-changed">Source records changed since submission. The saved return is shown unchanged.</p> : null}
      {shiftId && !data ? (
        <p className="muted">Loading return…</p>
      ) : data && !data.lines.length ? (
        <p className="muted">Nobody was confirmed or recorded in attendance on this shift.</p>
      ) : data ? (
        <div className="mp-table-wrap">
          <table className="mp-table mp-return-table">
            <thead>
              <tr>
                <th>Person</th>
                <th>Planned</th>
                <th>Attended</th>
                <th>Booked</th>
                <th>Checks</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {data.lines.map((line) => (
                <tr key={line.personnel_id} className={line.flags.length ? "is-flagged" : ""}>
                  <td>
                    {line.person}
                    <small className="muted mp-block">{line.trade}</small>
                  </td>
                  <td>{line.planned} h</td>
                  <td>
                    {line.attended} h<small className="muted mp-block">{line.attendance || "No record"}</small>
                  </td>
                  <td>{line.booked} h</td>
                  <td>
                    {line.flags.length ? (
                      <div className="mp-problems">
                        {line.flags.map((text) => (
                          <span key={text}>{text}</span>
                        ))}
                      </div>
                    ) : (
                      <span className="mp-ok">Matches</span>
                    )}
                  </td>
                  <td>
                    {editable && data.can_submit && line.flags.length ? (
                      <input
                        aria-label={`Reason for ${line.person}`}
                        placeholder="Why it differs"
                        value={reasons[line.personnel_id] || ""}
                        onChange={(event) => setReasons({ ...reasons, [line.personnel_id]: event.target.value })}
                      />
                    ) : (
                      <small>{line.reason || "—"}</small>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {data && data.lines.length && editable && data.can_submit ? (
        <div className="mp-return-actions">
          <input aria-label="Return note" placeholder="Note (optional)" value={note} onChange={(event) => setNote(event.target.value)} />
          <button
            type="button"
            className="primary"
            disabled={!ready}
            onClick={() =>
              void send("", {
                work_date: day,
                shift_id: Number(shiftId),
                note,
                reasons: Object.entries(reasons).map(([id, reason]) => ({ personnel_id: Number(id), reason })),
                version: record ? record.version : null,
              })
            }
          >
            Submit return
          </button>
        </div>
      ) : null}
      {record && record.state === "Submitted" && data?.can_accept ? (
        <div className="mp-return-actions">
          <button type="button" className="primary" onClick={() => void send(`/${record.id}/accept`, { version: record.version })}>
            Accept
          </button>
          <input aria-label="Reason to send back" placeholder="Reason to send back" value={back} onChange={(event) => setBack(event.target.value)} />
          <button type="button" disabled={back.trim().length < 3} onClick={() => void send(`/${record.id}/return`, { reason: back, version: record.version })}>
            Send back
          </button>
        </div>
      ) : null}
    </>
  );
}
```

### Step 10 — Styles

Open `frontend/src/style.css` and paste at the very end (rose colour family, so
it stands apart from the violet Allocation tab):

```css
/* Manpower daily returns */
button.proc-tab.tone-mreturn svg { color: #be123c; background: #ffe4e6; }
button.proc-tab.tone-mreturn.is-on { background: #be123c; }
.mp-range-return label { color: #be123c; }
.mp-range-return input, .mp-range-return select { padding: 5px 8px; border: 1px solid #fecdd3; border-radius: 8px; background: #fff1f2; }
.mp-return-state { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin: 8px 0; padding: 8px 12px; border-radius: 10px; background: #fff1f2; border: 1px solid #fecdd3; font-size: 12.5px; color: #475569; }
.mp-return-accepted { background: #f0fdf4; border-color: #bbf7d0; }
.mp-state-submitted { background: #ffe4e6; color: #9f1239; }
.mp-state-returned { background: #fef3c7; color: #92400e; }
.mp-state-accepted { background: #dcfce7; color: #166534; }
.mp-return-why { color: #92400e; font-weight: 650; }
.mp-return-changed { margin: 6px 0; padding: 8px 12px; border-radius: 10px; background: #fffbeb; border: 1px solid #fde68a; color: #92400e; font-weight: 650; font-size: 12.5px; }
.mp-return-table th { background: linear-gradient(180deg, #ffe4e6, #fff1f2); color: #881337; }
.mp-return-table td { vertical-align: top; }
.mp-return-table tr.is-flagged td:first-child { box-shadow: inset 3px 0 0 #e11d48; }
.mp-return-table input { min-width: 180px; padding: 4px 8px; }
.mp-return-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 12px; }
.mp-return-actions input { flex: 1; min-width: 200px; padding: 6px 10px; }
```

### Step 11 — Deploy

```powershell
# 1. Build and start. The "migrate" container runs your new migration automatically.
docker compose up -d --build backend frontend

# 2. Confirm the migration ran (should print YOUR new id, e.g. a1b2c3d4e5f6)
docker compose exec -T db psql -U siteforge -d siteforge -c "select version_num from alembic_version;"

# 3. Confirm the tables exist
docker compose exec -T db psql -U siteforge -d siteforge -c "\dt mp_*"
```

If the frontend build fails, the error lines contain `TS` codes with a file and
line number. The most common one is "declared but never used" — remove that import.

Then open http://localhost:5173, sign in, click **Manpower** → **Daily returns**.
Check it loads, the date and shift pickers work, and the empty message shows.
Do not submit anything on FLOW-01.

### Step 12 — Update docs

- `docs/implementation_status.md`: add a "Manpower slice 4 is open: …" paragraph after the slice 3 paragraph, and change "Alembic head is `f6a2d8e41c93`" to your new id.
- `docs/next_cursor_prompt.md`: say slice 4 is live and slice 5 is next.
- `docs/connected_execution_workflow.md`: in the "Crew assignment" row, change "daily returns are not built" to "daily returns reconcile planned, attended, and booked hours".

---

## 3. Slice 5 — Utilization, shortfalls and alerts (plan)

Mostly read-only calculations. Usually **no new table**, so **no migration**
unless you add saved alert settings.

**New file** `backend/app/domains/manpower/utilization.py` with:

- `utilization(db, project, names, first, days)` — for each trade and each person:
  - available minutes = days Available (use `availability.Calendar(...).status(pid, day) == "Available"`) × shift capacity (`allocation._capacity(shift)`)
  - planned = confirmed `Assignment.planned_minutes`
  - attended = `AttendanceRecord.worked_minutes`
  - utilization % = attended ÷ available; allocation % = planned ÷ available
- `shortfalls(db, project, first, days)` — for each open demand (`WorkforceRequest.status in REQUEST_ALLOCATING`) and each date it covers: approved headcount minus people with a confirmed assignment against it that day.
- `alerts(db, project)` — return a list of `{"kind", "owner", "since", "detail"}` for:
  - demand short within 3 days of its start
  - confirmed assignment flagged (reuse `allocation.board(...)` problems)
  - daily return not submitted 1 day after the shift
  - returned return not resubmitted
  - person under 50% utilization for 7 days

**Routes** in `router.py` (all `manpower.view`):

- `GET /projects/{pid}/manpower/utilization?start&days` (days 7–28)
- `GET /projects/{pid}/manpower/alerts`

**Test**: create assignments and attendance like the slice 4 test, then assert
the percentages and that each alert kind appears.

**Frontend**: a "Utilization" tab (amber or sky colour): a trade table with
progress bars (`width: ${pct}%`), a shortfall list, and an alerts list with owner
and age. Copy the HR Alerts tab layout from `frontend/src/hr.tsx`.

If you later want alerts to send notifications, use `notify(...)` from
`app.domains.coordination.jobs`. Notifications are sent by the `worker` service,
which stays off, so keep alerts visible on screen only.

## 4. Slice 6 — Productivity and management dashboards (plan)

Read-only. No migration.

**New file** `backend/app/domains/manpower/productivity.py`:

- `productivity(db, project, first, last)` — per activity:
  - quantity done = sum of `ProgressLine.quantity` on approved `ProgressReport`s in the period
  - labour hours = sum of `ProgressLabour.productive_minutes` / 60 on those lines
  - productivity = quantity ÷ labour hours (unit per man-hour); idle % = idle ÷ (productive + idle)
- `summary(db, project)` — headline numbers for the dashboard: headcount deployed, available today, utilization this week, open shortfall, open alerts, returns pending acceptance.

**Routes**: `GET /projects/{pid}/manpower/productivity?start&end` (`manpower.view`).

**Frontend**: add cards to the existing `Dashboard` component in `manpower.tsx`
(it uses `Count` from `./hr`) and a "Productivity" tab with a per-activity table.
Do not show money or cost figures — labour cost needs Financials, which is not built.

---

## 5. Command cheat sheet

| What | Command |
|---|---|
| Manpower tests only | `docker compose run --rm --build --no-deps backend pytest -q tests/test_manpower.py` |
| One test by name | `docker compose run --rm --build --no-deps backend pytest -q tests/test_manpower.py -k daily_returns` |
| All tests | `docker compose run --rm --build --no-deps backend pytest -q` |
| Deploy backend + frontend | `docker compose up -d --build backend frontend` |
| Deploy frontend only | `docker compose up -d --build frontend` |
| Current migration | `docker compose exec -T db psql -U siteforge -d siteforge -c "select version_num from alembic_version;"` |
| Migration log | `docker compose logs migrate --tail 50` |
| Backend errors | `docker compose logs backend --tail 80` |
| Running containers | `docker compose ps` |
| Restart backend only | `docker compose restart backend` |

## 6. Common errors and fixes

| Error | Cause | Fix |
|---|---|---|
| `Multiple head revisions` | Two migrations have the same `down_revision` | Set your new file's `down_revision` to the latest id |
| `Can't locate revision` | Typo in `revision` / `down_revision` | Make sure the id in the file name, `revision`, and the next file's `down_revision` match |
| 422 `Extra inputs are not permitted` | Frontend sends a field the schema doesn't have (`Strict` forbids extras) | Add it to the schema or stop sending it |
| 409 `This record changed` | Wrong `version` sent | Reload, then send the latest `version` |
| 403 in tests | The role lacks the permission | Check `seed.py`; tests run `seed()` fresh each time |
| `TS6133 declared but its value is never read` | Unused import / variable | Remove it |
| `TS2322 Type ... is not assignable` | Type mismatch | Match the type to what the API returns |
| Backend container keeps restarting | Python import or syntax error | `docker compose logs backend --tail 80` and fix the file/line shown |
| Page shows old version | Browser cache | Press Ctrl+F5 |

## 7. Coding style used in this project

- Python: short functions, plain-English error messages, `HTTPException(422, ...)` for invalid input, 409 for wrong state or stale version, 403 for not allowed, 404 for not found.
- Every write route: `_project` → `permitted` → do the work → `_audit` → `_commit`.
- Every state change uses `_bump(...)` so two people can't overwrite each other.
- Comments only when a rule isn't obvious from the code.
- Frontend: one component per tab, `api<Type>(url, method, body)` for calls, errors go to `onError(message)`, empty states tell the user what to set up first.
- Each tab has its own colour family (`tone-*` class) in `style.css`.
