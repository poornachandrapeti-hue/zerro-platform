# Wave 1 change guide — connect the modules that already exist

Four changes, in this order. Each one can be built, tested and deployed on its own.

| # | Change | Migration | Main files |
| --- | --- | --- | --- |
| 1 | Crew check from Manpower on release, start and daily progress | None | `construction/readiness.py`, `construction/progress.py`, `frontend/src/construction.tsx` |
| 2 | One live readiness result per check (Ready / Blocked / Pending / Not Applicable) | `e1a7c3d52f90` | `construction/readiness.py`, `construction/models.py`, `construction/schemas.py`, `frontend/src/construction.tsx` |
| 3 | Drawing supersession or withdrawal opens an impact review on work packages | `e2b8d4f63a01` | new `construction/impact.py`, `engineering_documents/workflow.py`, `construction/progress.py`, `construction/router.py`, `construction/service.py`, `frontend/src/construction.tsx` |
| 4 | Stock reserved for a work package, issue drawn from that reservation, optional issue-before-start | `e3c9e5a74b12` | `supply_chain/models.py`, `supply_chain/schemas.py`, `supply_chain/stock.py`, `construction/readiness.py`, `frontend/src/procurement.tsx` |

All backend paths below are relative to `backend/app/domains/`. Current Alembic head is `d5f9c3a72e08`.

---

## 1. Crew check from Manpower

### Rule

- The check runs only when the package has a **Manpower** readiness row. This keeps existing packages working.
- For each active activity due on the date (date inside `target_start`..`target_finish`, or no target dates), there must be at least one **Confirmed** `mp_assignments` row that still passes `manpower.allocation.check(..., confirm=True)`.
- Date used: release uses `max(today, package.planned_start)`. Start uses today.
- Mandatory Manpower row: Blocked or Pending stops release and start. Advisory: shown as a warning.
- Daily progress: when the Manpower row is Mandatory, a labour entry needs a Confirmed assignment for that person, activity and report date.

### 1a. `construction/readiness.py`

Add near the other constants (after `MATERIAL_CLOSED`):

```python
CREW_PENDING = (
    "No active activity is due on this date. This check stays Pending until an activity is due "
    "and Manpower has confirmed people on it."
)
```

Add after `material_gate`:

```python
def _due(activity, on_date):
    if activity.target_start and on_date < activity.target_start:
        return False
    if activity.target_finish and on_date > activity.target_finish:
        return False
    return True


def crew_date(package, on_date=None):
    from datetime import date

    today = date.today()
    return on_date or max(today, package.planned_start or today)


def crew_gate(db, project, package, on_date=None):
    """Confirmed Manpower assignments on each activity due on the date, rechecked now."""
    from app.domains.manpower.allocation import check
    from app.domains.manpower.models import Assignment
    from app.domains.workforce.models import Personnel, Shift

    on_date = crew_date(package, on_date)
    activities = [
        row
        for row in db.query(ConstructionActivity).filter_by(package_id=package.id, active=True)
        if _due(row, on_date)
    ]
    if not activities:
        return "pending", CREW_PENDING, []
    reasons, notes, sources = [], [], []
    for activity in activities:
        good = 0
        rows = db.query(Assignment).filter_by(
            project_id=project.id, activity_id=activity.id, work_date=on_date, state="Confirmed"
        )
        for row in rows:
            person = db.get(Personnel, row.personnel_id)
            shift = db.get(Shift, row.shift_id)
            problems, _deployment = check(
                db, project, person, activity, shift, on_date, row.planned_minutes, confirm=True, exclude_id=row.id
            )
            if problems:
                notes.append(f"{activity.code}: {person.code} {', '.join(problems)}.")
            else:
                good += 1
        if not good:
            reasons.append(f"{activity.code} has no confirmed, eligible people on {on_date.isoformat()}.")
        sources.append(
            {"activity_id": activity.id, "code": activity.code, "confirmed": good, "date": on_date.isoformat()}
        )
    if reasons:
        return "blocked", " ".join(reasons + notes), sources
    text = f"Every activity due on {on_date.isoformat()} has confirmed, eligible people from Manpower."
    return "ready", " ".join([text] + notes), sources
```

In `_source_label`, before `if check_type == "Predecessor":` add:

```python
    if check_type == "Manpower":
        _state, reason, _sources = crew_gate(db, project, package)
        return reason
```

In `_check_row`, compute the crew result and return it. Add after the Material block:

```python
    live_crew = None
    crew_sources = []
    if row.check_type == "Manpower":
        live_crew, label, crew_sources = crew_gate(db, project, package)
```

and add to the returned dict:

```python
        "live_crew": live_crew,
        "crew_sources": crew_sources,
```

and change the `manual` line to:

```python
        "manual": row.check_type not in {"Drawing", "Material", "Manpower"},
```

Change `_release_problems` to take a date and check crew. New signature and the crew block (put it right after the material block):

```python
def _release_problems(db, project, package, rows, on_date=None):
    ...
    crew_row = next((row for row in rows if row.check_type == "Manpower"), None)
    if crew_row and crew_row.classification == "Mandatory":
        crew_state, crew_reason, _sources = crew_gate(db, project, package, on_date)
        if crew_state != "ready":
            return [crew_reason]
```

The existing loop at the end of `_release_problems` would then also demand `row.status == "Satisfied"` for the Manpower row. Skip the stored status for it, because the live result decides:

```python
    for row in rows:
        ...
        if row.check_type == "Manpower":
            continue
        if row.classification == "Mandatory" and row.status != "Satisfied":
            ...
```

In `update_check`, add a branch next to the Material one:

```python
    elif data.status == "Satisfied" and row.check_type == "Manpower":
        state, reason, _sources = crew_gate(db, project, package)
        if state != "ready":
            raise HTTPException(422, reason)
        row.source_label = reason
```

In `start_work`, recheck with today's date:

```python
    from datetime import date
    ...
    problems = _release_problems(db, project, package, rows, date.today())
```

Add `Advisory` crew warnings in `package_view` (optional but useful): after `"warnings": _warnings(rows),` merge in the crew reason when the Manpower row is Advisory and not ready.

### 1b. `construction/progress.py`

Add a helper after `_started`:

```python
def _assigned(db, project, package, person, activity, on_date, status_code=409):
    from app.domains.manpower.models import Assignment

    from .models import ReadinessCheck

    rule = (
        db.query(ReadinessCheck)
        .filter_by(package_id=package.id, check_type="Manpower", classification="Mandatory")
        .first()
    )
    if not rule:
        return
    found = (
        db.query(Assignment)
        .filter_by(
            project_id=project.id,
            activity_id=activity.id,
            personnel_id=person.id,
            work_date=on_date,
            state="Confirmed",
        )
        .first()
    )
    if not found:
        raise HTTPException(
            status_code,
            f"{person.code} has no confirmed Manpower assignment on {activity.code} for {on_date.isoformat()}",
        )
```

In `add_labour`, after the `assert_eligible(...)` call:

```python
    activity = db.get(ConstructionActivity, line.activity_id)
    _assigned(db, project, db.get(WorkPackage, activity.package_id), person, activity, report.report_date)
```

In `_prepare`, inside the labour loop after `assert_eligible(...)`:

```python
        activity = db.get(ConstructionActivity, line.activity_id)
        _assigned(
            db, project, db.get(WorkPackage, activity.package_id), db.get(Personnel, entry.personnel_id),
            activity, report.report_date, 422,
        )
```

### 1c. `frontend/src/construction.tsx`

- `type CheckRow` (around line 945): add `live_crew: string | null;`.
- In the readiness card (around line 1271), next to the material message:

```tsx
{check.live_crew && check.live_crew !== "ready" ? (
  <p>Manpower has not confirmed eligible people on every activity due, so this check cannot be satisfied.</p>
) : null}
```

- In `CheckActions` (around line 1341) hide Satisfied for crew too:

```tsx
{(check.live_material && check.live_material !== "ready") || (check.live_crew && check.live_crew !== "ready") ? null : (
```

### 1d. Test (`backend/tests/test_construction.py` or `test_manpower.py`)

Reuse the setup from `test_assignments_check_eligibility_booking_and_mobilization` (person, mobilized deployment, shift, activity). Assert:

1. Package with a Mandatory Manpower check and no assignment: release returns 422 with "has no confirmed, eligible people".
2. Propose and confirm an assignment on `planned_start`: release passes this check.
3. Labour on a daily line for a person with no confirmed assignment: 409.
4. Approved leave on the date: start returns 409.

---

## 2. One live readiness result per check

### Rule

Every check row returns `live_state` (Ready, Blocked, Pending, Not Applicable), `live_reason`, `live_owner` and `live_sources`. Live types are read from the owning module. Manual types keep evidence.

| Check type | Source | Owner |
| --- | --- | --- |
| Drawing | `drawing_gate` | Engineering |
| Material | `material_gate` | Stores / Procurement |
| Material issue (added in change 4) | `material_gate(require_issue=True)` | Stores |
| Manpower | `crew_gate` | Manpower |
| Permit | `permit_block`, `field_block`, `hold_block`, plus an Active package permit | HSE |
| Quality hold | `work_blocked`, `release_blocked` | QA/QC |
| Predecessor, Workfront, Procedure, Inspection | stored status and evidence | Check owner |

Not Applicable is allowed only on manual types, with evidence of at least 10 characters, and is recorded with the actor. A live type is never Not Applicable.

### 2a. Migration `backend/migrations/versions/e1a7c3d52f90_readiness_live_statuses.py`

```python
"""Readiness: Not Applicable status and Material issue check type.

Revision ID: e1a7c3d52f90
Revises: d5f9c3a72e08
"""
from alembic import op

revision = "e1a7c3d52f90"
down_revision = "d5f9c3a72e08"
branch_labels = None
depends_on = None

TYPES_OLD = (
    "check_type IN ('Drawing', 'Material', 'Predecessor', 'Workfront', 'Manpower', "
    "'Procedure', 'Inspection', 'Permit', 'Quality hold')"
)
TYPES_NEW = (
    "check_type IN ('Drawing', 'Material', 'Material issue', 'Predecessor', 'Workfront', 'Manpower', "
    "'Procedure', 'Inspection', 'Permit', 'Quality hold')"
)
STATUS_OLD = "status IN ('Not Checked', 'Pending', 'Satisfied', 'Blocked')"
STATUS_NEW = "status IN ('Not Checked', 'Pending', 'Satisfied', 'Blocked', 'Not Applicable')"


def upgrade():
    op.drop_constraint("ck_construction_readiness_type", "construction_readiness", type_="check")
    op.create_check_constraint("ck_construction_readiness_type", "construction_readiness", TYPES_NEW)
    op.drop_constraint("ck_construction_readiness_status", "construction_readiness", type_="check")
    op.create_check_constraint("ck_construction_readiness_status", "construction_readiness", STATUS_NEW)


def downgrade():
    pass
```

Downgrade does nothing on purpose (rows may already use the new values), matching `c4e8a2f61d07`.

### 2b. `construction/models.py` — `ReadinessCheck.__table_args__`

Change the two constraints to the same text as `TYPES_NEW` and `STATUS_NEW` above. The SQLite tests build tables from the models, so the models must match.

### 2c. `construction/schemas.py`

```python
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
```

### 2d. `construction/readiness.py`

Add constants:

```python
LIVE_TYPES = {"Drawing", "Material", "Material issue", "Manpower", "Permit", "Quality hold"}
STATE = {"ready": "Ready", "released": "Ready", "blocked": "Blocked", "pending": "Pending", "missing": "Pending"}
```

Add after `crew_gate`:

```python
def _permit_live(db, package):
    from app.domains.hse.field import field_block
    from app.domains.hse.holds import hold_block
    from app.domains.hse.models import HsePermit
    from app.domains.hse.permits import permit_block, refresh_permit

    for message in (permit_block(db, package), field_block(db, package), hold_block(db, package)):
        if message:
            return "Blocked", message
    active = []
    for row in db.query(HsePermit).filter_by(project_id=package.project_id, package_id=package.id, activity_id=None):
        refresh_permit(db, row)
        if row.status == "Active":
            active.append(row.number)
    if active:
        return "Ready", f"Active permit {', '.join(active)} covers this package. Field rules and safety holds were checked now."
    return "Pending", "No active permit covers the whole package. An activity permit does not cover the rest of the package."


def _quality_live(db, package):
    from app.domains.quality.findings import release_blocked, work_blocked

    hold = work_blocked(db, package, None) or release_blocked(db, package)
    if hold:
        return "Blocked", f"Quality hold {hold.number} blocks this work."
    return "Ready", "No open quality hold blocks release or work on this package."


def live_result(db, project, package, row, on_date=None):
    sources = []
    if row.check_type == "Drawing":
        state, labels = drawing_gate(db, project, package)
        reason = _source_label(db, project, package, "Drawing")
        return {"state": STATE[state], "reason": reason, "owner": "Engineering", "sources": labels}
    if row.check_type in {"Material", "Material issue"}:
        state, reason, sources = material_gate(db, project, package, require_issue=row.check_type == "Material issue")
        return {"state": STATE[state], "reason": reason, "owner": "Stores / Procurement", "sources": sources}
    if row.check_type == "Manpower":
        state, reason, sources = crew_gate(db, project, package, on_date)
        return {"state": STATE[state], "reason": reason, "owner": "Manpower", "sources": sources}
    if row.check_type == "Permit":
        state, reason = _permit_live(db, package)
        return {"state": state, "reason": reason, "owner": "HSE", "sources": []}
    if row.check_type == "Quality hold":
        state, reason = _quality_live(db, package)
        return {"state": state, "reason": reason, "owner": "QA/QC", "sources": []}
    owner = db.get(User, row.owner_user_id) if row.owner_user_id else None
    manual = {"Satisfied": "Ready", "Blocked": "Blocked", "Not Applicable": "Not Applicable"}
    return {
        "state": manual.get(row.status, "Pending"),
        "reason": row.evidence or MANUAL,
        "owner": owner.name if owner else "Check owner",
        "sources": [],
    }
```

(`require_issue` is added to `material_gate` in change 4. If you deploy change 2 before change 4, call `material_gate(db, project, package)` and leave out `Material issue`.)

In `_check_row`, add to the returned dict (keep the old `live_drawing` / `live_material` / `live_crew` keys so the current UI keeps working):

```python
    live_row = live_result(db, project, package, row)
    ...
        "live_state": live_row["state"],
        "live_reason": live_row["reason"],
        "live_owner": live_row["owner"],
        "live_sources": live_row["sources"],
        "manual": row.check_type not in LIVE_TYPES,
```

Replace the end of `_release_problems` (the final `for row in rows:` loop) with:

```python
    for row in rows:
        if row.classification != "Mandatory":
            continue
        if row.check_type in LIVE_TYPES:
            result = live_result(db, project, package, row, on_date)
            if result["state"] != "Ready":
                return [f"{row.check_type}: {result['reason']}"]
        elif row.status not in {"Satisfied", "Not Applicable"}:
            return [f"{row.check_type} is mandatory and is not satisfied"]
    return []
```

Keep the earlier drawing and material blocks in `_release_problems`: they block even when no check row exists. The crew block from change 1 is now covered by the loop and can be removed.

Update `_warnings` so Advisory live rows use the live state:

```python
def _warnings(rows, db=None, project=None, package=None):
    out = []
    for row in rows:
        if row.classification != "Advisory":
            continue
        if db is not None and row.check_type in LIVE_TYPES:
            result = live_result(db, project, package, row)
            if result["state"] != "Ready":
                out.append(f"{row.check_type} is {result['state']}: {result['reason']}")
        elif row.status not in {"Satisfied", "Not Applicable"}:
            out.append(f"{row.check_type} is {row.status}")
    return out
```

and pass `db, project, package` at the three call sites (`package_view`, `submit_release`, `apply_resubmit`).

In `update_check`:

- Before the Satisfied branches, refuse Satisfied on a live type that is not Ready (this replaces the per-type Material, Drawing and Manpower branches):

```python
    if data.status == "Satisfied" and row.check_type in LIVE_TYPES:
        result = live_result(db, project, package, row)
        if result["state"] != "Ready":
            raise HTTPException(422, result["reason"])
        row.source_label = result["reason"]
    elif data.status == "Not Applicable":
        if row.check_type in LIVE_TYPES:
            raise HTTPException(422, "A check read from its owning module cannot be marked Not Applicable")
        if len(evidence) < 10:
            raise HTTPException(422, "Record who decided this check does not apply, and why")
    elif data.status == "Satisfied":
        ...  # existing manual evidence branch
```

- Change `verified = data.status in {"Satisfied", "Blocked"}` to include `"Not Applicable"`.

Store the live results in the release snapshot: in `_snapshot`, add `"live": live_result(db, project, package, row)` to each item in `"checks"`.

### 2e. `frontend/src/construction.tsx`

- Line ~933 `CHECK_TYPES`: add `"Material issue"` after `"Material"`.
- `type CheckRow`: add

```ts
  live_state: "Ready" | "Blocked" | "Pending" | "Not Applicable";
  live_reason: string;
  live_owner: string;
```

- `checkClass`: add `if (status === "Not Applicable") return "chk-ok";`.
- In the readiness card, replace the separate `live_drawing` / `live_material` / `live_crew` messages with one line:

```tsx
<p>
  <strong>{check.live_state}</strong> · {check.live_owner} — {check.live_reason}
</p>
```

- In `CheckActions`: show Satisfied only when `check.manual || check.live_state === "Ready"`. Add a Not Applicable button only when `check.manual`:

```tsx
{check.manual ? (
  <button type="button" onClick={() => onSet("Not Applicable", evidence)}>Not applicable</button>
) : null}
```

### 2f. Tests

- A Mandatory Permit row with no Active permit: release returns 422 "Permit: No active permit covers the whole package".
- A Mandatory Quality hold row with an open package hold: release returns 422.
- Not Applicable on a Permit row: 422. On a Workfront row with 10+ characters of evidence: 200, and release no longer reports Workfront.
- Update `test_release_follows_saved_reviewer_and_readiness` if it marks Permit or Quality hold Satisfied by typed evidence; those now need the real record.

---

## 3. Drawing impact review on work packages

### Rule

- When a revision linked to a live package (Draft, Ready, In Progress, On Hold) is superseded or withdrawn, the package gets `impact_state = "Review required"`.
- Links come from `work_package_drawings.revision_id` and from `construction_activities.drawing_revision_id`.
- The responsible engineer and the supervisor get a High task and an in-app notification.
- Daily progress stays closed on that package until the responsible engineer resolves it.
- Resolve with **relink** (choose the released revision of the same drawing; package and activity links move to it) or **accept** (reason required; links stay). Accept does not unblock release or start of a Draft/Ready package, because the drawing gate still sees an unreleased revision.
- No drawing is switched silently.

### 3a. Migration `backend/migrations/versions/e2b8d4f63a01_package_drawing_impact.py`

```python
"""Work package drawing impact review.

Revision ID: e2b8d4f63a01
Revises: e1a7c3d52f90
"""
from alembic import op
import sqlalchemy as sa

revision = "e2b8d4f63a01"
down_revision = "e1a7c3d52f90"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("work_packages", sa.Column("impact_state", sa.String(30), nullable=False, server_default=""))
    op.add_column("work_packages", sa.Column("impact_detail", sa.Text(), nullable=False, server_default=""))
    op.add_column(
        "work_packages",
        sa.Column("impact_revision_id", sa.Integer(), sa.ForeignKey("drawing_revisions.id"), nullable=True),
    )


def downgrade():
    op.drop_column("work_packages", "impact_revision_id")
    op.drop_column("work_packages", "impact_detail")
    op.drop_column("work_packages", "impact_state")
```

### 3b. `construction/models.py` — `WorkPackage`

Add after `cancellation_reason`:

```python
    impact_state: Mapped[str] = mapped_column(String(30), default="")
    impact_detail: Mapped[str] = mapped_column(Text, default="")
    impact_revision_id: Mapped[int | None] = mapped_column(ForeignKey("drawing_revisions.id"), nullable=True)
```

### 3c. New file `construction/impact.py`

```python
"""Drawing supersession and withdrawal on work packages.

A newer release does not switch a package to it. The package is flagged, its
owners get a task, and the responsible engineer relinks or accepts with a reason.
"""

from fastapi import HTTPException

from app.domains.coordination.jobs import notify
from app.domains.coordination.service import _close_tasks, _task
from app.domains.engineering_documents.models import Drawing, DrawingRevision
from app.domains.identity_projects.models import Project, User

from .models import ConstructionActivity, WorkPackage, WorkPackageDrawing, now

IMPACT = "construction.drawing_impact"
LIVE = ("Draft", "Ready", "In Progress", "On Hold")
OPEN = "Review required"


def _packages(db, revision):
    ids = {row.package_id for row in db.query(WorkPackageDrawing).filter_by(revision_id=revision.id)}
    ids |= {row.package_id for row in db.query(ConstructionActivity).filter_by(drawing_revision_id=revision.id)}
    if not ids:
        return []
    return db.query(WorkPackage).filter(WorkPackage.id.in_(ids), WorkPackage.status.in_(LIVE)).all()


def flag_revision(db, user, revision, detail):
    drawing = db.get(Drawing, revision.drawing_id)
    project = db.get(Project, drawing.project_id) if drawing else None
    if not project:
        return
    for package in _packages(db, revision):
        if package.impact_state == OPEN and package.impact_revision_id == revision.id:
            continue
        package.impact_state = OPEN
        package.impact_detail = detail
        package.impact_revision_id = revision.id
        package.version += 1
        package.modified_by = user.id
        package.modified_at = now()
        for owner_id in {package.responsible_user_id, package.supervisor_user_id} - {None}:
            person = db.get(User, owner_id)
            if not person or not person.active:
                continue
            _task(db, user, project, owner_id, f"Review drawing impact on {package.code}", IMPACT, package.id, priority="High")
            notify(
                db,
                person,
                "Drawing impact on work package",
                f"{package.code}: {detail}",
                f"package-impact:{package.id}:{revision.id}:{revision.release_state}:{owner_id}",
                project_id=project.id,
                link=f"/projects/{project.id}",
            )


def choices(db, package):
    if package.impact_state != OPEN or not package.impact_revision_id:
        return []
    old = db.get(DrawingRevision, package.impact_revision_id)
    rows = db.query(DrawingRevision).filter_by(drawing_id=old.drawing_id, release_state="Released").all()
    return [{"id": row.id, "code": row.code} for row in rows]


def resolve(db, user, project, package, data):
    from .readiness import _bump

    if package.impact_state != OPEN:
        raise HTTPException(409, "This work package has no open drawing impact")
    if user.id != package.responsible_user_id:
        raise HTTPException(403, "Only the responsible engineer resolves a drawing impact")
    reason = data.reason.strip()
    old = db.get(DrawingRevision, package.impact_revision_id)
    new = None
    if data.action == "relink":
        new = db.get(DrawingRevision, data.revision_id) if data.revision_id else None
        if not new or new.drawing_id != old.drawing_id or new.release_state != "Released":
            raise HTTPException(422, "Choose the released revision of the same drawing")
    elif len(reason) < 10:
        raise HTTPException(422, "Record why the work is not affected")
    note = f"Relinked to rev {new.code}. {reason}".strip() if new else f"Accepted without change: {reason}"
    _bump(db, package, data.version, {"impact_state": "Reviewed", "impact_detail": note, "modified_by": user.id})
    if new:
        link = db.query(WorkPackageDrawing).filter_by(package_id=package.id, revision_id=old.id).first()
        if link:
            if db.query(WorkPackageDrawing).filter_by(package_id=package.id, revision_id=new.id).first():
                db.delete(link)
            else:
                link.revision_id = new.id
        for activity in db.query(ConstructionActivity).filter_by(package_id=package.id, drawing_revision_id=old.id):
            activity.drawing_revision_id = new.id
            activity.version += 1
    _close_tasks(db, project.id, IMPACT, package.id, "Completed", note)
    db.flush()
    return package
```

### 3d. `engineering_documents/workflow.py`

Add next to `_procurement_impact` (around line 571):

```python
def _construction_impact(db, user, revision, detail):
    from app.domains.construction.impact import flag_revision as flag_packages

    flag_packages(db, user, revision, detail)
```

Call it right after each `_procurement_impact(...)` call:

- `release_revision`, inside the supersede loop (line ~551):
  `_construction_impact(db, user, previous, f"Drawing {drawing.number} rev {previous.code} was superseded by {revision.code}")`
- `withdraw_revision` (line ~568):
  `_construction_impact(db, user, revision, f"Drawing {drawing.number} rev {revision.code} was withdrawn: {reason}")`

### 3e. `construction/progress.py` — `_started`

Add at the top of `_started`:

```python
    if package.impact_state == "Review required":
        raise HTTPException(
            422,
            f"A drawing impact review is open on {package.code}. {package.impact_detail} "
            "The responsible engineer relinks or accepts it before more progress is recorded.",
        )
```

### 3f. `construction/service.py` — `_package_row`

Add to the returned dict:

```python
        "impact_state": package.impact_state,
        "impact_detail": package.impact_detail,
        "impact_revision_id": package.impact_revision_id,
```

In `construction/readiness.py` → `package_view`, add `"impact_choices": impact.choices(db, package),` (import `from . import impact` inside the function to avoid a cycle).

### 3g. `construction/schemas.py`

```python
class ImpactIn(Strict):
    version: int = Field(ge=1)
    action: Literal["relink", "accept"]
    revision_id: int | None = None
    reason: str = Field(default="", max_length=2000)
```

### 3h. `construction/router.py`

Import `impact` alongside the other modules and `ImpactIn` from schemas, then add after `start_package`:

```python
@router.post("/projects/{pid}/construction/packages/{package_id}/drawing-impact")
def resolve_drawing_impact(
    pid: int,
    package_id: int,
    data: ImpactIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _edit(db, u, found)
    package = _package(db, pid, package_id)
    impact.resolve(db, u, found, package, data)
    _audit(db, u, "drawing_impact", "work_packages", package.id, pid, {"action": data.action})
    _commit(db)
    return readiness.package_view(db, u, found, package)
```

### 3i. `frontend/src/construction.tsx`

- `type Package`: add `impact_state: string; impact_detail: string; impact_revision_id: number | null;`.
- `type ReleaseCard`: add `impact_choices: { id: number; code: string }[];`.
- In the release card (after the `<h4>` around line 1257), when `card.package.impact_state === "Review required"`, render a `note-card note-alert` with `impact_detail`, a select of `card.impact_choices`, a reason input and two buttons that call:

```ts
await api(`/projects/${pid}/construction/packages/${card.package.id}/drawing-impact`, "POST", {
  version: card.package.version,
  action, // "relink" or "accept"
  revision_id: action === "relink" ? Number(revisionId) : null,
  reason,
});
```

Show the same banner on the package list and daily progress screens so site staff see why progress is closed.

### 3j. Tests

Extend `test_drawing_review_release_and_supersession` or add a new test:

1. Link rev B to a package and start it. Release rev C. The package is `Review required`, the engineer has a task and a notification, and a daily line returns 422.
2. A user who is not the responsible engineer resolving: 403.
3. Relink to C: links move, task closed, daily progress opens again.
4. Withdraw a linked revision: the package is flagged again.

---

## 4. Package-owned reservations and issue-before-start

### Rule

- A reservation can name a work package (`stock_postings.package_id`).
- An issue can draw from a reservation (`reservation_id`). It reduces both on-hand and reserved, and each issue line points to its reservation line through the existing `stock_posting_lines.source_line_id`.
- Today an issue can only use *unreserved* stock (`quantity > on_hand - reserved` is refused), so reserved stock can never be issued without cancelling the reservation first. This change fixes that.
- `material_gate` counts only stock reserved or issued **for this package**, with required quantities added up per item.
- A new **Material issue** check (from change 2) requires the quantity to be issued, not just reserved, before start.
- **Behavior change:** existing project-level reservations no longer satisfy a package. Re-post them against the package (cancel, then reserve again with the package chosen) before deploying.

### 4a. Migration `backend/migrations/versions/e3c9e5a74b12_package_reservations.py`

```python
"""Stock reservations and issues for a work package.

Revision ID: e3c9e5a74b12
Revises: e2b8d4f63a01
"""
from alembic import op
import sqlalchemy as sa

revision = "e3c9e5a74b12"
down_revision = "e2b8d4f63a01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "stock_postings",
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=True),
    )
    op.create_index("ix_stock_postings_package_id", "stock_postings", ["package_id"])


def downgrade():
    op.drop_index("ix_stock_postings_package_id", table_name="stock_postings")
    op.drop_column("stock_postings", "package_id")
```

### 4b. `supply_chain/models.py` — `StockPosting`

Add after `source_posting_id`:

```python
    package_id: Mapped[int | None] = mapped_column(ForeignKey("work_packages.id"), nullable=True, index=True)
```

### 4c. `supply_chain/schemas.py`

```python
class ReservationIn(Strict):
    number: str = Field(min_length=1, max_length=80)
    warehouse_id: int
    reason: str = Field(min_length=1, max_length=2000)
    lines: list[ItemQtyIn] = Field(min_length=1)
    package_id: int | None = None


class IssueIn(ReservationIn):
    recipient: str = Field(min_length=1, max_length=200)
    reservation_id: int | None = None
```

### 4d. `supply_chain/stock.py`

Add after `returned_qty`:

```python
def _issue_lines(db, reservation_line_id):
    out = []
    for line in db.query(StockPostingLine).filter_by(source_line_id=reservation_line_id):
        posting = db.get(StockPosting, line.posting_id)
        if posting and posting.status == "Posted" and posting.kind == "Issue":
            out.append(line)
    return out


def drawn_qty(db, reservation_line_id):
    return sum((_amount(line.quantity) for line in _issue_lines(db, reservation_line_id)), Decimal("0"))


def package_stock(db, project_id, package_id, item_id):
    """Still reserved for the package, and issued from its reservations net of returns."""
    reserved = Decimal("0")
    issued = Decimal("0")
    lines = (
        db.query(StockPostingLine)
        .join(StockPosting, StockPosting.id == StockPostingLine.posting_id)
        .filter(
            StockPosting.project_id == project_id,
            StockPosting.package_id == package_id,
            StockPosting.kind == "Reservation",
            StockPosting.status == "Posted",
            StockPostingLine.item_id == item_id,
        )
    )
    for line in lines:
        drawn = _issue_lines(db, line.id)
        reserved += _amount(line.quantity) - sum((_amount(row.quantity) for row in drawn), Decimal("0"))
        for row in drawn:
            issued += _amount(row.quantity) - returned_qty(db, row.id)
    return reserved, issued


def _open_package(db, project, package_id):
    if package_id is None:
        return None
    from app.domains.construction.models import WorkPackage

    package = db.get(WorkPackage, package_id)
    if not package or package.project_id != project.id or package.status in {"Cancelled", "Handed Over"}:
        raise HTTPException(422, "Choose an open work package on this project")
    return package
```

`reserve_stock` — validate the package and store it:

```python
def reserve_stock(db, user, project, data):
    _stores(db, user, project)
    _warehouse(db, project, data.warehouse_id)
    package = _open_package(db, project, data.package_id)
    ...
    posting = _save(db, user, project, "Reservation", data.number, data.warehouse_id, data.reason, "", None, None)
    posting.package_id = package.id if package else None
    ...
```

`issue_stock` — draw from a reservation when one is named:

```python
def issue_stock(db, user, project, data):
    _stores(db, user, project)
    _warehouse(db, project, data.warehouse_id)
    reservation = None
    if data.reservation_id is not None:
        reservation = db.get(StockPosting, data.reservation_id)
        if (
            not reservation
            or reservation.project_id != project.id
            or reservation.kind != "Reservation"
            or reservation.status != "Posted"
            or reservation.warehouse_id != data.warehouse_id
        ):
            raise HTTPException(422, "Choose a posted reservation in this warehouse")
    ...  # existing item loop and quality-hold check unchanged
    posting = _save(
        db, user, project, "Issue", data.number, data.warehouse_id, data.reason, data.recipient,
        None, reservation.id if reservation else None,
    )
    posting.package_id = reservation.package_id if reservation else None
    for item, quantity in sorted(chosen, key=lambda item: item[0].id):
        balance = _lock_balance(db, user, project, data.warehouse_id, item.id, "")
        source = None
        if reservation:
            source = db.query(StockPostingLine).filter_by(posting_id=reservation.id, item_id=item.id).first()
            if not source:
                raise HTTPException(422, f"{item.code} is not on reservation {reservation.number}")
            if quantity > _amount(source.quantity) - drawn_qty(db, source.id):
                raise HTTPException(422, "Issued quantity cannot exceed what is still reserved")
            balance.reserved = _amount(balance.reserved) - quantity
        elif quantity > _available(balance):
            raise HTTPException(422, "Issued quantity cannot exceed the available quantity")
        balance.on_hand = _amount(balance.on_hand) - quantity
        balance.version += 1
        db.add(
            StockPostingLine(
                posting_id=posting.id,
                item_id=item.id,
                source_line_id=source.id if source else None,
                quantity=quantity,
                unit=balance.unit,
            )
        )
    ...
```

`cancel_posting` — keep reserved balances right:

- Before the line loop:

```python
    if row.kind == "Reservation" and any(drawn_qty(db, line.id) > 0 for line in lines):
        raise HTTPException(409, "Cancel the issues drawn from this reservation first")
```

- In the `Issue` branch:

```python
        elif row.kind == "Issue":
            balance.on_hand = _amount(balance.on_hand) + quantity
            if line.source_line_id:
                balance.reserved = _amount(balance.reserved) + quantity
```

`payload` — add:

```python
        "package_id": row.package_id,
        "package_code": package.code if package else "",
```

with `package = db.get(WorkPackage, row.package_id) if row.package_id else None` (import `WorkPackage` inside the function).

### 4e. `construction/readiness.py` — `material_gate`

Change the signature to `def material_gate(db, project, package, require_issue=False):` and import `package_stock` instead of (or as well as) `item_stock`:

```python
from app.domains.supply_chain.stock import item_stock, package_stock
```

Add `needed = {}` before `for link in links:`. Replace the per-line calculation (from `required = ...` to the end of the `else:` note) with:

```python
            needed[line.item_id] = needed.get(line.item_id, Decimal("0")) + _amount(line.quantity)
            required = needed[line.item_id]
            reserved, issued = package_stock(db, project.id, package.id, line.item_id)
            covered = reserved + issued
            hold = issue_blocked(db, project.id, line.item_id)
            if hold:
                note = f"{code} on {requirement.number} is under quality hold {hold.number}."
            elif covered < required:
                note = (
                    f"{code} on {requirement.number} needs {qty(required)} {line.unit} for {package.code}. "
                    f"Stores has {qty(reserved)} reserved and {qty(issued)} issued for this package."
                )
            elif require_issue and issued < required:
                note = (
                    f"{code} on {requirement.number} needs {qty(required)} {line.unit} issued before start. "
                    f"Stores has issued {qty(issued)} for {package.code}."
                )
            else:
                note = (
                    f"{code} on {requirement.number} has {qty(required)} {line.unit} "
                    f"{'issued' if require_issue else 'reserved or issued'} for {package.code}."
                )
            short = covered < required or (require_issue and issued < required)
            if hold or short:
                ready = False
                reasons.append(note)
```

Add `from decimal import Decimal` at the top of the file. Update the `sources.append` dict to report `reserved` and `issued` instead of `on_hand`.

### 4f. `frontend/src/procurement.tsx` — Stock panel (around line 2740)

- Load open packages for the selector: `api<{ id: number; code: string; status: string }[]>(\`/projects/${pid}/construction/packages\`)`. Only call it when the user has `construction.view`, or catch a 403 and leave the list empty.
- Reserve form: add a "Work package (optional)" select and send `package_id: packageId ? Number(packageId) : null`.
- Issue form: add a "From reservation (optional)" select listing `postings.filter(p => p.kind === "Reservation" && p.status === "Posted")`, and send `reservation_id`. When a reservation is chosen, list only its items.
- Postings table: show `package_code` in a new column.
- Change the note text: "Reserve holds available quantity, optionally for a work package. An issue can draw from a reservation."

### 4g. Tests

- Update `test_material_readiness_reads_accepted_reserved_stock`: post the reservation with `package_id`. A project-level reservation without a package must leave the check blocked.
- Issue from a reservation: reserved and on-hand both go down. Issuing more than is still reserved: 422.
- Cancelling a reservation that has an issue drawn from it: 409. Cancelling that issue puts the quantity back into reserved.
- Material issue check (Mandatory): reserved but not issued blocks start. After the issue it passes.
- Two requirement lines for the same item: the gate needs the sum.

---

## Docs to update in the same change

The project rule ("Rule for the next module" in `docs/connected_execution_workflow.md`) asks for these with every new link or gate:

- `docs/connected_execution_workflow.md`: change "Eligible crew" from Missing to Partial (Manpower confirmed assignments; command: release, start, labour; test name). Released drawing: impact review now opened. Material readiness: package-owned reservation and optional issue. Section 2: the four target statuses now exist.
- `requirements/00_coverage_tracker.md`: same rows in the connected-step table.
- `docs/implementation_status.md`: one paragraph per change and the new Alembic head `e3c9e5a74b12`.

## Build, test, deploy

From `siteforge/`:

```bash
# back up first
docker compose exec db pg_dump -U siteforge siteforge > backup_before_wave1.sql

# tests (SQLite, builds tables from the models)
docker compose run --rm --build --no-deps backend pytest -q

# frontend type check and build
cd frontend && npm ci && npm run typecheck && npm run build && cd ..

# deploy: the migrate service runs alembic upgrade head before the backend starts
docker compose up --build -d
docker compose logs migrate backend
docker compose run --rm migrate alembic current   # expect e3c9e5a74b12
docker compose run --rm migrate alembic check
```

Do not use `docker compose down -v`. It deletes the database volume.

## Manual checks after deploy

1. Package with a Mandatory Manpower check: release is refused until Manpower confirms people on `planned_start`. Daily labour for an unassigned person is refused.
2. Readiness card shows Ready / Blocked / Pending / Not Applicable with the owner and reason for every row.
3. Release a newer revision of a drawing linked to an In Progress package: the engineer gets a task, daily progress is closed, relink reopens it.
4. Reserve stock for the package, issue from that reservation, and watch the Material and Material issue checks turn Ready.
