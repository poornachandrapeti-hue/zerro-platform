"""HR alerts and escalation.

Alerts are worked out from current records each time; nothing is stored but the
notification. A project sends notifications only after its alert settings are
saved and enabled. An alert escalates to the saved escalation recipients once it
has stayed open for the configured number of days. Notification text names
codes and numbers only, never personal details.
"""

from datetime import date, timedelta

from fastapi import HTTPException

from app.domains.identity_projects.models import Membership, Project, User

from .models import Deployment, MonitorSetting, OnboardingCheck, Personnel, WorkforceRequest, now

DEFAULTS = {"enabled": False, "mobilization_grace_days": 2, "onboarding_lead_days": 3, "attendance_grace_days": 1, "escalate_after_days": 3}
MONITOR_NOTE = (
    "Alerts are worked out from current records. Notifications go out only after these settings are saved and enabled, "
    "from the background worker. An alert escalates once it stays open for the set number of days. "
    "Notification text names codes and numbers only."
)


def settings(db, project):
    return db.query(MonitorSetting).filter_by(project_id=project.id).first()


def _values(row):
    if row is None:
        return {**DEFAULTS, "escalation_user_ids": [], "version": None, "saved": False}
    return {
        "enabled": row.enabled,
        "mobilization_grace_days": row.mobilization_grace_days,
        "onboarding_lead_days": row.onboarding_lead_days,
        "attendance_grace_days": row.attendance_grace_days,
        "escalate_after_days": row.escalate_after_days,
        "escalation_user_ids": list(row.escalation_user_ids or []),
        "version": row.version,
        "saved": True,
    }


def save_settings(db, user, project, data):
    members = {row.user_id for row in db.query(Membership).filter_by(project_id=project.id, active=True)}
    unknown = [uid for uid in data.escalation_user_ids if uid not in members]
    if unknown:
        raise HTTPException(422, "Escalation recipients must be active project members")
    row = settings(db, project)
    values = {
        "enabled": data.enabled,
        "mobilization_grace_days": data.mobilization_grace_days,
        "onboarding_lead_days": data.onboarding_lead_days,
        "attendance_grace_days": data.attendance_grace_days,
        "escalate_after_days": data.escalate_after_days,
        "escalation_user_ids": list(dict.fromkeys(data.escalation_user_ids)),
        "modified_by": user.id,
        "modified_at": now(),
    }
    if row is None:
        if data.version is not None:
            raise HTTPException(409, "This record changed. Reload it and try again")
        row = MonitorSetting(organization_id=project.organization_id, project_id=project.id, **values)
        db.add(row)
        db.flush()
        return row
    if data.version != row.version:
        raise HTTPException(409, "This record changed. Reload it and try again")
    for key, value in values.items():
        setattr(row, key, value)
    row.version += 1
    db.flush()
    return row


def _login(db, personnel_id):
    person = db.get(Personnel, personnel_id) if personnel_id else None
    return person.user_id if person and person.user_id else None


def _owner(db, deployment):
    return _login(db, deployment.supervisor_id) or deployment.created_by


def _alert(kind, key, subject, body, since, today, escalate_after, recipients):
    age = (today - since).days
    return {
        "kind": kind,
        "key": key,
        "subject": subject,
        "body": body,
        "since": since.isoformat(),
        "age_days": max(age, 0),
        "escalated": age >= escalate_after,
        "recipient_ids": sorted({uid for uid in recipients if uid}),
    }


def findings(db, project, today=None, values=None):
    from .attendance import ATTENDING_DEPLOYMENTS
    from .credentials import type_status
    from .deployments import REQUEST_ALLOCATING, _counts
    from .leave import approved_leave
    from .models import AttendanceRecord, Credential, CredentialRule, CredentialType, Offboarding, Shift
    from .offboarding import LIVE as OFFBOARDING_LIVE
    from .offboarding import open_tasks

    today = today or date.today()
    values = values or _values(settings(db, project))
    escalate = values["escalate_after_days"]
    alerts = []
    deployments = db.query(Deployment).filter_by(project_id=project.id).all()
    people = {row.id: row for row in db.query(Personnel).filter_by(organization_id=project.organization_id)}

    for row in db.query(WorkforceRequest).filter(WorkforceRequest.project_id == project.id, WorkforceRequest.status.in_(tuple(REQUEST_ALLOCATING))):
        counts = _counts(db, row)
        if counts["shortfall"] and row.start_date <= today + timedelta(days=7):
            alerts.append(
                _alert(
                    "Workforce shortfall",
                    f"request:{row.id}",
                    row.number,
                    f"Request {row.number} still needs {counts['shortfall']} of {counts['required']} people from {row.start_date.isoformat()}.",
                    row.start_date - timedelta(days=7),
                    today,
                    escalate,
                    [row.requested_by],
                )
            )

    for row in deployments:
        person = people.get(row.personnel_id)
        code = person.code if person else f"#{row.personnel_id}"
        if row.status == "Approved for Mobilization":
            since = row.planned_start + timedelta(days=values["mobilization_grace_days"])
            if since < today:
                alerts.append(
                    _alert(
                        "Mobilization delayed",
                        f"deployment:{row.id}",
                        code,
                        f"{code} was planned to mobilize on {row.planned_start.isoformat()} and is not mobilized.",
                        since,
                        today,
                        escalate,
                        [row.created_by],
                    )
                )
        if row.status == "Proposed":
            pending = db.query(OnboardingCheck).filter_by(deployment_id=row.id, status="Pending").count()
            since = row.planned_start - timedelta(days=values["onboarding_lead_days"])
            if pending and since <= today:
                alerts.append(
                    _alert(
                        "Onboarding evidence missing",
                        f"onboarding:{row.id}",
                        code,
                        f"{code} has {pending} onboarding check{'s' if pending != 1 else ''} still pending; planned mobilization {row.planned_start.isoformat()}.",
                        since,
                        today,
                        escalate,
                        [row.created_by],
                    )
                )

    if db.query(Shift).filter_by(project_id=project.id).first():
        day = today - timedelta(days=values["attendance_grace_days"])
        for row in deployments:
            if row.status not in ATTENDING_DEPLOYMENTS or row.status == "Temporarily Unavailable" or not row.actual_start:
                continue
            missing = 0
            first = None
            for back in range(escalate + 1):
                check = day - timedelta(days=back)
                if check < row.actual_start or (row.actual_end and check > row.actual_end):
                    break
                if approved_leave(db, project, row.personnel_id, check):
                    break
                if db.query(AttendanceRecord).filter_by(project_id=project.id, personnel_id=row.personnel_id, attendance_date=check).first():
                    break
                missing += 1
                first = check
            if not missing:
                continue
            person = people.get(row.personnel_id)
            code = person.code if person else f"#{row.personnel_id}"
            alerts.append(
                _alert(
                    "Attendance missing",
                    f"attendance:{row.personnel_id}:{day.isoformat()}",
                    code,
                    f"No attendance is recorded for {code} on {day.isoformat()}"
                    + (f" ({missing} days in a row)." if missing > 1 else "."),
                    first,
                    day,
                    escalate,
                    [_owner(db, row)],
                )
            )

    names = {row.id: row for row in db.query(CredentialType).filter_by(organization_id=project.organization_id)}
    required = {rule.type_id for rule in db.query(CredentialRule).filter_by(project_id=project.id)}
    seen = set()
    for row in deployments:
        if row.status not in {"Approved for Mobilization", "Mobilized", "Temporarily Unavailable"} or row.personnel_id in seen:
            continue
        seen.add(row.personnel_id)
        person = people.get(row.personnel_id)
        if not person:
            continue
        for type_id in sorted(required):
            kind = names.get(type_id)
            if not kind or not kind.active or type_status(db, person.id, type_id, today) != "Expired":
                continue
            lapsed = (
                db.query(Credential)
                .filter(Credential.personnel_id == person.id, Credential.type_id == type_id, Credential.status == "Verified")
                .order_by(Credential.expiry_date.desc())
                .first()
            )
            since = lapsed.expiry_date + timedelta(days=1) if lapsed and lapsed.expiry_date else today
            alerts.append(
                _alert(
                    "Mandatory credential expired",
                    f"credential:{person.id}:{type_id}",
                    person.code,
                    f"{kind.name} for {person.code} expired on {lapsed.expiry_date.isoformat() if lapsed and lapsed.expiry_date else 'an earlier date'}. Assignments that need it are blocked.",
                    since,
                    today,
                    escalate,
                    [_owner(db, row), lapsed.verified_by if lapsed else None],
                )
            )

    for row in db.query(Offboarding).filter(Offboarding.project_id == project.id, Offboarding.status.in_(tuple(OFFBOARDING_LIVE))):
        person = people.get(row.personnel_id)
        if not person:
            continue
        count = len(open_tasks(db, project, person))
        if count:
            deployment = db.get(Deployment, row.deployment_id)
            alerts.append(
                _alert(
                    "Demobilization has open tasks",
                    f"offboarding:{row.id}",
                    person.code,
                    f"{person.code} is being demobilized and still owns {count} open task{'s' if count != 1 else ''} on this project.",
                    row.created_at.date(),
                    today,
                    escalate,
                    [person.user_id, _owner(db, deployment) if deployment else None],
                )
            )

    from .service import _company_ids

    admins = [row.id for row in db.query(User).filter_by(organization_id=project.organization_id, organization_admin=True, active=True)]
    companies = _company_ids(db, project)
    for person in people.values():
        if person.status != "Separated" or not person.user_id or person.company_id not in companies:
            continue
        login = db.get(User, person.user_id)
        if login and login.active:
            alerts.append(
                _alert(
                    "Employment ended but login active",
                    f"login:{person.id}",
                    person.code,
                    f"Employment of {person.code} ended and the linked login is still active.",
                    person.end_date or today,
                    today,
                    escalate,
                    admins,
                )
            )
    return alerts


def _send(db, project, values, alerts):
    from app.domains.coordination.jobs import notify

    escalation = [db.get(User, uid) for uid in values["escalation_user_ids"]]
    for alert in alerts:
        base = f"hr:monitor:{project.id}:{alert['key']}:{alert['since']}"
        for uid in alert["recipient_ids"]:
            login = db.get(User, uid)
            if login and login.active:
                notify(db, login, alert["kind"], alert["body"], f"{base}:{uid}", project_id=project.id, link=f"/projects/{project.id}")
        if alert["escalated"]:
            for login in escalation:
                if login and login.active:
                    notify(
                        db,
                        login,
                        f"Escalated: {alert['kind']}",
                        f"{alert['body']} Open for {alert['age_days']} days.",
                        f"{base}:escalated:{login.id}",
                        project_id=project.id,
                        link=f"/projects/{project.id}",
                    )


def scan(db, today=None):
    """Send HR alerts for every project with saved, enabled settings."""
    for row in db.query(MonitorSetting).filter_by(enabled=True).all():
        project = db.get(Project, row.project_id)
        if not project:
            continue
        values = _values(row)
        _send(db, project, values, findings(db, project, today, values))


def supplement(db, user, project, payload):
    values = _values(settings(db, project))
    alerts = findings(db, project, values=values)
    users = {row.id: row.name for row in db.query(User).filter(User.organization_id == project.organization_id)}
    for alert in alerts:
        alert["recipients"] = [users.get(uid, "") for uid in alert["recipient_ids"]]
    payload["alerts"] = alerts
    payload["monitor_settings"] = values
    payload["monitor_note"] = MONITOR_NOTE
    payload["escalation_names"] = [users.get(uid, "") for uid in values["escalation_user_ids"]]
    payload["counts"]["open_alerts"] = len(alerts)
    payload["counts"]["escalated_alerts"] = sum(1 for alert in alerts if alert["escalated"])
    return payload
