"""Project deployments, onboarding checks, and workforce requests.

A deployment places a person on a project. It does not create a login, a
project membership, or a role. Approved for Mobilization is not task
eligibility. HR coordinates mobilization; HSE and QA/QC verify their own
checks. A workforce request keeps required, proposed, allocated, and shortfall
apart.
"""

from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import update

from app.domains.coordination.service import REVIEW_GUARDS
from app.domains.engineering_documents.workflow import submit_record
from app.domains.identity_projects.models import Area, Discipline, ProjectDiscipline, User
from app.domains.identity_projects.security import holds
from app.domains.supply_chain.service import _authority, _policy, role_allows

from .models import (
    CHECK_STATUSES,
    CHECK_TYPES,
    PRIORITIES,
    Deployment,
    OnboardingCheck,
    Personnel,
    RequestLine,
    WorkforceMaster,
    WorkforceRequest,
    now,
)
from .service import _company_ids

DEPLOYMENT = "hr.deployment"
REQUEST = "hr.request"
CHECK_OWNER = {
    "Personnel documents": "HR",
    "Qualifications": "QA/QC",
    "Site induction": "HSE",
    "Work eligibility": "HSE",
    "Access arrangements": "HR",
}
LIVE = {"Proposed", "Pending Approval", "Approved for Mobilization", "Mobilized", "Temporarily Unavailable"}
ON_SITE = {"Approved for Mobilization", "Mobilized"}
REQUEST_EDITABLE = {"Draft", "Returned"}
REQUEST_ALLOCATING = {"Open", "Partially Allocated", "Allocated"}
DEPLOYMENT_NOTE = (
    "A deployment does not give a login, a project membership, or a role. "
    "Approved for Mobilization does not mean the person is eligible for every controlled activity."
)
REQUEST_NOTE = "Required, proposed, allocated, and shortfall are separate. Proposed people do not reduce the shortfall."


def _bump(db, model, row, version, values):
    changed = db.execute(
        update(model).where(model.id == row.id, model.version == version).values(version=version + 1, **values)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This record changed. Reload it and try again")
    db.refresh(row)


def _policy_for(db, project, record_type, company_id, discipline_id):
    policy = _policy(db, project, record_type, company_id, discipline_id)
    if not policy:
        raise HTTPException(422, "Mandatory reviewer configuration is missing")
    _authority(db, project, policy)
    return policy


def _discipline(db, project, discipline_id):
    if discipline_id is None:
        return None
    row = db.query(ProjectDiscipline).filter_by(project_id=project.id, discipline_id=discipline_id, active=True).first()
    if not row:
        raise HTTPException(422, "Discipline is not active on this project")
    return db.get(Discipline, discipline_id)


def _area(db, project, area_id):
    if area_id is None:
        return None
    row = db.get(Area, area_id)
    if not row or row.project_id != project.id:
        raise HTTPException(422, "Choose a work location on this project")
    return row


def _person(db, project, personnel_id):
    person = db.get(Personnel, personnel_id)
    if not person or person.organization_id != project.organization_id or person.company_id not in _company_ids(db, project):
        raise HTTPException(422, "Choose a person employed by a company active on this project")
    return person


def _overlaps(start_a, end_a, start_b, end_b):
    far = date.max
    return start_a <= (end_b or far) and start_b <= (end_a or far)


def _check_dates(db, project, person, start, end, current_id=None):
    if end and end < start:
        raise HTTPException(422, "Planned demobilization cannot be before planned mobilization")
    if start < person.start_date:
        raise HTTPException(422, "Planned mobilization is before this person's employment start")
    if person.end_date and (start > person.end_date or (end and end > person.end_date)):
        raise HTTPException(422, "The deployment runs past this person's employment end date")
    others = db.query(Deployment).filter(
        Deployment.project_id == project.id,
        Deployment.personnel_id == person.id,
        Deployment.status.in_(tuple(LIVE)),
    )
    if current_id:
        others = others.filter(Deployment.id != current_id)
    for row in others:
        if _overlaps(start, end, row.planned_start, row.planned_end):
            raise HTTPException(409, "This person already has an open deployment on this project for those dates")


def add_deployment(db, user, project, data):
    person = _person(db, project, data.personnel_id)
    if person.status != "Active":
        raise HTTPException(422, "Only an active person can be deployed")
    _discipline(db, project, data.discipline_id)
    _area(db, project, data.area_id)
    if data.supervisor_id is not None:
        boss = _person(db, project, data.supervisor_id)
        if boss.id == person.id:
            raise HTTPException(422, "A person cannot supervise themselves")
    _check_dates(db, project, person, data.planned_start, data.planned_end)
    unknown = [name for name in data.checks if name not in CHECK_TYPES]
    if unknown:
        raise HTTPException(422, "Choose onboarding checks from the listed checks")
    row = Deployment(
        organization_id=project.organization_id,
        project_id=project.id,
        personnel_id=person.id,
        company_id=person.company_id,
        discipline_id=data.discipline_id if data.discipline_id is not None else person.discipline_id,
        supervisor_id=data.supervisor_id,
        area_id=data.area_id,
        planned_start=data.planned_start,
        planned_end=data.planned_end,
        shift=data.shift.strip(),
        required_skills=data.required_skills.strip(),
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(row)
    db.flush()
    chosen = set(data.checks)
    for name in CHECK_TYPES:
        db.add(
            OnboardingCheck(
                deployment_id=row.id,
                check_type=name,
                owner=CHECK_OWNER[name],
                status="Pending" if name in chosen else "Not required",
            )
        )
    db.flush()
    return row


def save_deployment(db, user, project, row, data):
    if row.status != "Proposed":
        raise HTTPException(409, "Only a proposed deployment can be edited")
    person = db.get(Personnel, row.personnel_id)
    _discipline(db, project, data.discipline_id)
    _area(db, project, data.area_id)
    if data.supervisor_id is not None:
        boss = _person(db, project, data.supervisor_id)
        if boss.id == person.id:
            raise HTTPException(422, "A person cannot supervise themselves")
    _check_dates(db, project, person, data.planned_start, data.planned_end, current_id=row.id)
    _bump(
        db,
        Deployment,
        row,
        data.version,
        {
            "discipline_id": data.discipline_id,
            "supervisor_id": data.supervisor_id,
            "area_id": data.area_id,
            "planned_start": data.planned_start,
            "planned_end": data.planned_end,
            "shift": data.shift.strip(),
            "required_skills": data.required_skills.strip(),
            "modified_by": user.id,
            "modified_at": now(),
        },
    )
    return row


def _may_verify(db, user, project, owner):
    if owner == "HR":
        return holds(db, user, project, "hr.edit")
    if owner == "HSE":
        return role_allows(db, user, project, "hse.plan")
    return role_allows(db, user, project, "quality.plan")


def verify_check(db, user, project, deployment, check, data):
    if check.deployment_id != deployment.id:
        raise HTTPException(404, "Check not found")
    if deployment.status not in {"Proposed", "Pending Approval"}:
        raise HTTPException(409, "Onboarding checks are recorded before mobilization approval")
    if data.status not in CHECK_STATUSES:
        raise HTTPException(422, "Choose Pending, Verified, or Not required")
    if not _may_verify(db, user, project, check.owner):
        raise HTTPException(403, f"{check.check_type} is verified by {check.owner}")
    person = db.get(Personnel, deployment.personnel_id)
    if person.user_id and person.user_id == user.id:
        raise HTTPException(403, "You cannot verify your own onboarding")
    if data.status == "Verified" and len(data.evidence.strip()) < 3:
        raise HTTPException(422, "Record the evidence you checked")
    _bump(
        db,
        OnboardingCheck,
        check,
        data.version,
        {
            "status": data.status,
            "evidence": data.evidence.strip(),
            "verified_by": user.id if data.status != "Pending" else None,
            "verified_at": now() if data.status != "Pending" else None,
        },
    )
    return check


def _checks(db, deployment):
    return db.query(OnboardingCheck).filter_by(deployment_id=deployment.id).order_by(OnboardingCheck.id).all()


def submit_deployment(db, user, project, row, version):
    if row.status != "Proposed":
        raise HTTPException(409, "Only a proposed deployment can be submitted")
    pending = [check.check_type for check in _checks(db, row) if check.status == "Pending"]
    if pending:
        raise HTTPException(409, "Verify the onboarding checks first: " + ", ".join(pending))
    person = db.get(Personnel, row.personnel_id)
    if person.status != "Active":
        raise HTTPException(409, "Only an active person can be mobilized")
    policy = _policy_for(db, project, DEPLOYMENT, row.company_id, row.discipline_id)
    _bump(db, Deployment, row, version, {"status": "Pending Approval", "modified_by": user.id, "modified_at": now()})
    return submit_record(db, user, project, DEPLOYMENT, row.id, row.version, policy)


MOVES = {
    "mobilize": ({"Approved for Mobilization"}, "Mobilized"),
    "unavailable": ({"Mobilized"}, "Temporarily Unavailable"),
    "return": ({"Temporarily Unavailable"}, "Mobilized"),
    "demobilize": ({"Mobilized", "Temporarily Unavailable"}, "Demobilized"),
    "cancel": ({"Proposed", "Approved for Mobilization"}, "Cancelled"),
}


def move_deployment(db, user, project, row, data):
    if data.action not in MOVES:
        raise HTTPException(422, "Unknown deployment action")
    if data.action == "demobilize":
        raise HTTPException(409, "Demobilize through an approved offboarding")
    allowed, target = MOVES[data.action]
    if row.status not in allowed:
        raise HTTPException(409, f"A {row.status.lower()} deployment cannot do that")
    values = {"status": target, "modified_by": user.id, "modified_at": now()}
    person = db.get(Personnel, row.personnel_id)
    if data.action == "mobilize":
        if not data.on:
            raise HTTPException(422, "Enter the actual mobilization date")
        if person.status != "Active":
            raise HTTPException(409, "Only an active person can be mobilized")
        if data.on < person.start_date or (person.end_date and data.on > person.end_date):
            raise HTTPException(422, "The mobilization date is outside this person's employment")
        values["actual_start"] = data.on
    if data.action == "demobilize":
        if not data.on:
            raise HTTPException(422, "Enter the actual demobilization date")
        if row.actual_start and data.on < row.actual_start:
            raise HTTPException(422, "Demobilization cannot be before mobilization")
        values["actual_end"] = data.on
    if data.action in {"unavailable", "cancel"}:
        if len(data.reason.strip()) < 3:
            raise HTTPException(422, "Enter the reason")
        values["status_reason"] = data.reason.strip()
    if data.action == "return":
        values["status_reason"] = ""
    _bump(db, Deployment, row, data.version, values)
    if target in {"Demobilized", "Cancelled", "Temporarily Unavailable"}:
        _release_lines(db, row, target)
    return row


def _release_lines(db, deployment, target):
    """Leaving the project releases allocations. Unavailability only flags them."""
    lines = db.query(RequestLine).filter_by(deployment_id=deployment.id, state="Allocated").all()
    for line in lines:
        if target == "Temporarily Unavailable":
            continue
        line.state = "Released"
        line.modified_at = now()
        request = db.get(WorkforceRequest, line.request_id)
        if request:
            _settle(db, request)


def on_review_event(db, user, instance, project, action, stage=None):
    if action == "advance":
        return
    if instance.record_type == DEPLOYMENT:
        row = db.get(Deployment, instance.record_id)
        if not row or row.project_id != project.id:
            return
        if action == "return":
            row.status = "Proposed"
        elif action == "reject":
            row.status = "Cancelled"
            row.status_reason = "Mobilization approval was rejected"
        elif instance.state == "Approved":
            row.status = "Approved for Mobilization"
        else:
            return
    else:
        row = db.get(WorkforceRequest, instance.record_id)
        if not row or row.project_id != project.id:
            return
        if action == "return":
            row.status = "Returned"
        elif action == "reject":
            row.status = "Rejected"
        elif instance.state == "Approved":
            row.status = "Open"
        else:
            return
    row.version += 1
    row.modified_by = user.id
    row.modified_at = now()


def apply_resubmit(db, user, instance, review_version):
    from app.domains.coordination.service import _close_tasks as close_tasks
    from app.domains.coordination.service import _lock, _open_stage, current_stage
    from app.domains.identity_projects.models import Project

    if instance.state != "Returned":
        raise HTTPException(409, "Only a returned review can be resubmitted")
    if user.id != instance.submitted_by and not user.organization_admin:
        raise HTTPException(403, "Only the submitter can resubmit")
    project = db.get(Project, instance.project_id)
    if instance.record_type == DEPLOYMENT:
        row = db.get(Deployment, instance.record_id)
        if not row or row.status != "Proposed":
            raise HTTPException(409, "Only a returned deployment can be resubmitted")
        pending = [check.check_type for check in _checks(db, row) if check.status == "Pending"]
        if pending:
            raise HTTPException(409, "Verify the onboarding checks first: " + ", ".join(pending))
        policy = _policy_for(db, project, DEPLOYMENT, row.company_id, row.discipline_id)
        status = "Pending Approval"
        model = Deployment
    else:
        row = db.get(WorkforceRequest, instance.record_id)
        if not row or row.status != "Returned":
            raise HTTPException(409, "Only a returned request can be resubmitted")
        policy = _policy_for(db, project, REQUEST, row.company_id, row.discipline_id)
        status = "Pending Review"
        model = WorkforceRequest
    _lock(db, instance, review_version)
    close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    _bump(db, model, row, row.version, {"status": status, "modified_by": user.id, "modified_at": now()})
    instance.record_version = row.version
    instance.policy_id = policy.id
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def review_guard(db, user, instance, stage, action):
    if action != "approve" or instance.record_type not in {DEPLOYMENT, REQUEST}:
        return
    if user.id == instance.submitted_by:
        raise HTTPException(403, "You cannot approve your own submission")
    if instance.record_type == DEPLOYMENT:
        row = db.get(Deployment, instance.record_id)
        person = db.get(Personnel, row.personnel_id) if row else None
        if person and person.user_id == user.id:
            raise HTTPException(403, "You cannot approve your own mobilization")


if review_guard not in REVIEW_GUARDS:
    REVIEW_GUARDS.append(review_guard)


# Workforce requests


def _trade(db, project, trade_id):
    row = db.get(WorkforceMaster, trade_id)
    if not row or row.organization_id != project.organization_id or row.kind != "Trade":
        raise HTTPException(422, "Choose a trade from the workforce list")
    return row


def _check_request(db, project, data, current=None):
    if data.priority not in PRIORITIES:
        raise HTTPException(422, "Choose Low, Normal, High, or Urgent")
    if data.company_id not in _company_ids(db, project):
        raise HTTPException(422, "The requesting company is not active on this project")
    trade = _trade(db, project, data.trade_id)
    if not trade.active and (current is None or current.trade_id != trade.id):
        raise HTTPException(422, f"Trade {trade.name} is no longer active")
    _discipline(db, project, data.discipline_id)
    _area(db, project, data.area_id)
    if data.package_id is not None:
        from app.domains.construction.models import WorkPackage

        package = db.get(WorkPackage, data.package_id)
        if not package or package.project_id != project.id:
            raise HTTPException(422, "Choose a work package on this project")
    if data.activity_id is not None:
        from app.domains.construction.models import ConstructionActivity

        activity = db.get(ConstructionActivity, data.activity_id)
        if not activity or activity.project_id != project.id:
            raise HTTPException(422, "Choose an activity on this project")
        if data.package_id is not None and activity.package_id != data.package_id:
            raise HTTPException(422, "The activity is not in that work package")
    if data.grade_id is not None:
        grade = db.get(WorkforceMaster, data.grade_id)
        if not grade or grade.organization_id != project.organization_id or grade.kind != "Skill grade":
            raise HTTPException(422, "Choose a skill grade from the workforce list")
        if not grade.active and (current is None or current.grade_id != grade.id):
            raise HTTPException(422, f"Skill grade {grade.name} is no longer active")
    if data.end_date and data.end_date < data.start_date:
        raise HTTPException(422, "Required end date cannot be before the start date")
    if data.required_mobilization and data.required_mobilization > data.start_date:
        raise HTTPException(422, "Required mobilization cannot be after the start date")
    key = data.number.strip().casefold()
    clash = db.query(WorkforceRequest).filter(WorkforceRequest.project_id == project.id, WorkforceRequest.number_key == key)
    if current is not None:
        clash = clash.filter(WorkforceRequest.id != current.id)
    if clash.first():
        raise HTTPException(409, f"Request {data.number} already exists on this project")
    return key


def _request_values(db, data):
    package_id = data.package_id
    if data.activity_id is not None and package_id is None:
        from app.domains.construction.models import ConstructionActivity

        package_id = db.get(ConstructionActivity, data.activity_id).package_id
    return {
        "number": data.number.strip(),
        "discipline_id": data.discipline_id,
        "area_id": data.area_id,
        "package_id": package_id,
        "activity_id": data.activity_id,
        "grade_id": data.grade_id,
        "required_hours": data.required_hours,
        "required_mobilization": data.required_mobilization,
        "company_id": data.company_id,
        "trade_id": data.trade_id,
        "headcount": data.headcount,
        "qualifications": data.qualifications.strip(),
        "start_date": data.start_date,
        "end_date": data.end_date,
        "shift": data.shift.strip(),
        "priority": data.priority,
        "justification": data.justification.strip(),
    }


def add_request(db, user, project, data):
    key = _check_request(db, project, data)
    row = WorkforceRequest(
        organization_id=project.organization_id,
        project_id=project.id,
        number_key=key,
        requested_by=user.id,
        created_by=user.id,
        modified_by=user.id,
        **_request_values(db, data),
    )
    db.add(row)
    db.flush()
    return row


def save_request(db, user, project, row, data):
    if row.status not in REQUEST_EDITABLE:
        raise HTTPException(409, "Only a draft or returned request can be edited")
    if user.id != row.requested_by and not user.organization_admin:
        raise HTTPException(403, "Only the requesting engineer can edit this request")
    key = _check_request(db, project, data, current=row)
    _bump(
        db,
        WorkforceRequest,
        row,
        data.version,
        {**_request_values(db, data), "number_key": key, "modified_by": user.id, "modified_at": now()},
    )
    return row


def submit_request(db, user, project, row, version):
    if row.status != "Draft":
        raise HTTPException(409, "Only a draft request can be submitted")
    if user.id != row.requested_by and not user.organization_admin:
        raise HTTPException(403, "Only the requesting engineer can submit this request")
    policy = _policy_for(db, project, REQUEST, row.company_id, row.discipline_id)
    _bump(db, WorkforceRequest, row, version, {"status": "Pending Review", "modified_by": user.id, "modified_at": now()})
    return submit_record(db, user, project, REQUEST, row.id, row.version, policy)


def _counts(db, row):
    lines = db.query(RequestLine).filter_by(request_id=row.id).all()
    allocated = sum(1 for line in lines if line.state == "Allocated")
    proposed = sum(1 for line in lines if line.state == "Proposed")
    return {
        "required": row.headcount,
        "proposed": proposed,
        "allocated": allocated,
        "shortfall": max(0, row.headcount - allocated),
    }


def _settle(db, row):
    if row.status not in REQUEST_ALLOCATING:
        return
    allocated = _counts(db, row)["allocated"]
    target = "Open" if allocated == 0 else "Allocated" if allocated >= row.headcount else "Partially Allocated"
    if target != row.status:
        row.status = target
        row.version += 1
        row.modified_at = now()


def save_line(db, user, project, row, data):
    if row.status not in REQUEST_ALLOCATING:
        raise HTTPException(409, "People are proposed after the request is approved")
    if data.state not in {"Proposed", "Allocated", "Released"}:
        raise HTTPException(422, "Choose Proposed, Allocated, or Released")
    person = _person(db, project, data.personnel_id)
    if person.trade_id != row.trade_id:
        raise HTTPException(422, "This person's trade does not match the request")
    if person.status != "Active" and data.state != "Released":
        raise HTTPException(422, "Only an active person can be proposed or allocated")
    deployment = None
    if data.state == "Allocated":
        deployment = db.get(Deployment, data.deployment_id) if data.deployment_id else None
        if not deployment or deployment.project_id != project.id or deployment.personnel_id != person.id:
            raise HTTPException(422, "Allocate through this person's deployment on this project")
        if deployment.status not in ON_SITE:
            raise HTTPException(409, "Allocate only a deployment that is approved for mobilization or mobilized")
        if not _overlaps(row.start_date, row.end_date, deployment.planned_start, deployment.planned_end):
            raise HTTPException(422, "The deployment dates do not cover the requested dates")
        busy = (
            db.query(RequestLine)
            .join(WorkforceRequest, WorkforceRequest.id == RequestLine.request_id)
            .filter(
                RequestLine.personnel_id == person.id,
                RequestLine.state == "Allocated",
                RequestLine.request_id != row.id,
                WorkforceRequest.project_id == project.id,
            )
            .all()
        )
        for line in busy:
            other = db.get(WorkforceRequest, line.request_id)
            if other and _overlaps(row.start_date, row.end_date, other.start_date, other.end_date):
                raise HTTPException(409, f"This person is already allocated to request {other.number} for those dates")
    _bump(db, WorkforceRequest, row, data.version, {"modified_by": user.id, "modified_at": now()})
    line = db.query(RequestLine).filter_by(request_id=row.id, personnel_id=person.id).first()
    if line is None:
        if data.state == "Released":
            raise HTTPException(409, "This person is not on the request")
        line = RequestLine(request_id=row.id, personnel_id=person.id, created_by=user.id)
        db.add(line)
    line.state = data.state
    line.deployment_id = deployment.id if deployment else (line.deployment_id if data.state == "Released" else None)
    line.modified_at = now()
    db.flush()
    _settle(db, row)
    db.flush()
    _shortfall_alert(db, project, row)
    return row


def _shortfall_alert(db, project, row):
    counts = _counts(db, row)
    if counts["shortfall"] == 0 or row.start_date > date.today() + timedelta(days=7):
        return
    from app.domains.coordination.jobs import notify

    requester = db.get(User, row.requested_by)
    if requester and requester.active:
        notify(
            db,
            requester,
            "Workforce shortfall",
            f"Request {row.number} still needs {counts['shortfall']} of {counts['required']} people.",
            f"hr:request:{row.id}:shortfall:{counts['shortfall']}",
            project_id=project.id,
            link=f"/projects/{project.id}",
        )


def forecast_request(db, user, project, row, data):
    if row.status not in REQUEST_ALLOCATING:
        raise HTTPException(409, "Record the forecast after the request is approved")
    _bump(
        db,
        WorkforceRequest,
        row,
        data.version,
        {"expected_mobilization": data.expected_mobilization, "modified_by": user.id, "modified_at": now()},
    )
    return row


def close_request(db, user, project, row, data):
    if data.action == "close":
        if row.status not in REQUEST_ALLOCATING:
            raise HTTPException(409, "Only an approved request can be closed")
        target = "Closed"
    elif data.action == "cancel":
        if row.status not in {"Draft", "Returned", *REQUEST_ALLOCATING}:
            raise HTTPException(409, "This request can no longer be cancelled")
        if user.id != row.requested_by and not (
            holds(db, user, project, "hr.edit") or holds(db, user, project, "manpower.coordinate")
        ):
            raise HTTPException(403, "Only the requester, HR, or a manpower coordinator can cancel this request")
        target = "Cancelled"
    else:
        raise HTTPException(422, "Choose close or cancel")
    _bump(
        db,
        WorkforceRequest,
        row,
        data.version,
        {"status": target, "status_reason": data.reason.strip(), "modified_by": user.id, "modified_at": now()},
    )
    for line in db.query(RequestLine).filter_by(request_id=row.id).filter(RequestLine.state != "Released"):
        line.state = "Released"
        line.modified_at = now()
    return row


# Views


def _latest_review(db, project, record_type, record_id):
    from app.domains.coordination.models import ReviewInstance

    return (
        db.query(ReviewInstance)
        .filter_by(project_id=project.id, record_type=record_type, record_id=record_id)
        .order_by(ReviewInstance.id.desc())
        .first()
    )


def _review_view(db, user, project, record_type, record_id):
    from app.domains.coordination.service import review_payload

    instance = _latest_review(db, project, record_type, record_id)
    return review_payload(db, user, instance) if instance else None


def deployment_view(db, user, project, row, names):
    person = db.get(Personnel, row.personnel_id)
    boss = db.get(Personnel, row.supervisor_id) if row.supervisor_id else None
    area = db.get(Area, row.area_id) if row.area_id else None
    checks = _checks(db, row)
    verifiers = {check.verified_by: db.get(User, check.verified_by) for check in checks if check.verified_by}
    flagged = (
        db.query(RequestLine).filter_by(deployment_id=row.id, state="Allocated").count()
        if row.status == "Temporarily Unavailable"
        else 0
    )
    return {
        "id": row.id,
        "personnel_id": row.personnel_id,
        "person": f"{person.code} · {person.full_name}" if person else "",
        "trade_id": person.trade_id if person else None,
        "company_id": row.company_id,
        "company_name": names["company"].get(row.company_id, ""),
        "discipline_id": row.discipline_id,
        "discipline": names["discipline"].get(row.discipline_id, "") if row.discipline_id else "",
        "supervisor_id": row.supervisor_id,
        "supervisor_name": boss.full_name if boss else "",
        "area_id": row.area_id,
        "area": f"{area.code} · {area.name}" if area else "",
        "planned_start": row.planned_start.isoformat(),
        "planned_end": row.planned_end.isoformat() if row.planned_end else None,
        "actual_start": row.actual_start.isoformat() if row.actual_start else None,
        "actual_end": row.actual_end.isoformat() if row.actual_end else None,
        "shift": row.shift,
        "required_skills": row.required_skills,
        "status": row.status,
        "status_reason": row.status_reason,
        "flagged_allocations": flagged,
        "version": row.version,
        "checks": [
            {
                "id": check.id,
                "check_type": check.check_type,
                "owner": check.owner,
                "status": check.status,
                "evidence": check.evidence,
                "verified_by": verifiers[check.verified_by].name if check.verified_by and verifiers.get(check.verified_by) else "",
                "can_verify": row.status in {"Proposed", "Pending Approval"} and _may_verify(db, user, project, check.owner),
                "version": check.version,
            }
            for check in checks
        ],
        "review": _review_view(db, user, project, DEPLOYMENT, row.id),
    }


def request_view(db, user, project, row, names):
    lines = db.query(RequestLine).filter_by(request_id=row.id).order_by(RequestLine.id).all()
    requester = db.get(User, row.requested_by)
    area = db.get(Area, row.area_id) if row.area_id else None
    package = activity = None
    if row.package_id or row.activity_id:
        from app.domains.construction.models import ConstructionActivity, WorkPackage

        package = db.get(WorkPackage, row.package_id) if row.package_id else None
        activity = db.get(ConstructionActivity, row.activity_id) if row.activity_id else None
    people = []
    for line in lines:
        person = db.get(Personnel, line.personnel_id)
        people.append(
            {
                "id": line.id,
                "personnel_id": line.personnel_id,
                "person": f"{person.code} · {person.full_name}" if person else "",
                "state": line.state,
                "deployment_id": line.deployment_id,
            }
        )
    return {
        "id": row.id,
        "number": row.number,
        "discipline_id": row.discipline_id,
        "discipline": names["discipline"].get(row.discipline_id, "") if row.discipline_id else "",
        "area_id": row.area_id,
        "area": f"{area.code} · {area.name}" if area else "",
        "package_id": row.package_id,
        "package": package.code if package else "",
        "activity_id": row.activity_id,
        "activity": activity.code if activity else "",
        "company_id": row.company_id,
        "company_name": names["company"].get(row.company_id, ""),
        "trade_id": row.trade_id,
        "trade": names["master"].get(row.trade_id, ""),
        "grade_id": row.grade_id,
        "grade": names["master"].get(row.grade_id, "") if row.grade_id else "",
        "headcount": row.headcount,
        "required_hours": row.required_hours,
        "required_mobilization": row.required_mobilization.isoformat() if row.required_mobilization else None,
        "qualifications": row.qualifications,
        "start_date": row.start_date.isoformat(),
        "end_date": row.end_date.isoformat() if row.end_date else None,
        "shift": row.shift,
        "priority": row.priority,
        "requested_by": row.requested_by,
        "requester": requester.name if requester else "",
        "justification": row.justification,
        "expected_mobilization": row.expected_mobilization.isoformat() if row.expected_mobilization else None,
        "status": row.status,
        "status_reason": row.status_reason,
        "counts": _counts(db, row),
        "lines": people,
        "version": row.version,
        "review": _review_view(db, user, project, REQUEST, row.id),
    }


def supplement(db, user, project, payload, names):
    from app.domains.construction.models import WorkPackage
    from app.domains.identity_projects.models import Membership, ProjectDiscipline

    deployments = db.query(Deployment).filter_by(project_id=project.id).order_by(Deployment.planned_start.desc(), Deployment.id.desc()).all()
    requests = db.query(WorkforceRequest).filter_by(project_id=project.id).order_by(WorkforceRequest.id.desc()).all()
    today = date.today()
    soon = today + timedelta(days=14)
    deployed = {row.personnel_id for row in deployments if row.status == "Mobilized"}
    payload["deployments"] = [deployment_view(db, user, project, row, names) for row in deployments]
    payload["requests"] = [request_view(db, user, project, row, names) for row in requests]
    payload["deployment_note"] = DEPLOYMENT_NOTE
    payload["request_note"] = REQUEST_NOTE
    payload["check_types"] = [{"name": name, "owner": CHECK_OWNER[name]} for name in CHECK_TYPES]
    payload["priorities"] = list(PRIORITIES)
    payload["areas"] = [
        {"id": row.id, "name": f"{row.code} · {row.name}"}
        for row in db.query(Area).filter_by(project_id=project.id).order_by(Area.code)
    ]
    payload["packages"] = [
        {"id": row.id, "name": row.code}
        for row in db.query(WorkPackage).filter_by(project_id=project.id).order_by(WorkPackage.code)
    ]
    enabled = {row.discipline_id for row in db.query(ProjectDiscipline).filter_by(project_id=project.id, active=True)}
    payload["project_disciplines"] = [row for row in payload["disciplines"] if row["id"] in enabled]
    seen = set()
    members = []
    for member in db.query(Membership).filter_by(project_id=project.id, active=True):
        person = db.get(User, member.user_id)
        if person and person.active and person.id not in seen:
            seen.add(person.id)
            members.append({"id": person.id, "name": person.name})
    payload["members"] = members
    payload["can_request"] = holds(db, user, project, "hr.request")
    open_requests = [row for row in payload["requests"] if row["status"] in REQUEST_ALLOCATING]
    payload["counts"].update(
        {
            "deployed": len(deployed),
            "pending_onboarding": sum(
                1 for row in payload["deployments"] if row["status"] == "Proposed" and any(c["status"] == "Pending" for c in row["checks"])
            ),
            "pending_approval": sum(1 for row in deployments if row.status == "Pending Approval"),
            "unavailable": len({row.personnel_id for row in deployments if row.status == "Temporarily Unavailable"}),
            "open_requests": len(open_requests),
            "shortfall": sum(row["counts"]["shortfall"] for row in open_requests),
            "allocated": sum(row["counts"]["allocated"] for row in open_requests),
        }
    )
    payload["upcoming_mobilizations"] = [
        row
        for row in payload["deployments"]
        if row["status"] in {"Proposed", "Pending Approval", "Approved for Mobilization"}
        and today.isoformat() <= row["planned_start"] <= soon.isoformat()
    ]
    payload["upcoming_demobilizations"] = [
        row
        for row in payload["deployments"]
        if row["status"] in {"Mobilized", "Temporarily Unavailable"}
        and row["planned_end"]
        and today.isoformat() <= row["planned_end"] <= soon.isoformat()
    ]
    payload["deployed_note"] = (
        f"Deployed counts distinct people with a mobilized deployment on {today.isoformat()}. "
        "It is not attendance, availability, or task eligibility."
    )
    return payload
