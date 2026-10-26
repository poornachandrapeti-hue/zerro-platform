"""HSE controlled references and risk assessments.

An approved assessment records the hazards and controls. It does not authorize
work, open a permit, or release a safety hold.
"""

from fastapi import HTTPException
from sqlalchemy import update

from app.domains.construction.models import ConstructionActivity, WorkPackage
from app.domains.coordination.jobs import notify
from app.domains.coordination.service import REVIEW_GUARDS, review_payload
from app.domains.engineering_documents.workflow import submit_record
from app.domains.identity_projects.models import Area, Company, Discipline, Membership, ProjectCompany, ProjectDiscipline, Role, User
from app.domains.identity_projects.security import holds
from app.domains.supply_chain.service import _authority, _policy, _project_member

from .models import DOCUMENT_KINDS, HseAssessment, HseDocument, now

DOCUMENT = "hse.document"
ASSESSMENT = "hse.assessment"
DOCUMENT_STATEMENT = (
    "This reference records HSE applicability. Engineering and Document Control own the controlled file. "
    "Approval does not authorize work."
)
ASSESSMENT_STATEMENT = "Approval of this assessment does not authorize work."
RATING_NOTE = "Risk ratings are recorded as written in the approved project procedure. This application does not apply a risk threshold."
EDITABLE = {"Draft", "Returned for Correction"}
WATCH = {"HSE", "Site Engineer", "Supervisor", "Construction Manager", "Discipline Head", "Project Manager"}


def _bump(db, model, row, version, values):
    changed = db.execute(
        update(model).where(model.id == row.id, model.version == version).values(version=version + 1, modified_at=now(), **values)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This record changed. Reload it and try again")
    db.refresh(row)


def _member(db, project, user_id, label):
    person = db.get(User, user_id)
    if not _project_member(db, project, person):
        raise HTTPException(422, f"Choose an active project member as the {label}")
    return person


def _company(db, project, company_id):
    company = db.get(Company, company_id)
    if not company or company.organization_id != project.organization_id:
        raise HTTPException(422, "Choose a company on this project")
    link = db.query(ProjectCompany).filter_by(project_id=project.id, company_id=company_id, active=True).first()
    if not link and project.client_company_id != company_id:
        raise HTTPException(422, "Choose a company on this project")
    return company


def _discipline(db, project, discipline_id):
    if not discipline_id:
        return None
    row = db.query(ProjectDiscipline).filter_by(project_id=project.id, discipline_id=discipline_id, active=True).first()
    if not row:
        raise HTTPException(422, "Discipline is not active on this project")
    return row


def _area(db, project, area_id):
    if not area_id:
        return None
    row = db.get(Area, area_id)
    if not row or row.project_id != project.id:
        raise HTTPException(422, "Choose an area on this project")
    return row


def _package(db, project, package_id):
    if not package_id:
        return None
    row = db.get(WorkPackage, package_id)
    if not row or row.project_id != project.id:
        raise HTTPException(422, "Choose a work package on this project")
    return row


def _activity(db, package, activity_id):
    if not activity_id:
        return None
    if not package:
        raise HTTPException(422, "Choose the work package before the activity")
    row = db.get(ConstructionActivity, activity_id)
    if not row or row.package_id != package.id:
        raise HTTPException(422, "Choose an activity on that work package")
    return row


def _policy_for(db, project, record_type, company_id, discipline_id):
    policy = _policy(db, project, record_type, company_id, discipline_id)
    if not policy:
        raise HTTPException(422, "Mandatory reviewer configuration is missing")
    _authority(db, project, policy)
    return policy


def _latest(db, project, record_type, record_id):
    from app.domains.coordination.models import ReviewInstance

    return (
        db.query(ReviewInstance)
        .filter_by(project_id=project.id, record_type=record_type, record_id=record_id)
        .order_by(ReviewInstance.id.desc())
        .first()
    )


def _watchers(db, project):
    people = []
    seen = set()
    for member in db.query(Membership).filter_by(project_id=project.id, active=True):
        if member.user_id in seen:
            continue
        person = db.get(User, member.user_id)
        role = db.get(Role, member.role_id)
        if person and person.active and role and role.name in WATCH:
            seen.add(person.id)
            people.append(person)
    return people


def _tell(db, project, people, title, body, source_key):
    for person in people:
        notify(db, person, title, body, source_key, project_id=project.id, link=f"/projects/{project.id}")


def _document_snapshot(row):
    return {
        "kind": row.kind,
        "number": row.number,
        "title": row.title,
        "revision_label": row.revision_label,
        "discipline_id": row.discipline_id,
        "company_id": row.company_id,
        "area_id": row.area_id,
        "owner_id": row.owner_id,
        "effective_from": row.effective_from.isoformat() if row.effective_from else None,
        "effective_to": row.effective_to.isoformat() if row.effective_to else None,
        "applicability": row.applicability,
        "engineering_reference": row.engineering_reference,
        "statement": DOCUMENT_STATEMENT,
    }


def _assessment_snapshot(db, row):
    document = db.get(HseDocument, row.document_id) if row.document_id else None
    return {
        "number": row.number,
        "company_id": row.company_id,
        "discipline_id": row.discipline_id,
        "area_id": row.area_id,
        "package_id": row.package_id,
        "activity_id": row.activity_id,
        "task_description": row.task_description,
        "steps": row.steps,
        "hazards": row.hazards,
        "exposed": row.exposed,
        "existing_controls": row.existing_controls,
        "initial_rating": row.initial_rating,
        "additional_controls": row.additional_controls,
        "residual_rating": row.residual_rating,
        "control_owners": row.control_owners,
        "required_permits": row.required_permits,
        "required_competencies": row.required_competencies,
        "prepared_by": row.prepared_by,
        "review_on": row.review_on.isoformat() if row.review_on else None,
        "document": (
            {"id": document.id, "number": document.number, "revision_label": document.revision_label, "kind": document.kind}
            if document
            else None
        ),
        "supersedes_id": row.supersedes_id,
        "statement": ASSESSMENT_STATEMENT,
        "rating_note": RATING_NOTE,
    }


def document_view(db, user, project, row):
    instance = _latest(db, project, DOCUMENT, row.id)
    owner = db.get(User, row.owner_id)
    return {
        "id": row.id,
        "kind": row.kind,
        "number": row.number,
        "title": row.title,
        "revision_label": row.revision_label,
        "discipline_id": row.discipline_id,
        "company_id": row.company_id,
        "area_id": row.area_id,
        "owner_id": row.owner_id,
        "owner_name": owner.name if owner else "",
        "status": row.status,
        "effective_from": row.effective_from.isoformat() if row.effective_from else None,
        "effective_to": row.effective_to.isoformat() if row.effective_to else None,
        "applicability": row.applicability,
        "engineering_reference": row.engineering_reference,
        "statement": row.statement or DOCUMENT_STATEMENT,
        "withdrawal_reason": row.withdrawal_reason,
        "version": row.version,
        "review": review_payload(db, user, instance) if instance and instance.state in {"In Review", "Returned"} else None,
    }


def assessment_view(db, user, project, row):
    instance = _latest(db, project, ASSESSMENT, row.id)
    package = db.get(WorkPackage, row.package_id) if row.package_id else None
    activity = db.get(ConstructionActivity, row.activity_id) if row.activity_id else None
    document = db.get(HseDocument, row.document_id) if row.document_id else None
    preparer = db.get(User, row.prepared_by)
    return {
        "id": row.id,
        "number": row.number,
        "company_id": row.company_id,
        "discipline_id": row.discipline_id,
        "area_id": row.area_id,
        "package_id": row.package_id,
        "package_code": package.code if package else "",
        "package_status": package.status if package else "",
        "activity_id": row.activity_id,
        "activity_code": activity.code if activity else "",
        "document_id": row.document_id,
        "document_label": f"{document.number} rev {document.revision_label}" if document else "",
        "supersedes_id": row.supersedes_id,
        "task_description": row.task_description,
        "steps": row.steps,
        "hazards": row.hazards,
        "exposed": row.exposed,
        "existing_controls": row.existing_controls,
        "initial_rating": row.initial_rating,
        "additional_controls": row.additional_controls,
        "residual_rating": row.residual_rating,
        "control_owners": row.control_owners,
        "required_permits": row.required_permits,
        "required_competencies": row.required_competencies,
        "prepared_by": row.prepared_by,
        "prepared_name": preparer.name if preparer else "",
        "review_on": row.review_on.isoformat() if row.review_on else None,
        "status": row.status,
        "statement": row.statement or ASSESSMENT_STATEMENT,
        "withdrawal_reason": row.withdrawal_reason,
        "rating_note": RATING_NOTE,
        "version": row.version,
        "review": review_payload(db, user, instance) if instance and instance.state in {"In Review", "Returned"} else None,
    }


def _context(db, project):
    companies = []
    seen = set()
    for link in db.query(ProjectCompany).filter_by(project_id=project.id, active=True):
        company = db.get(Company, link.company_id)
        if company and company.id not in seen:
            seen.add(company.id)
            companies.append({"id": company.id, "name": company.name})
    if project.client_company_id and project.client_company_id not in seen:
        client = db.get(Company, project.client_company_id)
        if client:
            companies.append({"id": client.id, "name": client.name})
    disciplines = []
    for link in db.query(ProjectDiscipline).filter_by(project_id=project.id, active=True):
        discipline = db.get(Discipline, link.discipline_id)
        if discipline:
            disciplines.append({"id": discipline.id, "name": discipline.name})
    areas = [{"id": row.id, "name": f"{row.code} · {row.name}"} for row in db.query(Area).filter_by(project_id=project.id)]
    packages = [
        {"id": row.id, "code": row.code, "status": row.status, "discipline_id": row.discipline_id}
        for row in db.query(WorkPackage).filter_by(project_id=project.id).order_by(WorkPackage.id)
    ]
    activities = []
    for package in db.query(WorkPackage).filter_by(project_id=project.id):
        for activity in db.query(ConstructionActivity).filter_by(package_id=package.id):
            activities.append({"id": activity.id, "package_id": package.id, "code": activity.code, "name": activity.name})
    people = []
    seen_people = set()
    for member in db.query(Membership).filter_by(project_id=project.id, active=True):
        if member.user_id in seen_people:
            continue
        person = db.get(User, member.user_id)
        if person and person.active:
            seen_people.add(person.id)
            people.append({"id": person.id, "name": person.name})
    return {
        "companies": companies,
        "disciplines": disciplines,
        "areas": areas,
        "packages": packages,
        "activities": activities,
        "members": people,
        "kinds": list(DOCUMENT_KINDS),
    }


def board(db, user, project):
    documents = db.query(HseDocument).filter_by(project_id=project.id).order_by(HseDocument.id.desc()).all()
    assessments = db.query(HseAssessment).filter_by(project_id=project.id).order_by(HseAssessment.id.desc()).all()
    payload = {
        "note": ASSESSMENT_STATEMENT,
        "rating_note": RATING_NOTE,
        "document_statement": DOCUMENT_STATEMENT,
        "counts": {
            "documents": len(documents),
            "approved_documents": sum(row.status == "Approved" for row in documents),
            "assessments": len(assessments),
            "pending_assessments": sum(row.status == "Pending Review" for row in assessments),
            "approved_assessments": sum(row.status == "Approved" for row in assessments),
        },
        "documents": [document_view(db, user, project, row) for row in documents],
        "assessments": [assessment_view(db, user, project, row) for row in assessments],
        **_context(db, project),
    }
    from .permits import supplement

    payload = supplement(db, user, project, payload)
    from .field import supplement as field_supplement

    payload = field_supplement(db, user, project, payload)
    from .incidents import supplement as incident_supplement

    payload = incident_supplement(db, user, project, payload)
    from .holds import supplement as hold_supplement

    payload = hold_supplement(db, user, project, payload)
    from .emergency import supplement as emergency_supplement

    payload = emergency_supplement(db, user, project, payload)
    from .environment import supplement as environment_supplement

    payload = environment_supplement(db, user, project, payload)
    from .dashboard import view as dashboard_view

    payload["dashboard"] = dashboard_view(db, project)
    return payload


def work_view(db, project, package_id):
    package = _package(db, project, package_id)
    if not package:
        raise HTTPException(422, "Choose a work package")
    rows = (
        db.query(HseAssessment)
        .filter_by(project_id=project.id, package_id=package.id)
        .order_by(HseAssessment.id.desc())
        .all()
    )
    from .field import work_note
    from .emergency import work_line as emergency_line
    from .environment import work_line as environment_line
    from .holds import hold_block
    from .incidents import work_line
    from .permits import work_permits

    return {
        "package_id": package.id,
        "package_status": package.status,
        "note": ASSESSMENT_STATEMENT,
        "assessments": [{"id": row.id, "number": row.number, "status": row.status} for row in rows],
        **work_permits(db, project, package),
        **work_note(db, package),
        **work_line(),
        **emergency_line(),
        **environment_line(),
        "hold_block": hold_block(db, package),
    }


def add_document(db, user, project, data):
    if data.kind not in DOCUMENT_KINDS:
        raise HTTPException(422, "Choose an HSE document kind")
    if data.effective_from and data.effective_to and data.effective_to < data.effective_from:
        raise HTTPException(422, "The effective end is before the effective start")
    _company(db, project, data.company_id)
    _discipline(db, project, data.discipline_id)
    _area(db, project, data.area_id)
    _member(db, project, data.owner_id, "owner")
    number_key = data.number.strip().casefold()
    revision_key = data.revision_label.strip().casefold()
    if (
        db.query(HseDocument)
        .filter_by(project_id=project.id, kind=data.kind, number_key=number_key, revision_key=revision_key)
        .first()
    ):
        raise HTTPException(409, "That document revision already exists")
    row = HseDocument(
        organization_id=project.organization_id,
        project_id=project.id,
        kind=data.kind,
        number=data.number.strip(),
        number_key=number_key,
        title=data.title.strip(),
        revision_label=data.revision_label.strip(),
        revision_key=revision_key,
        discipline_id=data.discipline_id,
        company_id=data.company_id,
        area_id=data.area_id,
        owner_id=data.owner_id,
        effective_from=data.effective_from,
        effective_to=data.effective_to,
        applicability=data.applicability.strip(),
        engineering_reference=data.engineering_reference.strip(),
        statement=DOCUMENT_STATEMENT,
        payload={},
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def submit_document(db, user, project, row, version):
    if row.status == "Returned for Correction":
        raise HTTPException(409, "A returned HSE document is resubmitted, not submitted again")
    if row.status != "Draft":
        raise HTTPException(409, "Only a draft HSE document can be submitted")
    policy = _policy_for(db, project, DOCUMENT, row.company_id, row.discipline_id)
    _bump(db, HseDocument, row, version, {"status": "Pending Review", "payload": _document_snapshot(row), "modified_by": user.id})
    return submit_record(db, user, project, DOCUMENT, row.id, row.version, policy)


def withdraw_document(db, user, project, row, data):
    if row.status != "Approved":
        raise HTTPException(409, "Only an approved HSE document can be withdrawn")
    _bump(db, HseDocument, row, data.version, {"status": "Withdrawn", "withdrawal_reason": data.reason.strip(), "modified_by": user.id})
    return row


def add_assessment(db, user, project, data, supersedes_id=None):
    _company(db, project, data.company_id)
    _discipline(db, project, data.discipline_id)
    _area(db, project, data.area_id)
    package = _package(db, project, data.package_id)
    _activity(db, package, data.activity_id)
    _member(db, project, data.prepared_by, "preparer")
    document = None
    if data.document_id:
        document = db.get(HseDocument, data.document_id)
        if not document or document.project_id != project.id or document.status != "Approved":
            raise HTTPException(422, "Choose an approved HSE document")
    number_key = data.number.strip().casefold()
    if db.query(HseAssessment).filter_by(project_id=project.id, number_key=number_key).first():
        raise HTTPException(409, "That assessment number already exists")
    row = HseAssessment(
        organization_id=project.organization_id,
        project_id=project.id,
        number=data.number.strip(),
        number_key=number_key,
        company_id=data.company_id,
        discipline_id=data.discipline_id,
        area_id=data.area_id,
        package_id=data.package_id,
        activity_id=data.activity_id,
        document_id=document.id if document else None,
        supersedes_id=supersedes_id,
        task_description=data.task_description.strip(),
        steps=data.steps.strip(),
        hazards=data.hazards.strip(),
        exposed=data.exposed.strip(),
        existing_controls=data.existing_controls.strip(),
        initial_rating=data.initial_rating.strip(),
        additional_controls=data.additional_controls.strip(),
        residual_rating=data.residual_rating.strip(),
        control_owners=data.control_owners.strip(),
        required_permits=data.required_permits.strip(),
        required_competencies=data.required_competencies.strip(),
        prepared_by=data.prepared_by,
        review_on=data.review_on,
        statement=ASSESSMENT_STATEMENT,
        payload={},
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def submit_assessment(db, user, project, row, version):
    if row.status == "Returned for Correction":
        raise HTTPException(409, "A returned assessment is resubmitted, not submitted again")
    if row.status != "Draft":
        raise HTTPException(409, "Only a draft assessment can be submitted")
    if row.document_id:
        document = db.get(HseDocument, row.document_id)
        if not document or document.status != "Approved":
            raise HTTPException(422, "The linked HSE document is no longer approved")
    policy = _policy_for(db, project, ASSESSMENT, row.company_id, row.discipline_id)
    _bump(db, HseAssessment, row, version, {"status": "Pending Review", "payload": _assessment_snapshot(db, row), "modified_by": user.id})
    return submit_record(db, user, project, ASSESSMENT, row.id, row.version, policy)


def reassess(db, user, project, row, data):
    if row.status != "Approved":
        raise HTTPException(409, "Reassessment starts from an approved assessment")
    if row.version != data.version:
        raise HTTPException(409, "This record changed. Reload it and try again")
    from .schemas import AssessmentIn

    copy = AssessmentIn(
        number=data.number,
        company_id=row.company_id,
        discipline_id=row.discipline_id,
        area_id=row.area_id,
        package_id=row.package_id,
        activity_id=row.activity_id,
        document_id=row.document_id,
        task_description=row.task_description,
        steps=row.steps,
        hazards=row.hazards,
        exposed=row.exposed,
        existing_controls=row.existing_controls,
        initial_rating=row.initial_rating,
        additional_controls=row.additional_controls,
        residual_rating=row.residual_rating,
        control_owners=row.control_owners,
        required_permits=row.required_permits,
        required_competencies=row.required_competencies,
        prepared_by=row.prepared_by,
        review_on=row.review_on,
    )
    return add_assessment(db, user, project, copy, supersedes_id=row.id)


def withdraw_assessment(db, user, project, row, data):
    if row.status != "Approved":
        raise HTTPException(409, "Only an approved assessment can be withdrawn")
    _bump(db, HseAssessment, row, data.version, {"status": "Withdrawn", "withdrawal_reason": data.reason.strip(), "modified_by": user.id})
    return row


def _resubmit_row(db, user, project, instance, review_version, model, record_type):
    from app.domains.coordination.service import _close_tasks, _lock, _open_stage, current_stage

    if instance.state != "Returned":
        raise HTTPException(409, "Only a returned review can be resubmitted")
    if user.id != instance.submitted_by and not user.organization_admin:
        raise HTTPException(403, "Only the submitter can resubmit")
    if not (holds(db, user, project, "hse.plan") or holds(db, user, project, "hse.edit")):
        from app.domains.identity_projects.security import permitted

        permitted(db, user, project, "hse.plan")
    row = db.get(model, instance.record_id)
    if not row or row.project_id != project.id or row.status != "Returned for Correction":
        raise HTTPException(409, "Only a returned record can be resubmitted")
    policy = _policy_for(db, project, record_type, row.company_id, row.discipline_id)
    payload = _document_snapshot(row) if record_type == DOCUMENT else _assessment_snapshot(db, row)
    _lock(db, instance, review_version)
    _close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    _bump(db, model, row, row.version, {"status": "Pending Review", "payload": payload, "modified_by": user.id})
    instance.record_version = row.version
    instance.policy_id = policy.id
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def apply_resubmit(db, user, instance, review_version):
    from app.domains.identity_projects.models import Project

    if instance.record_type not in {DOCUMENT, ASSESSMENT}:
        return
    project = db.get(Project, instance.project_id)
    if not project:
        raise HTTPException(404, "HSE record not found")
    model = HseDocument if instance.record_type == DOCUMENT else HseAssessment
    return _resubmit_row(db, user, project, instance, review_version, model, instance.record_type)


def on_review_event(db, user, instance, project, action, stage=None):
    if instance.record_type == DOCUMENT:
        row = db.get(HseDocument, instance.record_id)
    elif instance.record_type == ASSESSMENT:
        row = db.get(HseAssessment, instance.record_id)
    else:
        return
    if not row or row.project_id != project.id:
        return
    if action == "advance":
        return
    if action == "return":
        row.status = "Returned for Correction"
    elif action == "reject":
        row.status = "Rejected"
    elif instance.state == "Approved":
        row.status = "Approved"
        if isinstance(row, HseDocument):
            others = (
                db.query(HseDocument)
                .filter_by(project_id=project.id, kind=row.kind, number_key=row.number_key, status="Approved")
                .all()
            )
            for other in others:
                if other.id != row.id:
                    other.status = "Superseded"
                    other.modified_at = now()
            _tell(db, project, _watchers(db, project), "HSE document approved", f"{row.number} rev {row.revision_label} is approved for HSE use. This does not authorize work.", f"hse.document.{row.id}")
        else:
            if row.supersedes_id:
                previous = db.get(HseAssessment, row.supersedes_id)
                if previous and previous.project_id == project.id and previous.status == "Approved":
                    previous.status = "Superseded"
                    previous.modified_at = now()
            package = db.get(WorkPackage, row.package_id) if row.package_id else None
            _tell(
                db,
                project,
                _watchers(db, project),
                "Risk assessment approved",
                f"{row.number} is approved. This does not authorize work."
                + (f" Work package {package.code} stays {package.status}." if package else ""),
                f"hse.assessment.{row.id}",
            )
    else:
        return
    row.version += 1
    row.modified_by = user.id
    row.modified_at = now()


def review_guard(db, user, instance, stage, action):
    if action != "approve":
        return
    if instance.record_type in {DOCUMENT, ASSESSMENT, "hse.permit", "hse.incident", "hse.hold"}:
        if user.id == instance.submitted_by:
            raise HTTPException(403, "You cannot approve your own submission")
    if instance.record_type == "hse.hold":
        from .holds import release_guard

        release_guard(db, user, instance)


if review_guard not in REVIEW_GUARDS:
    REVIEW_GUARDS.append(review_guard)
