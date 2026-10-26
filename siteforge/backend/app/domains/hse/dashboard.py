"""Safety dashboard.

Counts come from records already stored. A filter keeps a record only when
that record carries the chosen company, discipline, location, package,
severity, owner, or date. The incident rate stays N/A.
"""

from datetime import date, datetime

from fastapi import HTTPException

from app.domains.construction.models import WorkPackage

from .field import field_block
from .holds import BLOCKING, hold_block
from .incidents import RATE_NOTE
from .models import (
    HseAction,
    HseDrill,
    HseEnvironmentRecord,
    HseFinding,
    HseHold,
    HseIncident,
    HseIncidentCategory,
    HseInspection,
    HseObservation,
    HsePermit,
    now,
)
from .permits import permit_block, refresh_permit

DASHBOARD_NOTE = (
    "These counts use records already stored. A filter hides a record that does not carry "
    "the chosen company, discipline, location, package, severity, owner, or date. "
    "The incident rate stays N/A until an approved definition and exposure hours exist."
)
OBSERVATION_COUNT_NOTE = (
    "This counts reported unsafe conditions and unsafe acts. A positive observation is not included. "
    "Severity is not invented here."
)
DATE_KINDS = ("recorded", "due", "planned", "expiry")
OPEN_ACTION = {"Open", "In Progress", "Pending Verification"}
INCIDENT_SKIP = {"Cancelled", "Rejected"}
CRITICAL_OBSERVATIONS = {"Unsafe Condition", "Unsafe Act"}


def _today():
    return now().date()


def _on(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def _key(value):
    return (value or "").strip().casefold()


def _filters(data):
    kind = (data.get("date_kind") or "").strip()
    start = data.get("date_from")
    end = data.get("date_to")
    if kind and kind not in DATE_KINDS:
        raise HTTPException(422, "Choose a date type")
    if (start or end) and not kind:
        raise HTTPException(422, "Choose which date the range uses")
    if start and end and end < start:
        raise HTTPException(422, "The end date is before the start date")
    return {
        "company_id": data.get("company_id"),
        "discipline_id": data.get("discipline_id"),
        "area_id": data.get("area_id"),
        "package_id": data.get("package_id"),
        "owner_id": data.get("owner_id"),
        "severity": (data.get("severity") or "").strip(),
        "date_kind": kind,
        "date_from": start,
        "date_to": end,
    }


def _match(filters, **dims):
    for key in ("company_id", "discipline_id", "area_id", "package_id", "owner_id"):
        wanted = filters[key]
        if wanted is None:
            continue
        if dims.get(key) != wanted:
            return False
    if filters["severity"] and _key(dims.get("severity")) != _key(filters["severity"]):
        return False
    kind = filters["date_kind"]
    if kind:
        value = _on(dims.get(kind))
        if not isinstance(value, date):
            return False
        if filters["date_from"] and value < filters["date_from"]:
            return False
        if filters["date_to"] and value > filters["date_to"]:
            return False
    return True


def _package_dims(db, package_id, **dims):
    if package_id and "package_id" not in dims:
        dims["package_id"] = package_id
    package = db.get(WorkPackage, dims.get("package_id")) if dims.get("package_id") else None
    if not package:
        return dims
    dims.setdefault("company_id", package.company_id)
    dims.setdefault("discipline_id", package.discipline_id)
    dims.setdefault("area_id", package.area_id)
    return dims


def view(db, project, data=None):
    filters = _filters(data or {})
    today = _today()
    permits = {"active": 0, "pending": 0, "expired": 0, "suspended": 0}
    for row in db.query(HsePermit).filter_by(project_id=project.id):
        refresh_permit(db, row)
        if not _match(
            filters,
            company_id=row.company_id,
            discipline_id=row.discipline_id,
            area_id=row.area_id,
            package_id=row.package_id,
            owner_id=row.applicant_id,
            recorded=_on(row.valid_from),
            expiry=_on(row.valid_until),
        ):
            continue
        if row.status == "Active":
            permits["active"] += 1
        elif row.status == "Pending Review":
            permits["pending"] += 1
        elif row.status == "Expired":
            permits["expired"] += 1
        elif row.status == "Suspended":
            permits["suspended"] += 1

    blocked = []
    for package in db.query(WorkPackage).filter_by(project_id=project.id):
        if package.status == "Cancelled":
            continue
        if not _match(
            filters,
            company_id=package.company_id,
            discipline_id=package.discipline_id,
            area_id=package.area_id,
            package_id=package.id,
            owner_id=package.responsible_user_id,
            planned=package.planned_start,
        ):
            continue
        reason = permit_block(db, package) or field_block(db, package) or hold_block(db, package)
        if reason:
            blocked.append({"code": package.code, "reason": reason})

    observations = 0
    issues = []
    for row in db.query(HseObservation).filter_by(project_id=project.id, status="Reported"):
        dims = _package_dims(db, row.package_id, area_id=row.area_id, owner_id=row.reporter_id, recorded=_on(row.created_at))
        if not _match(filters, **dims):
            continue
        if row.observation_type in CRITICAL_OBSERVATIONS:
            observations += 1
        if row.observation_type == "Environmental Concern":
            issues.append({"number": row.number, "detail": row.observation_type})

    categories = []
    for category in db.query(HseIncidentCategory).filter_by(project_id=project.id).order_by(HseIncidentCategory.name):
        count = 0
        for row in db.query(HseIncident).filter_by(project_id=project.id, category_id=category.id):
            if row.status in INCIDENT_SKIP:
                continue
            if _match(
                filters,
                company_id=row.company_id,
                area_id=row.area_id,
                package_id=row.package_id,
                owner_id=row.reporter_id,
                severity=row.initial_severity,
                recorded=_on(row.event_at),
            ):
                count += 1
        if count:
            categories.append({"name": category.name, "count": count})

    open_actions = 0
    overdue = 0
    for row in db.query(HseAction).filter_by(project_id=project.id):
        if row.status not in OPEN_ACTION:
            continue
        if not _match(
            filters,
            company_id=row.company_id,
            owner_id=row.owner_id,
            severity=row.severity,
            recorded=_on(row.created_at),
            due=row.due_on,
        ):
            continue
        open_actions += 1
        if row.due_on and row.due_on < today:
            overdue += 1

    holds = 0
    for row in db.query(HseHold).filter_by(project_id=project.id, kind="Hold"):
        if row.status not in BLOCKING:
            continue
        if _match(
            filters,
            company_id=row.company_id,
            area_id=row.area_id,
            package_id=row.package_id,
            owner_id=row.owner_id,
            severity=row.severity,
        ):
            holds += 1

    gaps = _gap_count(db, project, filters, today)
    done, total = _inspections(db, project, filters)
    if total == 0:
        completion = "No inspection is recorded."
    else:
        completion = f"{done} of {total} have no open finding."

    drills = []
    for row in db.query(HseDrill).filter_by(project_id=project.id, status="Planned").order_by(HseDrill.planned_on):
        if row.planned_on < today:
            continue
        if not _match(filters, planned=row.planned_on):
            continue
        drills.append({"number": row.number, "title": row.title, "planned_on": row.planned_on.isoformat()})

    for row in db.query(HseEnvironmentRecord).filter_by(project_id=project.id, result="Outside criteria"):
        dims = _package_dims(db, row.package_id, area_id=row.area_id, recorded=row.recorded_on)
        if _match(filters, **dims):
            issues.append({"number": row.number, "detail": row.kind})

    return {
        "note": DASHBOARD_NOTE,
        "observation_note": OBSERVATION_COUNT_NOTE,
        "rate": "N/A",
        "rate_note": RATE_NOTE,
        "date_kinds": list(DATE_KINDS),
        "filters": {
            "company_id": filters["company_id"],
            "discipline_id": filters["discipline_id"],
            "area_id": filters["area_id"],
            "package_id": filters["package_id"],
            "owner_id": filters["owner_id"],
            "severity": filters["severity"],
            "date_kind": filters["date_kind"],
            "date_from": filters["date_from"].isoformat() if filters["date_from"] else None,
            "date_to": filters["date_to"].isoformat() if filters["date_to"] else None,
        },
        "permits": permits,
        "blocked_work": blocked,
        "open_critical_observations": observations,
        "incidents_by_category": categories,
        "open_actions": open_actions,
        "overdue_actions": overdue,
        "active_holds": holds,
        "eligibility_gaps": gaps,
        "inspection_completion": {"done": done, "total": total, "label": completion},
        "upcoming_drills": drills,
        "environmental_issues": issues,
    }


def _inspections(db, project, filters):
    done = 0
    total = 0
    for row in db.query(HseInspection).filter_by(project_id=project.id):
        if not _match(
            filters,
            company_id=row.company_id,
            discipline_id=row.discipline_id,
            area_id=row.area_id,
            package_id=row.package_id,
            owner_id=row.inspector_id,
            recorded=row.inspected_on,
        ):
            continue
        total += 1
        if db.query(HseFinding).filter_by(inspection_id=row.id, status="Open").count() == 0:
            done += 1
    return done, total


def _gap_count(db, project, filters, today):
    from app.domains.identity_projects.models import Membership, User

    from .field import _counts, hr_eligible, refresh_eligibility
    from .models import HseEligibility, HseEligibilityRule

    people = []
    seen = set()
    for membership in db.query(Membership).filter_by(project_id=project.id, active=True):
        if membership.user_id in seen:
            continue
        person = db.get(User, membership.user_id)
        if person and person.active:
            seen.add(person.id)
            people.append(person)
    count = 0
    for rule in db.query(HseEligibilityRule).filter_by(project_id=project.id):
        package = db.get(WorkPackage, rule.package_id) if rule.package_id else None
        subjects = people
        if package:
            from .field import _assigned_people

            subjects = [db.get(User, member_id) for member_id in _assigned_people(db, package, None)]
        for person in subjects:
            if not person:
                continue
            rows = db.query(HseEligibility).filter_by(project_id=project.id, member_id=person.id, category_key=rule.category_key).all()
            for row in rows:
                refresh_eligibility(db, row)
            if any(_counts(row, today) for row in rows) or hr_eligible(db, project, person.id, rule.category_key, today):
                continue
            expired = next((row.expires_on for row in rows if row.expires_on and row.expires_on < today), None)
            dims = {
                "owner_id": person.id,
                "package_id": rule.package_id,
                "expiry": expired,
            }
            if package:
                dims["company_id"] = package.company_id
                dims["discipline_id"] = package.discipline_id
                dims["area_id"] = package.area_id
            if _match(filters, **dims):
                count += 1
    return count
