"""Quality plans, ITPs, and discipline inspection templates.

QA/QC records which approved document applies to an inspection. Engineering
keeps the controlled file. A saved reviewer approves the quality record.
Later edits create a new revision and leave the approved snapshot in place.
"""

from fastapi import HTTPException
from sqlalchemy import update

from app.domains.construction.models import ConstructionTemplate
from app.domains.construction.monitoring import _tell
from app.domains.construction.service import _area, _company
from app.domains.coordination.service import REVIEW_GUARDS, review_payload
from app.domains.engineering_documents.workflow import submit_record
from app.domains.identity_projects.models import (
    Company,
    Discipline,
    Membership,
    ProjectDiscipline,
    Role,
    User,
)
from app.domains.identity_projects.security import permitted
from app.domains.supply_chain.service import _authority, _policy

from .models import (
    DOCUMENT_KINDS,
    POINT_TYPES,
    QualityCheckpoint,
    QualityDocument,
    QualityForm,
    now,
)

DOCUMENT = "quality.document"
FORM = "quality.template"
EDITABLE = {"Draft", "Returned for Correction"}
CRITERIA_KINDS = {"ITP", "Inspection Procedure", "Test Procedure", "Acceptance Criteria"}
STATEMENT = (
    "This quality record says which approved project document applies to inspection. "
    "It does not accept work, certify billing, or create a commissioning test."
)
WITNESS = (
    "Witness-point attendance or waiver follows the approved project procedure. "
    "Nonattendance is not acceptance."
)
EXAMPLES = {
    "Civil": [
        "Survey",
        "Excavation",
        "Compaction",
        "Reinforcement",
        "Formwork",
        "Pre-pour",
        "Concrete tests",
        "Piling tests",
    ],
    "Mechanical": [
        "Equipment receipt",
        "Installation",
        "Alignment",
        "Grouting",
        "Torque checks",
        "Performance tests",
    ],
    "Electrical": [
        "Cable installation",
        "Termination",
        "Insulation resistance",
        "Continuity",
        "Earthing tests",
    ],
    "Instrumentation": [
        "Installation",
        "Calibration",
        "Tubing checks",
        "Loop checks",
        "Functional tests",
    ],
    "Piping": [
        "Fit-up",
        "Weld inspection",
        "NDT",
        "Heat treatment",
        "Material verification",
        "Pressure testing",
    ],
}
WATCH = {"QA/QC", "Discipline Head", "Project Manager", "Document Controller"}


def _bump(db, model, row, version, values):
    changed = db.execute(
        update(model)
        .where(model.id == row.id, model.version == version)
        .values(version=version + 1, modified_at=now(), **values)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This quality record changed. Reload it and try again")
    db.refresh(row)


def _editable(row):
    if row.status not in EDITABLE:
        raise HTTPException(409, "An approved quality record is kept. Add a new revision")


def _discipline(db, project, discipline_id, required):
    if discipline_id is None:
        if required:
            raise HTTPException(422, "Choose a discipline enabled on this project")
        return None
    enabled = (
        db.query(ProjectDiscipline)
        .filter_by(project_id=project.id, discipline_id=discipline_id, active=True)
        .first()
    )
    discipline = db.get(Discipline, discipline_id)
    if not enabled or not discipline:
        raise HTTPException(422, "Choose a discipline enabled on this project")
    return discipline


def _templates(db, project, discipline_id, template_ids):
    found = []
    for template_id in template_ids:
        row = db.get(ConstructionTemplate, template_id)
        if not row or row.project_id != project.id or not row.active:
            raise HTTPException(422, "Applicable activity is not on this project")
        if discipline_id and row.discipline_id != discipline_id:
            raise HTTPException(422, "Applicable activity is in another discipline")
        found.append(row)
    return found


def _checkpoints(db, document):
    return (
        db.query(QualityCheckpoint)
        .filter_by(document_id=document.id)
        .order_by(QualityCheckpoint.sequence)
        .all()
    )


def _check_point(point):
    if point.point_type not in POINT_TYPES:
        raise HTTPException(422, "Point type must be Review, Witness, Hold, or Surveillance")
    if point.point_type == "Hold" and len(point.next_release_conditions.strip()) < 3:
        raise HTTPException(422, "A hold point needs the condition for an authorized release")
    if point.point_type == "Witness" and len(point.required_signatories.strip()) < 3:
        raise HTTPException(
            422,
            "A witness point needs the required signatories. Nonattendance is not acceptance",
        )


def _validate_document(db, document):
    points = _checkpoints(db, document)
    if document.kind == "ITP" and not points:
        raise HTTPException(422, "Add the ITP checkpoints before submission")
    if document.kind != "ITP" and points:
        raise HTTPException(422, "Checkpoints belong on an ITP")
    if document.kind != "Project Quality Plan" and not document.discipline_id:
        raise HTTPException(422, "Choose a discipline enabled on this project")
    described = len(document.applicable_activities.strip()) >= 3 or bool(document.template_ids)
    referenced = len(document.engineering_reference.strip()) >= 3
    if document.kind == "ITP" and not described:
        raise HTTPException(422, "Name the activities this ITP applies to")
    if document.kind != "ITP" and not (described or referenced):
        raise HTTPException(422, "Add the engineering reference or the applicable activities")
    for point in points:
        if point.point_type == "Hold" and len(point.next_release_conditions.strip()) < 3:
            raise HTTPException(422, "A hold point needs the condition for an authorized release")
        if point.point_type == "Witness" and len(point.required_signatories.strip()) < 3:
            raise HTTPException(
                422,
                "A witness point needs the required signatories. Nonattendance is not acceptance",
            )


def _criteria(db, project, document_id, required):
    if not document_id:
        if required:
            raise HTTPException(422, "Choose an approved quality document for the acceptance criteria")
        return None
    row = db.get(QualityDocument, document_id)
    if not row or row.project_id != project.id:
        raise HTTPException(422, "Acceptance criteria are not on this project")
    if row.kind not in CRITERIA_KINDS:
        raise HTTPException(422, "Acceptance criteria must be an approved ITP or procedure")
    if required and row.status != "Approved":
        raise HTTPException(422, "Only an approved quality document can be used")
    return row


def _policy_for(db, project, record_type, company_id, discipline_id):
    policy = _policy(db, project, record_type, company_id, discipline_id)
    if not policy:
        raise HTTPException(422, "Mandatory reviewer configuration is missing")
    _authority(db, project, policy)
    return policy


def _latest_review(db, project, record_type, record_id):
    from app.domains.coordination.models import ReviewInstance

    return (
        db.query(ReviewInstance)
        .filter_by(project_id=project.id, record_type=record_type, record_id=record_id)
        .order_by(ReviewInstance.id.desc())
        .first()
    )


def _watchers(db, project):
    rows = (
        db.query(User)
        .join(Membership, Membership.user_id == User.id)
        .join(Role, Role.id == Membership.role_id)
        .filter(
            Membership.project_id == project.id,
            Membership.active.is_(True),
            User.active.is_(True),
            User.organization_id == project.organization_id,
            Role.name.in_(tuple(WATCH)),
        )
        .all()
    )
    return list({person.id: person for person in rows}.values())


def _point_view(point):
    return {
        "id": point.id,
        "sequence": point.sequence,
        "name": point.name,
        "criteria_reference": point.criteria_reference,
        "responsible_parties": point.responsible_parties,
        "point_type": point.point_type,
        "notice_hours": point.notice_hours,
        "required_evidence": point.required_evidence,
        "required_signatories": point.required_signatories,
        "partial_allowed": point.partial_allowed,
        "next_release_conditions": point.next_release_conditions,
    }


def document_view(db, user, project, row):
    instance = _latest_review(db, project, DOCUMENT, row.id)
    company = db.get(Company, row.company_id)
    discipline = db.get(Discipline, row.discipline_id) if row.discipline_id else None
    return {
        "id": row.id,
        "kind": row.kind,
        "number": row.number,
        "title": row.title,
        "revision_label": row.revision_label,
        "discipline_id": row.discipline_id,
        "discipline_name": discipline.name if discipline else "",
        "company_id": row.company_id,
        "company_name": company.name if company else "",
        "area_id": row.area_id,
        "status": row.status,
        "effective_date": row.effective_date.isoformat() if row.effective_date else None,
        "engineering_reference": row.engineering_reference,
        "applicable_activities": row.applicable_activities,
        "template_ids": row.template_ids or [],
        "statement": row.statement,
        "witness_rule": WITNESS if row.kind == "ITP" else "",
        "payload": row.payload or {},
        "checkpoints": [_point_view(point) for point in _checkpoints(db, row)],
        "version": row.version,
        "review": review_payload(db, user, instance) if instance else None,
    }


def form_view(db, user, project, row):
    instance = _latest_review(db, project, FORM, row.id)
    discipline = db.get(Discipline, row.discipline_id)
    criteria = db.get(QualityDocument, row.criteria_document_id) if row.criteria_document_id else None
    return {
        "id": row.id,
        "code": row.code,
        "title": row.title,
        "revision_label": row.revision_label,
        "discipline_id": row.discipline_id,
        "discipline_name": discipline.name if discipline else "",
        "criteria_document_id": row.criteria_document_id,
        "criteria_label": (
            f"{criteria.number} rev {criteria.revision_label}" if criteria else ""
        ),
        "criteria_status": criteria.status if criteria else "",
        "units": row.units,
        "prerequisites": row.prerequisites,
        "required_attachments": row.required_attachments,
        "items": row.items or [],
        "status": row.status,
        "payload": row.payload or {},
        "version": row.version,
        "review": review_payload(db, user, instance) if instance else None,
    }


def register(db, user, project):
    documents = (
        db.query(QualityDocument)
        .filter_by(project_id=project.id)
        .filter(QualityDocument.status != "Cancelled")
        .order_by(QualityDocument.id.desc())
        .all()
    )
    forms = (
        db.query(QualityForm)
        .filter_by(project_id=project.id)
        .filter(QualityForm.status != "Cancelled")
        .order_by(QualityForm.id.desc())
        .all()
    )
    companies = []
    seen = set()
    from app.domains.identity_projects.models import ProjectCompany

    for link in db.query(ProjectCompany).filter_by(project_id=project.id, active=True):
        company = db.get(Company, link.company_id)
        if company and company.id not in seen:
            seen.add(company.id)
            companies.append({"id": company.id, "name": company.name})
    disciplines = []
    for link in db.query(ProjectDiscipline).filter_by(project_id=project.id, active=True):
        discipline = db.get(Discipline, link.discipline_id)
        if discipline:
            disciplines.append({"id": discipline.id, "name": discipline.name})
    return {
        "statement": STATEMENT,
        "witness_rule": WITNESS,
        "documents": [document_view(db, user, project, row) for row in documents],
        "forms": [form_view(db, user, project, row) for row in forms],
        "companies": companies,
        "disciplines": disciplines,
        "examples": [
            {"discipline": name, "inspections": items}
            for name, items in EXAMPLES.items()
        ],
        "counts": {
            "draft_documents": sum(row.status == "Draft" for row in documents),
            "approved_documents": sum(row.status == "Approved" for row in documents),
            "draft_forms": sum(row.status == "Draft" for row in forms),
            "approved_forms": sum(row.status == "Approved" for row in forms),
        },
    }


def add_document(db, user, project, data):
    if data.kind not in DOCUMENT_KINDS:
        raise HTTPException(422, "Choose a quality plan, ITP, procedure, criteria, checklist, or report template")
    _company(db, project, data.company_id)
    if data.area_id:
        _area(db, project, data.area_id)
    _discipline(db, project, data.discipline_id, data.kind != "Project Quality Plan")
    _templates(db, project, data.discipline_id, data.template_ids)
    number_key = data.number.strip().casefold()
    revision_key = data.revision_label.strip().casefold()
    if (
        db.query(QualityDocument)
        .filter_by(project_id=project.id, kind=data.kind, number_key=number_key, revision_key=revision_key)
        .first()
    ):
        raise HTTPException(409, "That document revision already exists on this project")
    row = QualityDocument(
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
        effective_date=data.effective_date,
        engineering_reference=data.engineering_reference.strip(),
        applicable_activities=data.applicable_activities.strip(),
        template_ids=list(data.template_ids),
        statement=STATEMENT,
        payload={},
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def update_document(db, user, project, row, data):
    _editable(row)
    _company(db, project, data.company_id)
    if data.area_id:
        _area(db, project, data.area_id)
    _discipline(db, project, data.discipline_id, row.kind != "Project Quality Plan")
    _templates(db, project, data.discipline_id, data.template_ids)
    _bump(
        db,
        QualityDocument,
        row,
        data.version,
        {
            "title": data.title.strip(),
            "discipline_id": data.discipline_id,
            "company_id": data.company_id,
            "area_id": data.area_id,
            "effective_date": data.effective_date,
            "engineering_reference": data.engineering_reference.strip(),
            "applicable_activities": data.applicable_activities.strip(),
            "template_ids": list(data.template_ids),
            "modified_by": user.id,
        },
    )


def save_checkpoints(db, user, project, row, data):
    _editable(row)
    if row.kind != "ITP":
        raise HTTPException(422, "Checkpoints belong on an ITP")
    sequences = [point.sequence for point in data.checkpoints]
    if len(sequences) != len(set(sequences)):
        raise HTTPException(422, "Each checkpoint needs its own sequence")
    for point in data.checkpoints:
        _check_point(point)
    db.query(QualityCheckpoint).filter_by(document_id=row.id).delete()
    for point in data.checkpoints:
        db.add(
            QualityCheckpoint(
                document_id=row.id,
                sequence=point.sequence,
                name=point.name.strip(),
                criteria_reference=point.criteria_reference.strip(),
                responsible_parties=point.responsible_parties.strip(),
                point_type=point.point_type,
                notice_hours=point.notice_hours,
                required_evidence=point.required_evidence.strip(),
                required_signatories=point.required_signatories.strip(),
                partial_allowed=point.partial_allowed,
                next_release_conditions=point.next_release_conditions.strip(),
            )
        )
    db.flush()
    _bump(db, QualityDocument, row, data.version, {"modified_by": user.id})


def _document_snapshot(db, row):
    return {
        "kind": row.kind,
        "number": row.number,
        "title": row.title,
        "revision_label": row.revision_label,
        "discipline_id": row.discipline_id,
        "company_id": row.company_id,
        "area_id": row.area_id,
        "effective_date": row.effective_date.isoformat() if row.effective_date else None,
        "engineering_reference": row.engineering_reference,
        "applicable_activities": row.applicable_activities,
        "template_ids": list(row.template_ids or []),
        "checkpoints": [_point_view(point) for point in _checkpoints(db, row)],
        "statement": STATEMENT,
        "witness_rule": WITNESS if row.kind == "ITP" else "",
    }


def submit_document(db, user, project, row, version):
    if row.status == "Returned for Correction":
        raise HTTPException(409, "A returned quality document is resubmitted, not submitted again")
    if row.status != "Draft":
        raise HTTPException(409, "Only a draft quality document can be submitted")
    _validate_document(db, row)
    policy = _policy_for(db, project, DOCUMENT, row.company_id, row.discipline_id)
    payload = _document_snapshot(db, row)
    _bump(
        db,
        QualityDocument,
        row,
        version,
        {"status": "Pending Review", "payload": payload, "modified_by": user.id},
    )
    return submit_record(db, user, project, DOCUMENT, row.id, row.version, policy)


def add_form(db, user, project, data):
    _discipline(db, project, data.discipline_id, True)
    _criteria(db, project, data.criteria_document_id, False)
    items = _items(data.items)
    code_key = data.code.strip().casefold()
    revision_key = data.revision_label.strip().casefold()
    if (
        db.query(QualityForm)
        .filter_by(project_id=project.id, code_key=code_key, revision_key=revision_key)
        .first()
    ):
        raise HTTPException(409, "That template revision already exists on this project")
    row = QualityForm(
        organization_id=project.organization_id,
        project_id=project.id,
        discipline_id=data.discipline_id,
        code=data.code.strip(),
        code_key=code_key,
        title=data.title.strip(),
        revision_label=data.revision_label.strip(),
        revision_key=revision_key,
        criteria_document_id=data.criteria_document_id,
        units=data.units.strip(),
        prerequisites=data.prerequisites.strip(),
        required_attachments=data.required_attachments.strip(),
        items=items,
        payload={},
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def _items(values):
    items = []
    for value in values:
        text = value.strip()
        if not text:
            continue
        if len(text) > 200:
            raise HTTPException(422, "A checklist item is limited to 200 characters")
        items.append(text)
    return items


def update_form(db, user, project, row, data):
    _editable(row)
    _discipline(db, project, data.discipline_id, True)
    _criteria(db, project, data.criteria_document_id, False)
    _bump(
        db,
        QualityForm,
        row,
        data.version,
        {
            "title": data.title.strip(),
            "discipline_id": data.discipline_id,
            "criteria_document_id": data.criteria_document_id,
            "units": data.units.strip(),
            "prerequisites": data.prerequisites.strip(),
            "required_attachments": data.required_attachments.strip(),
            "items": _items(data.items),
            "modified_by": user.id,
        },
    )


def _form_snapshot(db, row):
    criteria = db.get(QualityDocument, row.criteria_document_id) if row.criteria_document_id else None
    return {
        "code": row.code,
        "title": row.title,
        "revision_label": row.revision_label,
        "discipline_id": row.discipline_id,
        "criteria_document_id": row.criteria_document_id,
        "criteria_revision": criteria.revision_label if criteria else "",
        "criteria_number": criteria.number if criteria else "",
        "units": row.units,
        "prerequisites": row.prerequisites,
        "required_attachments": row.required_attachments,
        "items": list(row.items or []),
        "statement": (
            "This template version is frozen with the submission. "
            "A later template edit does not change this record."
        ),
    }


def submit_form(db, user, project, row, version):
    if row.status == "Returned for Correction":
        raise HTTPException(409, "A returned template is resubmitted, not submitted again")
    if row.status != "Draft":
        raise HTTPException(409, "Only a draft template can be submitted")
    if not row.items:
        raise HTTPException(422, "Add the checklist items before submission")
    if not row.units.strip():
        raise HTTPException(422, "Record the measurement units")
    criteria = _criteria(db, project, row.criteria_document_id, True)
    if criteria.discipline_id and criteria.discipline_id != row.discipline_id:
        raise HTTPException(422, "The acceptance criteria are for another discipline")
    policy = _policy_for(db, project, FORM, None, row.discipline_id)
    payload = _form_snapshot(db, row)
    _bump(
        db,
        QualityForm,
        row,
        version,
        {"status": "Pending Review", "payload": payload, "modified_by": user.id},
    )
    return submit_record(db, user, project, FORM, row.id, row.version, policy)


def revise_document(db, user, project, row, data):
    if row.status not in {"Approved", "Rejected", "Superseded"}:
        raise HTTPException(409, "Revise an approved or rejected quality document")
    if row.version != data.version:
        raise HTTPException(409, "This quality record changed. Reload it and try again")
    revision_key = data.revision_label.strip().casefold()
    if (
        db.query(QualityDocument)
        .filter_by(project_id=project.id, kind=row.kind, number_key=row.number_key, revision_key=revision_key)
        .first()
    ):
        raise HTTPException(409, "That document revision already exists on this project")
    copy = QualityDocument(
        organization_id=project.organization_id,
        project_id=project.id,
        kind=row.kind,
        number=row.number,
        number_key=row.number_key,
        title=row.title,
        revision_label=data.revision_label.strip(),
        revision_key=revision_key,
        discipline_id=row.discipline_id,
        company_id=row.company_id,
        area_id=row.area_id,
        effective_date=row.effective_date,
        engineering_reference=row.engineering_reference,
        applicable_activities=row.applicable_activities,
        template_ids=list(row.template_ids or []),
        statement=STATEMENT,
        payload={},
        created_by=user.id,
    )
    db.add(copy)
    db.flush()
    for point in _checkpoints(db, row):
        db.add(
            QualityCheckpoint(
                document_id=copy.id,
                sequence=point.sequence,
                name=point.name,
                criteria_reference=point.criteria_reference,
                responsible_parties=point.responsible_parties,
                point_type=point.point_type,
                notice_hours=point.notice_hours,
                required_evidence=point.required_evidence,
                required_signatories=point.required_signatories,
                partial_allowed=point.partial_allowed,
                next_release_conditions=point.next_release_conditions,
            )
        )
    db.flush()
    return copy


def revise_form(db, user, project, row, data):
    if row.status not in {"Approved", "Rejected", "Superseded"}:
        raise HTTPException(409, "Revise an approved or rejected template")
    if row.version != data.version:
        raise HTTPException(409, "This quality record changed. Reload it and try again")
    revision_key = data.revision_label.strip().casefold()
    if (
        db.query(QualityForm)
        .filter_by(project_id=project.id, code_key=row.code_key, revision_key=revision_key)
        .first()
    ):
        raise HTTPException(409, "That template revision already exists on this project")
    copy = QualityForm(
        organization_id=project.organization_id,
        project_id=project.id,
        discipline_id=row.discipline_id,
        code=row.code,
        code_key=row.code_key,
        title=row.title,
        revision_label=data.revision_label.strip(),
        revision_key=revision_key,
        criteria_document_id=row.criteria_document_id,
        units=row.units,
        prerequisites=row.prerequisites,
        required_attachments=row.required_attachments,
        items=list(row.items or []),
        payload={},
        supersedes_id=row.id if row.status == "Approved" else row.supersedes_id,
        created_by=user.id,
    )
    db.add(copy)
    db.flush()
    return copy


def cancel_document(db, user, row, data):
    if row.status not in EDITABLE:
        raise HTTPException(409, "Only a draft quality document can be cancelled here")
    _bump(
        db,
        QualityDocument,
        row,
        data.version,
        {"status": "Cancelled", "cancellation_reason": data.reason.strip(), "modified_by": user.id},
    )


def cancel_form(db, user, row, data):
    if row.status not in EDITABLE:
        raise HTTPException(409, "Only a draft template can be cancelled here")
    _bump(
        db,
        QualityForm,
        row,
        data.version,
        {"status": "Cancelled", "cancellation_reason": data.reason.strip(), "modified_by": user.id},
    )


def apply_resubmit(db, user, instance, review_version):
    from app.domains.coordination.service import _close_tasks, _lock, _open_stage, current_stage
    from app.domains.identity_projects.models import Project

    if instance.record_type not in {DOCUMENT, FORM}:
        return
    if instance.state != "Returned":
        raise HTTPException(409, "Only a returned review can be resubmitted")
    if user.id != instance.submitted_by and not user.organization_admin:
        raise HTTPException(403, "Only the submitter can resubmit")
    project = db.get(Project, instance.project_id)
    if not project:
        raise HTTPException(404, "Quality record not found")
    permitted(db, user, project, "quality.plan")
    if instance.record_type == DOCUMENT:
        row = db.get(QualityDocument, instance.record_id)
        if not row or row.project_id != project.id or row.status != "Returned for Correction":
            raise HTTPException(409, "Only a returned quality document can be resubmitted")
        _validate_document(db, row)
        policy = _policy_for(db, project, DOCUMENT, row.company_id, row.discipline_id)
        payload = _document_snapshot(db, row)
        model = QualityDocument
    else:
        row = db.get(QualityForm, instance.record_id)
        if not row or row.project_id != project.id or row.status != "Returned for Correction":
            raise HTTPException(409, "Only a returned template can be resubmitted")
        if not row.items or not row.units.strip():
            raise HTTPException(422, "Add the checklist items and measurement units")
        criteria = _criteria(db, project, row.criteria_document_id, True)
        if criteria.discipline_id and criteria.discipline_id != row.discipline_id:
            raise HTTPException(422, "The acceptance criteria are for another discipline")
        policy = _policy_for(db, project, FORM, None, row.discipline_id)
        payload = _form_snapshot(db, row)
        model = QualityForm
    _lock(db, instance, review_version)
    _close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    _bump(db, model, row, row.version, {"status": "Pending Review", "payload": payload, "modified_by": user.id})
    instance.record_version = row.version
    instance.policy_id = policy.id
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def _supersede(db, project, row):
    if isinstance(row, QualityDocument):
        others = (
            db.query(QualityDocument)
            .filter_by(project_id=project.id, kind=row.kind, number_key=row.number_key, status="Approved")
            .all()
        )
    else:
        others = (
            db.query(QualityForm)
            .filter_by(project_id=project.id, code_key=row.code_key, status="Approved")
            .all()
        )
    for other in others:
        if other.id != row.id:
            other.status = "Superseded"
            other.modified_at = now()


def on_review_event(db, user, instance, project, action, stage=None):
    if instance.record_type == DOCUMENT:
        row = db.get(QualityDocument, instance.record_id)
    elif instance.record_type == FORM:
        row = db.get(QualityForm, instance.record_id)
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
        _supersede(db, project, row)
        label = row.number if isinstance(row, QualityDocument) else row.code
        _tell(
            db,
            project,
            _watchers(db, project),
            "Quality document approved",
            f"{label} rev {row.revision_label} is approved for use. No work was accepted and no billing certificate was created.",
            f"{instance.record_type}.{row.id}",
        )
    else:
        return
    row.version += 1
    row.modified_by = user.id
    row.modified_at = now()


def review_guard(db, user, instance, stage, action):
    if instance.record_type not in {DOCUMENT, FORM} or action != "approve":
        return
    from app.domains.identity_projects.models import Project

    project = db.get(Project, instance.project_id)
    if instance.record_type == DOCUMENT:
        row = db.get(QualityDocument, instance.record_id)
        if not project or not row or row.project_id != project.id or row.status != "Pending Review":
            raise HTTPException(409, "This quality document is not awaiting review")
        _validate_document(db, row)
        return
    row = db.get(QualityForm, instance.record_id)
    if not project or not row or row.project_id != project.id or row.status != "Pending Review":
        raise HTTPException(409, "This template is not awaiting review")
    criteria = db.get(QualityDocument, row.criteria_document_id) if row.criteria_document_id else None
    if not criteria or criteria.status != "Approved" or criteria.project_id != project.id:
        raise HTTPException(409, "Only an approved quality document can be used")
    frozen = (row.payload or {}).get("criteria_revision")
    if frozen and criteria.revision_label != frozen:
        raise HTTPException(409, "The acceptance criteria revision changed. Return the template")


if review_guard not in REVIEW_GUARDS:
    REVIEW_GUARDS.append(review_guard)
