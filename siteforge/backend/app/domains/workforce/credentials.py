"""Qualifications, training, and work eligibility kept in HR.

HR keeps the record. The owner of the qualification type (HR, HSE, or QA/QC)
verifies it, and nobody verifies their own record or one they entered. A
project requirement names the types needed project-wide, for a work package,
or for one activity. Eligibility is checked when labour is assigned, not only
by scheduled alerts. Medical detail is not stored here.
"""

from datetime import date, datetime, time, timedelta, timezone

from fastapi import HTTPException

from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import holds

from .deployments import LIVE, _bump, _may_verify, _person
from .models import Credential, CredentialRule, CredentialType, Deployment, Personnel, now

EXPIRY_WARNING_DAYS = 30
CLOSED = {"Rejected", "Withdrawn"}
ALERT = "hr.credential.alert"
CREDENTIAL_NOTE = (
    "HR keeps qualifications. The owner of each type verifies it: HR, HSE, or QA/QC. "
    "Nobody verifies their own record or one they entered. Medical detail is not stored here."
)
RULE_NOTE = (
    "A requirement applies project-wide, to one work package, or to one activity. "
    "Labour hours on a Construction daily line are blocked when a required qualification is missing, pending, or expired."
)
ELIGIBILITY_NOTE = (
    "Eligibility is worked out for today from verified qualifications and this project's requirements. "
    "Mobilization approval is not eligibility. With no requirements, a person is eligible by default."
)
RANK = {"Eligible": 0, "Pending Verification": 1, "Expired": 2, "Not Eligible": 3}


def _key(value):
    return value.strip().casefold()


def _scope_key(package_id, activity_id):
    return f"{package_id or 0}:{activity_id or 0}"


def _type(db, project, type_id):
    row = db.get(CredentialType, type_id)
    if not row or row.organization_id != project.organization_id:
        raise HTTPException(422, "Choose a qualification type from the list")
    return row


# Types


def add_type(db, user, project, data):
    key = _key(data.name)
    if db.query(CredentialType).filter_by(organization_id=project.organization_id, name_key=key).first():
        raise HTTPException(409, f"{data.name.strip()} is already a qualification type")
    row = CredentialType(
        organization_id=project.organization_id,
        name=data.name.strip(),
        name_key=key,
        owner=data.owner,
        requires_expiry=data.requires_expiry,
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def save_type(db, user, project, row, data):
    key = _key(data.name)
    clash = db.query(CredentialType).filter_by(organization_id=project.organization_id, name_key=key).first()
    if clash and clash.id != row.id:
        raise HTTPException(409, f"{data.name.strip()} is already a qualification type")
    if data.owner != row.owner and db.query(Credential).filter_by(type_id=row.id).first():
        raise HTTPException(409, "Records already use this type, so its verifying owner cannot change")
    _bump(
        db,
        CredentialType,
        row,
        data.version,
        {
            "name": data.name.strip(),
            "name_key": key,
            "owner": data.owner,
            "requires_expiry": data.requires_expiry,
            "active": data.active,
            "modified_by": user.id,
            "modified_at": now(),
        },
    )
    return row


# Records


def add_credential(db, user, project, data):
    person = _person(db, project, data.personnel_id)
    kind = _type(db, project, data.type_id)
    if not kind.active:
        raise HTTPException(422, f"{kind.name} is no longer an active qualification type")
    if not holds(db, user, project, "hr.edit") and person.user_id != user.id:
        raise HTTPException(403, "HR records qualifications for other people")
    if data.issue_date > date.today():
        raise HTTPException(422, "The issue date cannot be in the future")
    if kind.requires_expiry and not data.expiry_date:
        raise HTTPException(422, f"{kind.name} needs an expiry date")
    if data.expiry_date and data.expiry_date < data.issue_date:
        raise HTTPException(422, "The expiry date cannot be before the issue date")
    certificate_key = _key(data.certificate_number)
    mine = db.query(Credential).filter(
        Credential.personnel_id == person.id,
        Credential.type_id == kind.id,
        Credential.status.notin_(tuple(CLOSED)),
    )
    if mine.filter(Credential.status == "Pending Verification").first():
        raise HTTPException(409, f"{person.code} already has a {kind.name} record waiting for verification")
    if certificate_key and mine.filter(Credential.certificate_key == certificate_key).first():
        raise HTTPException(409, f"Certificate {data.certificate_number.strip()} is already on {person.code}'s record")
    if certificate_key:
        other = (
            db.query(Credential)
            .filter(
                Credential.organization_id == project.organization_id,
                Credential.type_id == kind.id,
                Credential.certificate_key == certificate_key,
                Credential.personnel_id != person.id,
                Credential.status != "Withdrawn",
            )
            .all()
        )
        if any(_key(row.issuer) == _key(data.issuer) for row in other):
            raise HTTPException(409, f"Certificate {data.certificate_number.strip()} from this issuer is already recorded for another person")
    row = Credential(
        organization_id=project.organization_id,
        personnel_id=person.id,
        type_id=kind.id,
        certificate_number=data.certificate_number.strip(),
        certificate_key=certificate_key,
        issuer=data.issuer.strip(),
        issue_date=data.issue_date,
        expiry_date=data.expiry_date,
        evidence=data.evidence.strip(),
        applicable_activities=data.applicable_activities.strip(),
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def decide(db, user, project, row, data):
    if row.status != "Pending Verification":
        raise HTTPException(409, "Only a record waiting for verification can be decided")
    kind = db.get(CredentialType, row.type_id)
    person = _person(db, project, row.personnel_id)
    if not _may_verify(db, user, project, kind.owner):
        raise HTTPException(403, f"{kind.name} is verified by {kind.owner}")
    if person.user_id and person.user_id == user.id:
        raise HTTPException(403, "You cannot verify your own qualification")
    if row.created_by == user.id:
        raise HTTPException(403, "You entered this record, so another verifier must check it")
    if data.action == "reject":
        if len(data.reason.strip()) < 3:
            raise HTTPException(422, "Give the reason for rejecting it")
        values = {"status": "Rejected"}
    else:
        if row.expiry_date and row.expiry_date < date.today():
            raise HTTPException(422, "This certificate has already expired")
        values = {"status": "Verified", "verified_by": user.id, "verified_at": now(), "verified_project_id": project.id}
    values.update({"decision_reason": data.reason.strip(), "modified_by": user.id, "modified_at": now()})
    _bump(db, Credential, row, data.version, values)
    if row.status == "Verified":
        _schedule_alerts(db, row)
    return row


def withdraw(db, user, project, row, data):
    if row.status not in {"Pending Verification", "Verified"}:
        raise HTTPException(409, "Only a pending or verified record can be withdrawn")
    kind = db.get(CredentialType, row.type_id)
    _person(db, project, row.personnel_id)
    if not holds(db, user, project, "hr.edit") and not _may_verify(db, user, project, kind.owner):
        raise HTTPException(403, f"HR or {kind.owner} withdraws this record")
    if len(data.reason.strip()) < 3:
        raise HTTPException(422, "Enter the reason")
    _bump(
        db,
        Credential,
        row,
        data.version,
        {"status": "Withdrawn", "decision_reason": data.reason.strip(), "modified_by": user.id, "modified_at": now()},
    )
    return row


# Requirements


def add_rule(db, user, project, data):
    from app.domains.construction.models import ConstructionActivity, WorkPackage

    kind = _type(db, project, data.type_id)
    if not kind.active:
        raise HTTPException(422, f"{kind.name} is no longer an active qualification type")
    if not holds(db, user, project, "hr.edit") and not _may_verify(db, user, project, kind.owner):
        raise HTTPException(403, f"HR or {kind.owner} sets this requirement")
    package_id = data.package_id
    if data.activity_id is not None:
        activity = db.get(ConstructionActivity, data.activity_id)
        if not activity or activity.project_id != project.id:
            raise HTTPException(422, "Choose an activity on this project")
        if package_id is not None and package_id != activity.package_id:
            raise HTTPException(422, "The activity is not in that work package")
        package_id = activity.package_id
    if package_id is not None:
        package = db.get(WorkPackage, package_id)
        if not package or package.project_id != project.id:
            raise HTTPException(422, "Choose a work package on this project")
    scope = _scope_key(package_id, data.activity_id)
    if db.query(CredentialRule).filter_by(project_id=project.id, type_id=kind.id, scope_key=scope).first():
        raise HTTPException(409, f"{kind.name} is already required for that scope")
    row = CredentialRule(
        organization_id=project.organization_id,
        project_id=project.id,
        type_id=kind.id,
        package_id=package_id,
        activity_id=data.activity_id,
        scope_key=scope,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def remove_rule(db, user, project, row):
    kind = db.get(CredentialType, row.type_id)
    if not holds(db, user, project, "hr.edit") and not _may_verify(db, user, project, kind.owner):
        raise HTTPException(403, f"HR or {kind.owner} removes this requirement")
    db.delete(row)
    db.flush()


def _rules(db, project, package_id=None, activity_id=None):
    """Requirements that apply to work in this package or activity. Rules on inactive types are not enforced."""
    active = {row.id for row in db.query(CredentialType).filter_by(organization_id=project.organization_id, active=True)}
    found = []
    for rule in db.query(CredentialRule).filter_by(project_id=project.id).order_by(CredentialRule.id):
        if rule.type_id not in active:
            continue
        if rule.package_id is None and rule.activity_id is None:
            found.append(rule)
        elif rule.activity_id is None and package_id is not None and rule.package_id == package_id:
            found.append(rule)
        elif rule.activity_id is not None and rule.activity_id == activity_id:
            found.append(rule)
    return found


# Eligibility


def _valid_on(row, on_date):
    return (
        row.status == "Verified"
        and row.issue_date <= on_date
        and (row.expiry_date is None or row.expiry_date >= on_date)
    )


def type_status(db, personnel_id, type_id, on_date):
    rows = db.query(Credential).filter_by(personnel_id=personnel_id, type_id=type_id).all()
    if any(_valid_on(row, on_date) for row in rows):
        return "Eligible"
    if any(row.status == "Verified" and row.expiry_date and row.expiry_date < on_date for row in rows):
        return "Expired"
    if any(row.status == "Pending Verification" for row in rows):
        return "Pending Verification"
    return "Not Eligible"


def eligibility(db, project, person, on_date, package_id=None, activity_id=None):
    names = {row.id: row.name for row in db.query(CredentialType).filter_by(organization_id=project.organization_id)}
    items = [
        {"type_id": rule.type_id, "type": names.get(rule.type_id, ""), "status": type_status(db, person.id, rule.type_id, on_date)}
        for rule in _rules(db, project, package_id, activity_id)
    ]
    seen = set()
    unique = []
    for item in items:
        if item["type_id"] not in seen:
            seen.add(item["type_id"])
            unique.append(item)
    status = max((item["status"] for item in unique), key=lambda value: RANK[value], default="Eligible")
    return {"status": status, "items": unique}


def assert_eligible(db, project, person, on_date, activity, code=409):
    result = eligibility(db, project, person, on_date, activity.package_id, activity.id)
    if result["status"] == "Eligible":
        return
    missing = ", ".join(f"{item['type']} ({item['status'].lower()})" for item in result["items"] if item["status"] != "Eligible")
    raise HTTPException(
        code,
        f"{person.code} is not eligible for {activity.code} on {on_date.isoformat()}: {missing}. This assignment stays blocked.",
    )


def _linked(db, organization_id, user_id):
    return db.query(Personnel).filter_by(organization_id=organization_id, user_id=user_id).first()


def hr_covers(db, organization_id, user_id, owner, on_date, name_key=None):
    """A verified HR record of this login's personnel, owned by HSE or QA/QC, valid on the date."""
    person = _linked(db, organization_id, user_id)
    if not person:
        return False
    kinds = db.query(CredentialType).filter_by(organization_id=organization_id, owner=owner)
    if name_key is not None:
        kinds = kinds.filter_by(name_key=name_key)
    ids = [row.id for row in kinds]
    if not ids:
        return False
    rows = db.query(Credential).filter(Credential.personnel_id == person.id, Credential.type_id.in_(ids)).all()
    return any(_valid_on(row, on_date) for row in rows)


def hr_has_any(db, organization_id, user_id, owner):
    person = _linked(db, organization_id, user_id)
    if not person:
        return False
    ids = [row.id for row in db.query(CredentialType).filter_by(organization_id=organization_id, owner=owner)]
    if not ids:
        return False
    return (
        db.query(Credential)
        .filter(Credential.personnel_id == person.id, Credential.type_id.in_(ids), Credential.status.in_(("Verified", "Withdrawn")))
        .first()
        is not None
    )


# Expiry alerts


def _schedule_alerts(db, row):
    if not row.expiry_date:
        return
    from app.domains.coordination.jobs import enqueue

    warn = datetime.combine(row.expiry_date - timedelta(days=EXPIRY_WARNING_DAYS), time(6), timezone.utc)
    lapse = datetime.combine(row.expiry_date + timedelta(days=1), time(6), timezone.utc)
    stamp = row.expiry_date.isoformat()
    enqueue(db, ALERT, {"credential_id": row.id, "stage": "expiring", "expiry": stamp}, f"hr:credential:{row.id}:expiring:{stamp}", warn)
    enqueue(db, ALERT, {"credential_id": row.id, "stage": "expired", "expiry": stamp}, f"hr:credential:{row.id}:expired:{stamp}", lapse)


def alert(db, job):
    from app.domains.coordination.jobs import notify

    row = db.get(Credential, job.payload["credential_id"])
    stage = job.payload["stage"]
    if not row or row.status != "Verified" or not row.expiry_date or row.expiry_date.isoformat() != job.payload["expiry"]:
        return
    person = db.get(Personnel, row.personnel_id)
    kind = db.get(CredentialType, row.type_id)
    if not person or not kind:
        return
    if stage == "expiring":
        title = "Qualification expiring"
        body = f"{kind.name} for {person.code} expires on {row.expiry_date.isoformat()}."
    else:
        title = "Qualification expired"
        body = f"{kind.name} for {person.code} expired on {row.expiry_date.isoformat()}. Assignments that need it are blocked."
    recipients = {}
    for user_id in (person.user_id, row.verified_by):
        login = db.get(User, user_id) if user_id else None
        if login and login.active:
            recipients[login.id] = (login, row.verified_project_id)
    if stage == "expired":
        live = db.query(Deployment).filter(Deployment.personnel_id == person.id, Deployment.status.in_(tuple(LIVE))).all()
        for deployment in live:
            boss = db.get(Personnel, deployment.supervisor_id) if deployment.supervisor_id else None
            login = db.get(User, boss.user_id) if boss and boss.user_id else None
            if login and login.active:
                recipients.setdefault(login.id, (login, deployment.project_id))
    for login, project_id in recipients.values():
        notify(
            db,
            login,
            title,
            body,
            f"hr:credential:{row.id}:{stage}:{row.expiry_date.isoformat()}:{login.id}",
            project_id=project_id,
            link=f"/projects/{project_id}" if project_id else "",
        )


# Views


def credential_view(db, user, project, row, kinds, people, users):
    kind = kinds.get(row.type_id)
    person = people.get(row.personnel_id)
    today = date.today()
    expired = row.status == "Verified" and row.expiry_date is not None and row.expiry_date < today
    expiring = (
        row.status == "Verified"
        and row.expiry_date is not None
        and today <= row.expiry_date <= today + timedelta(days=EXPIRY_WARNING_DAYS)
    )
    own = bool(person and person.user_id == user.id) or row.created_by == user.id
    may_verify = bool(kind) and _may_verify(db, user, project, kind.owner)
    return {
        "id": row.id,
        "personnel_id": row.personnel_id,
        "person": f"{person.code} · {person.full_name}" if person else "",
        "type_id": row.type_id,
        "type": kind.name if kind else "",
        "owner": kind.owner if kind else "",
        "certificate_number": row.certificate_number,
        "issuer": row.issuer,
        "issue_date": row.issue_date.isoformat(),
        "expiry_date": row.expiry_date.isoformat() if row.expiry_date else None,
        "evidence": row.evidence,
        "applicable_activities": row.applicable_activities,
        "status": row.status,
        "state": "Expired" if expired else "Expiring" if expiring else row.status,
        "decision_reason": row.decision_reason,
        "verified_by": users.get(row.verified_by, "") if row.verified_by else "",
        "verified_at": row.verified_at.isoformat() if row.verified_at else None,
        "created_by": users.get(row.created_by, ""),
        "can_decide": row.status == "Pending Verification" and may_verify and not own,
        "decide_block": (
            "You cannot verify your own record or one you entered"
            if row.status == "Pending Verification" and may_verify and own
            else ""
        ),
        "can_withdraw": row.status in {"Pending Verification", "Verified"} and (holds(db, user, project, "hr.edit") or may_verify),
        "version": row.version,
    }


def _rule_view(row, kinds, packages, activities):
    kind = kinds.get(row.type_id)
    if row.activity_id:
        scope = f"Activity {activities.get(row.activity_id, '')}"
    elif row.package_id:
        scope = f"Package {packages.get(row.package_id, '')}"
    else:
        scope = "Whole project"
    return {
        "id": row.id,
        "type_id": row.type_id,
        "type": kind.name if kind else "",
        "owner": kind.owner if kind else "",
        "active": bool(kind and kind.active),
        "package_id": row.package_id,
        "activity_id": row.activity_id,
        "scope": scope,
    }


def supplement(db, user, project, payload, names):
    from app.domains.construction.models import ConstructionActivity, WorkPackage

    from .service import _company_ids

    today = date.today()
    company_ids = _company_ids(db, project)
    type_rows = db.query(CredentialType).filter_by(organization_id=project.organization_id).order_by(CredentialType.name).all()
    kinds = {row.id: row for row in type_rows}
    people = {
        row.id: row
        for row in db.query(Personnel).filter(
            Personnel.organization_id == project.organization_id, Personnel.company_id.in_(company_ids or [-1])
        )
    }
    users = {row.id: row.name for row in db.query(User).filter(User.organization_id == project.organization_id)}
    packages = {row.id: row.code for row in db.query(WorkPackage).filter_by(project_id=project.id)}
    activity_rows = db.query(ConstructionActivity).filter_by(project_id=project.id, active=True).order_by(ConstructionActivity.code).all()
    activities = {row.id: row.code for row in activity_rows}
    records = (
        db.query(Credential)
        .filter(Credential.personnel_id.in_(list(people) or [-1]))
        .order_by(Credential.id.desc())
        .limit(200)
        .all()
    )
    rules = db.query(CredentialRule).filter_by(project_id=project.id).order_by(CredentialRule.id).all()
    views = [credential_view(db, user, project, row, kinds, people, users) for row in records]
    current = {(row["personnel_id"], row["type_id"]) for row in views if row["status"] == "Verified" and row["state"] != "Expired"}
    for row in views:
        row["superseded"] = row["state"] in {"Expired", "Expiring"} and any(
            other is not row
            and other["personnel_id"] == row["personnel_id"]
            and other["type_id"] == row["type_id"]
            and other["status"] == "Verified"
            and (other["expiry_date"] is None or (row["expiry_date"] and other["expiry_date"] > row["expiry_date"]))
            for other in views
        )
    deployed = {}
    for deployment in db.query(Deployment).filter(Deployment.project_id == project.id, Deployment.status.in_(tuple(LIVE))):
        deployed.setdefault(deployment.personnel_id, deployment.status)
    table = []
    for personnel_id, status in deployed.items():
        person = people.get(personnel_id)
        if not person:
            continue
        overall = eligibility(db, project, person, today)
        scoped = [
            {
                "rule_id": rule.id,
                "type": kinds[rule.type_id].name,
                "scope": _rule_view(rule, kinds, packages, activities)["scope"],
                "status": type_status(db, person.id, rule.type_id, today),
            }
            for rule in rules
            if (rule.package_id or rule.activity_id) and kinds.get(rule.type_id) and kinds[rule.type_id].active
        ]
        table.append(
            {
                "personnel_id": person.id,
                "person": f"{person.code} · {person.full_name}",
                "deployment_status": status,
                "status": overall["status"],
                "items": overall["items"],
                "scoped": scoped,
            }
        )
    table.sort(key=lambda row: (-RANK[row["status"]], row["person"]))
    payload["credential_types"] = [
        {"id": row.id, "name": row.name, "owner": row.owner, "requires_expiry": row.requires_expiry, "active": row.active, "version": row.version}
        for row in type_rows
    ]
    payload["credentials"] = views
    payload["credential_rules"] = [_rule_view(row, kinds, packages, activities) for row in rules]
    payload["eligibility"] = table
    payload["activities"] = [{"id": row.id, "name": row.code, "package_id": row.package_id} for row in activity_rows]
    payload["credential_note"] = CREDENTIAL_NOTE
    payload["rule_note"] = RULE_NOTE
    payload["eligibility_note"] = ELIGIBILITY_NOTE
    payload["can_manage_credentials"] = holds(db, user, project, "hr.edit")
    payload["credential_owners_i_verify"] = [owner for owner in ("HR", "HSE", "QA/QC") if _may_verify(db, user, project, owner)]
    payload["counts"].update(
        {
            "credentials_pending": sum(1 for row in views if row["status"] == "Pending Verification"),
            "credentials_expiring": sum(1 for row in views if row["state"] == "Expiring" and not row["superseded"]),
            "credentials_expired": len(
                {
                    (row["personnel_id"], row["type_id"])
                    for row in views
                    if row["state"] == "Expired" and (row["personnel_id"], row["type_id"]) not in current
                }
            ),
            "not_eligible": sum(1 for row in table if row["status"] != "Eligible"),
        }
    )
    return payload
