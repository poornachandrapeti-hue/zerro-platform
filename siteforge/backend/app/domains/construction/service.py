"""Work packages, activity templates, work items, and daily progress.

Saving a package does not release it. A drawing release does not create a package.
An approved handover dossier marks the package handed over. Inspection is not recorded here.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.domains.engineering_documents.models import Drawing, DrawingRevision
from app.domains.identity_projects.models import (
    Area,
    Company,
    Discipline,
    Membership,
    ProjectCompany,
    ProjectDiscipline,
    User,
)
from app.domains.supply_chain.models import MaterialRequirement

from .catalogue import example_rows
from .models import (
    ConstructionActivity,
    ConstructionItem,
    ConstructionPredecessor,
    ConstructionScopeChange,
    ConstructionTemplate,
    WorkPackage,
    WorkPackageDrawing,
    WorkPackageRequirement,
    now,
)

QTY = Decimal("0.001")
CLOSED = ()


def qty(value):
    return format(Decimal(value).quantize(QTY), "f")


def weight(value):
    if value is None:
        return None
    return format(Decimal(value).quantize(Decimal("0.01")), "f")


def day(value):
    return value.isoformat() if value else None


def _enabled_discipline(db, project, discipline_id):
    row = (
        db.query(ProjectDiscipline)
        .filter_by(project_id=project.id, discipline_id=discipline_id, active=True)
        .first()
    )
    if not row:
        raise HTTPException(422, "Discipline is not enabled on this project")


def _area(db, project, area_id):
    area = db.get(Area, area_id)
    if not area or area.project_id != project.id or not area.active:
        raise HTTPException(422, "Location is not an active area on this project")
    return area


def _company(db, project, company_id):
    link = (
        db.query(ProjectCompany)
        .filter_by(project_id=project.id, company_id=company_id, active=True)
        .first()
    )
    if not link:
        raise HTTPException(422, "Company is not active on this project")
    return db.get(Company, company_id)


def _member(db, project, user_id, label):
    if not user_id:
        return None
    person = db.get(User, user_id)
    row = (
        db.query(Membership)
        .filter_by(project_id=project.id, user_id=user_id, active=True)
        .first()
    )
    if not person or not person.active or person.organization_id != project.organization_id or not row:
        raise HTTPException(422, f"Choose an active project member for {label}")
    return person


def _dates(start, finish, label):
    if start and finish and finish < start:
        raise HTTPException(422, f"{label} finish is before the start")


def _released_revision(db, project, revision_id):
    revision = db.get(DrawingRevision, revision_id)
    drawing = db.get(Drawing, revision.drawing_id) if revision else None
    if (
        not revision
        or not drawing
        or drawing.project_id != project.id
        or drawing.organization_id != project.organization_id
        or revision.release_state != "Released"
    ):
        raise HTTPException(422, "Only a released drawing revision on this project can be linked")
    return revision, drawing


def _requirement(db, project, requirement_id):
    row = db.get(MaterialRequirement, requirement_id)
    if not row or row.project_id != project.id:
        raise HTTPException(422, "Material requirement is not on this project")
    return row


def _unique(ids, message):
    if len(ids) != len(set(ids)):
        raise HTTPException(422, message)
    return list(dict.fromkeys(ids))


def _draft_package(package):
    if package.status == "Cancelled":
        raise HTTPException(409, "This work package is cancelled")
    if getattr(package, "release_state", "Not Submitted") == "In Review":
        raise HTTPException(409, "This work package is in release review")
    if package.status != "Draft":
        raise HTTPException(409, "This work package can no longer be edited here")


def summary(db, project):
    return {
        "packages_draft": db.query(WorkPackage)
        .filter_by(project_id=project.id, status="Draft")
        .count(),
        "templates": db.query(ConstructionTemplate).filter_by(project_id=project.id, active=True).count(),
        "activities": db.query(ConstructionActivity).filter_by(project_id=project.id, active=True).count(),
        "items": db.query(ConstructionItem).filter_by(project_id=project.id, active=True).count(),
        "note": (
            "Daily progress is recorded on a package that is already in progress. "
            "A posted stores issue can be named on a line. The stores balance stays unchanged. "
            "An in-progress package can be held, and resume uses the saved release reviewer. "
            "An approved handover dossier marks the package handed over. "
            "Approving a report verifies the quantity. Quality records acceptance separately."
        ),
        "closed": list(CLOSED),
    }


def sources(db, project):
    disciplines = [
        {"id": row.id, "name": row.name}
        for row in db.query(Discipline)
        .join(ProjectDiscipline, ProjectDiscipline.discipline_id == Discipline.id)
        .filter(ProjectDiscipline.project_id == project.id, ProjectDiscipline.active.is_(True))
        .order_by(Discipline.name)
    ]
    areas = [
        {"id": row.id, "code": row.code, "name": row.name, "area_type": row.area_type}
        for row in db.query(Area).filter_by(project_id=project.id, active=True).order_by(Area.code)
    ]
    companies = [
        {"id": link.company_id, "name": db.get(Company, link.company_id).name, "participation_type": link.participation_type}
        for link in db.query(ProjectCompany).filter_by(project_id=project.id, active=True)
    ]
    members = []
    seen = set()
    for row in db.query(Membership).filter_by(project_id=project.id, active=True):
        if row.user_id in seen:
            continue
        seen.add(row.user_id)
        person = db.get(User, row.user_id)
        if person and person.active:
            members.append({"id": person.id, "name": person.name})
    revisions = []
    for revision, drawing in (
        db.query(DrawingRevision, Drawing)
        .join(Drawing, Drawing.id == DrawingRevision.drawing_id)
        .filter(Drawing.project_id == project.id, DrawingRevision.release_state == "Released")
        .order_by(Drawing.number, DrawingRevision.code)
    ):
        revisions.append(
            {
                "id": revision.id,
                "label": f"{drawing.number} rev {revision.code}",
            }
        )
    requirements = [
        {"id": row.id, "number": row.number}
        for row in db.query(MaterialRequirement)
        .filter_by(project_id=project.id)
        .order_by(MaterialRequirement.number)
    ]
    return {
        "disciplines": disciplines,
        "areas": areas,
        "companies": companies,
        "members": members,
        "revisions": revisions,
        "requirements": requirements,
    }


def _template_row(db, row):
    discipline = db.get(Discipline, row.discipline_id)
    return {
        "id": row.id,
        "discipline_id": row.discipline_id,
        "discipline_name": discipline.name if discipline else "",
        "code": row.code,
        "name": row.name,
        "unit": row.unit,
        "prerequisites": row.prerequisites,
        "required_evidence": row.required_evidence,
        "checkpoints": list(row.checkpoints or []),
        "progress_method": row.progress_method,
        "completion_conditions": row.completion_conditions,
        "active": row.active,
        "version": row.version,
    }


def list_templates(db, project):
    rows = (
        db.query(ConstructionTemplate)
        .filter_by(project_id=project.id)
        .order_by(ConstructionTemplate.code)
        .all()
    )
    return [_template_row(db, row) for row in rows]


def _save_template(db, user, project, data, existing=None):
    _enabled_discipline(db, project, data.discipline_id)
    key = data.code.casefold()
    taken = (
        db.query(ConstructionTemplate)
        .filter_by(project_id=project.id, code_key=key)
        .first()
    )
    if taken and (not existing or taken.id != existing.id):
        raise HTTPException(409, "Activity code already exists on this project")
    if existing:
        changed = db.execute(
            update(ConstructionTemplate)
            .where(ConstructionTemplate.id == existing.id, ConstructionTemplate.version == data.version)
            .values(
                discipline_id=data.discipline_id,
                code=data.code,
                code_key=key,
                name=data.name,
                unit=data.unit,
                prerequisites=data.prerequisites,
                required_evidence=data.required_evidence,
                checkpoints=data.checkpoints,
                progress_method=data.progress_method,
                completion_conditions=data.completion_conditions,
                active=data.active,
                modified_by=user.id,
                modified_at=now(),
                version=data.version + 1,
            )
        )
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "Template changed by another user; reload before saving")
        db.flush()
        db.refresh(existing)
        return existing
    row = ConstructionTemplate(
        organization_id=project.organization_id,
        project_id=project.id,
        discipline_id=data.discipline_id,
        code=data.code,
        code_key=key,
        name=data.name,
        unit=data.unit,
        prerequisites=data.prerequisites,
        required_evidence=data.required_evidence,
        checkpoints=data.checkpoints,
        progress_method=data.progress_method,
        completion_conditions=data.completion_conditions,
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def add_examples(db, user, project):
    added = 0
    enabled = (
        db.query(Discipline.name, ProjectDiscipline.discipline_id)
        .join(ProjectDiscipline, ProjectDiscipline.discipline_id == Discipline.id)
        .filter(ProjectDiscipline.project_id == project.id, ProjectDiscipline.active.is_(True))
        .all()
    )
    for name, discipline_id in enabled:
        for row in example_rows(name):
            key = row["code"].casefold()
            if (
                db.query(ConstructionTemplate)
                .filter_by(project_id=project.id, code_key=key)
                .first()
            ):
                continue
            db.add(
                ConstructionTemplate(
                    organization_id=project.organization_id,
                    project_id=project.id,
                    discipline_id=discipline_id,
                    code=row["code"],
                    code_key=key,
                    name=row["name"],
                    unit=row["unit"],
                    prerequisites=row["prerequisites"],
                    required_evidence=row["required_evidence"],
                    checkpoints=row["checkpoints"],
                    progress_method=row["progress_method"],
                    completion_conditions=row["completion_conditions"],
                    created_by=user.id,
                    modified_by=user.id,
                )
            )
            added += 1
    db.flush()
    return added


def _links(db, package):
    drawings = []
    for link in db.query(WorkPackageDrawing).filter_by(package_id=package.id):
        revision = db.get(DrawingRevision, link.revision_id)
        drawing = db.get(Drawing, revision.drawing_id) if revision else None
        if revision and drawing and drawing.project_id == package.project_id:
            drawings.append({"id": revision.id, "label": f"{drawing.number} rev {revision.code}"})
    requirements = []
    for link in db.query(WorkPackageRequirement).filter_by(package_id=package.id):
        row = db.get(MaterialRequirement, link.requirement_id)
        if row:
            requirements.append({"id": row.id, "number": row.number})
    return drawings, requirements


def _package_row(db, package):
    area = db.get(Area, package.area_id)
    company = db.get(Company, package.company_id)
    discipline = db.get(Discipline, package.discipline_id)
    responsible = db.get(User, package.responsible_user_id) if package.responsible_user_id else None
    supervisor = db.get(User, package.supervisor_user_id) if package.supervisor_user_id else None
    drawings, requirements = _links(db, package)
    return {
        "id": package.id,
        "code": package.code,
        "name": package.name,
        "discipline_id": package.discipline_id,
        "discipline_name": discipline.name if discipline else "",
        "area_id": package.area_id,
        "area_name": f"{area.code} · {area.name}" if area else "",
        "scope_description": package.scope_description,
        "company_id": package.company_id,
        "company_name": company.name if company else "",
        "responsible_user_id": package.responsible_user_id,
        "responsible_name": responsible.name if responsible else "",
        "supervisor_user_id": package.supervisor_user_id,
        "supervisor_name": supervisor.name if supervisor else "",
        "priority": package.priority,
        "planning_reference": package.planning_reference,
        "planned_start": day(package.planned_start),
        "planned_finish": day(package.planned_finish),
        "remarks": package.remarks,
        "status": package.status,
        "release_state": package.release_state,
        "cancellation_reason": package.cancellation_reason,
        "impact_state": package.impact_state,
        "impact_detail": package.impact_detail,
        "impact_revision_id": package.impact_revision_id,
        "revision_ids": [row["id"] for row in drawings],
        "revisions": drawings,
        "requirement_ids": [row["id"] for row in requirements],
        "requirements": requirements,
        "activity_count": db.query(ConstructionActivity).filter_by(package_id=package.id, active=True).count(),
        "version": package.version,
        "release_open": True,
    }


def list_packages(db, project):
    rows = db.query(WorkPackage).filter_by(project_id=project.id).order_by(WorkPackage.code).all()
    return [_package_row(db, row) for row in rows]


def _apply_links(db, project, package, revision_ids, requirement_ids):
    revision_ids = _unique(revision_ids, "Choose each drawing revision once")
    requirement_ids = _unique(requirement_ids, "Choose each material requirement once")
    for revision_id in revision_ids:
        _released_revision(db, project, revision_id)
    for requirement_id in requirement_ids:
        _requirement(db, project, requirement_id)
    db.execute(delete(WorkPackageDrawing).where(WorkPackageDrawing.package_id == package.id))
    db.execute(delete(WorkPackageRequirement).where(WorkPackageRequirement.package_id == package.id))
    for revision_id in revision_ids:
        db.add(WorkPackageDrawing(package_id=package.id, revision_id=revision_id))
    for requirement_id in requirement_ids:
        db.add(WorkPackageRequirement(package_id=package.id, requirement_id=requirement_id))
    db.flush()


def _package_values(db, project, data):
    _enabled_discipline(db, project, data.discipline_id)
    _area(db, project, data.area_id)
    _company(db, project, data.company_id)
    _member(db, project, data.responsible_user_id, "the responsible engineer")
    _member(db, project, data.supervisor_user_id, "the supervisor")
    _dates(data.planned_start, data.planned_finish, "Planned")
    return data.code.casefold()


def add_package(db, user, project, data):
    key = _package_values(db, project, data)
    if db.query(WorkPackage).filter_by(project_id=project.id, code_key=key).first():
        raise HTTPException(409, "Work package code already exists on this project")
    package = WorkPackage(
        organization_id=project.organization_id,
        project_id=project.id,
        code=data.code,
        code_key=key,
        name=data.name,
        discipline_id=data.discipline_id,
        area_id=data.area_id,
        scope_description=data.scope_description,
        company_id=data.company_id,
        responsible_user_id=data.responsible_user_id,
        supervisor_user_id=data.supervisor_user_id,
        priority=data.priority,
        planning_reference=data.planning_reference,
        planned_start=data.planned_start,
        planned_finish=data.planned_finish,
        remarks=data.remarks,
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(package)
    db.flush()
    _apply_links(db, project, package, data.revision_ids, data.requirement_ids)
    return package


def save_package(db, user, project, package, data):
    _draft_package(package)
    key = _package_values(db, project, data)
    taken = db.query(WorkPackage).filter_by(project_id=project.id, code_key=key).first()
    if taken and taken.id != package.id:
        raise HTTPException(409, "Work package code already exists on this project")
    changed = db.execute(
        update(WorkPackage)
        .where(WorkPackage.id == package.id, WorkPackage.version == data.version)
        .values(
            code=data.code,
            code_key=key,
            name=data.name,
            discipline_id=data.discipline_id,
            area_id=data.area_id,
            scope_description=data.scope_description,
            company_id=data.company_id,
            responsible_user_id=data.responsible_user_id,
            supervisor_user_id=data.supervisor_user_id,
            priority=data.priority,
            planning_reference=data.planning_reference,
            planned_start=data.planned_start,
            planned_finish=data.planned_finish,
            remarks=data.remarks,
            modified_by=user.id,
            modified_at=now(),
            version=data.version + 1,
        )
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Work package changed by another user; reload before saving")
    db.flush()
    db.refresh(package)
    _apply_links(db, project, package, data.revision_ids, data.requirement_ids)
    return package


def cancel_package(db, user, package, data):
    if package.release_state == "In Review":
        raise HTTPException(409, "This work package is in release review")
    if package.status != "Draft":
        raise HTTPException(409, "Only a draft work package can be cancelled here")
    changed = db.execute(
        update(WorkPackage)
        .where(WorkPackage.id == package.id, WorkPackage.version == data.version, WorkPackage.status == "Draft")
        .values(
            status="Cancelled",
            cancellation_reason=data.reason,
            modified_by=user.id,
            modified_at=now(),
            version=data.version + 1,
        )
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Work package changed by another user; reload before saving")
    db.flush()
    db.refresh(package)
    return package


def _activity(db, project, activity_id):
    row = db.get(ConstructionActivity, activity_id)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "Activity not found")
    return row


def _guard_cycle(db, activity_id, predecessor_ids):
    seen = set()
    stack = list(predecessor_ids)
    while stack:
        current = stack.pop()
        if current == activity_id:
            raise HTTPException(422, "An activity cannot depend on itself")
        if current in seen:
            continue
        seen.add(current)
        stack.extend(
            row.predecessor_id
            for row in db.query(ConstructionPredecessor).filter_by(activity_id=current)
        )


def _activity_row(db, row):
    company = db.get(Company, row.company_id)
    responsible = db.get(User, row.responsible_user_id) if row.responsible_user_id else None
    template = db.get(ConstructionTemplate, row.template_id) if row.template_id else None
    package = db.get(WorkPackage, row.package_id)
    revision_label = ""
    if row.drawing_revision_id:
        revision = db.get(DrawingRevision, row.drawing_revision_id)
        drawing = db.get(Drawing, revision.drawing_id) if revision else None
        if revision and drawing:
            revision_label = f"{drawing.number} rev {revision.code}"
    predecessors = [
        link.predecessor_id
        for link in db.query(ConstructionPredecessor).filter_by(activity_id=row.id)
    ]
    changes = [
        {
            "previous_quantity": qty(change.previous_quantity),
            "new_quantity": qty(change.new_quantity),
            "reason": change.reason,
        }
        for change in db.query(ConstructionScopeChange)
        .filter_by(activity_id=row.id)
        .order_by(ConstructionScopeChange.id.desc())
    ]
    row_out = {
        "id": row.id,
        "package_id": row.package_id,
        "package_code": package.code if package else "",
        "template_id": row.template_id,
        "template_code": template.code if template else "",
        "code": row.code,
        "name": row.name,
        "description": row.description,
        "baseline_quantity": qty(row.baseline_quantity),
        "quantity": qty(row.quantity),
        "unit": row.unit,
        "company_id": row.company_id,
        "company_name": company.name if company else "",
        "responsible_user_id": row.responsible_user_id,
        "responsible_name": responsible.name if responsible else "",
        "drawing_revision_id": row.drawing_revision_id,
        "drawing_label": revision_label,
        "predecessor_ids": predecessors,
        "measurement_method": row.measurement_method,
        "progress_weight": weight(row.progress_weight),
        "target_start": day(row.target_start),
        "target_finish": day(row.target_finish),
        "active": row.active,
        "version": row.version,
        "scope_changes": changes,
    }
    from .progress import activity_measures

    row_out["progress_note"] = activity_measures(db, row)["note"]
    return row_out


def list_activities(db, project):
    rows = (
        db.query(ConstructionActivity)
        .filter_by(project_id=project.id)
        .order_by(ConstructionActivity.code)
        .all()
    )
    return [_activity_row(db, row) for row in rows]


def _activity_package(db, project, data):
    package = db.get(WorkPackage, data.package_id)
    if not package or package.project_id != project.id:
        raise HTTPException(422, "Work package is not on this project")
    _draft_package(package)
    if data.template_id:
        template = db.get(ConstructionTemplate, data.template_id)
        if (
            not template
            or template.project_id != project.id
            or not template.active
            or template.discipline_id != package.discipline_id
        ):
            raise HTTPException(422, "Choose an active template for this package discipline")
    _company(db, project, data.company_id)
    _member(db, project, data.responsible_user_id, "the responsible engineer")
    if data.drawing_revision_id:
        _released_revision(db, project, data.drawing_revision_id)
    _dates(data.target_start, data.target_finish, "Target")
    predecessors = _unique(data.predecessor_ids, "Choose each predecessor once")
    for predecessor_id in predecessors:
        earlier = _activity(db, project, predecessor_id)
        if earlier.project_id != project.id:
            raise HTTPException(422, "Predecessor is not on this project")
    return package, predecessors


def _set_predecessors(db, activity_id, predecessor_ids):
    _guard_cycle(db, activity_id, predecessor_ids)
    db.execute(delete(ConstructionPredecessor).where(ConstructionPredecessor.activity_id == activity_id))
    for predecessor_id in predecessor_ids:
        db.add(ConstructionPredecessor(activity_id=activity_id, predecessor_id=predecessor_id))
    db.flush()


def add_activity(db, user, project, data):
    _activity_package(db, project, data)
    key = data.code.casefold()
    if db.query(ConstructionActivity).filter_by(project_id=project.id, code_key=key).first():
        raise HTTPException(409, "Activity code already exists on this project")
    amount = Decimal(data.quantity).quantize(QTY)
    row = ConstructionActivity(
        organization_id=project.organization_id,
        project_id=project.id,
        package_id=data.package_id,
        template_id=data.template_id,
        code=data.code,
        code_key=key,
        name=data.name,
        description=data.description,
        baseline_quantity=amount,
        quantity=amount,
        unit=data.unit,
        company_id=data.company_id,
        responsible_user_id=data.responsible_user_id,
        drawing_revision_id=data.drawing_revision_id,
        measurement_method=data.measurement_method,
        progress_weight=data.progress_weight,
        target_start=data.target_start,
        target_finish=data.target_finish,
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(row)
    db.flush()
    _set_predecessors(db, row.id, _unique(data.predecessor_ids, "Choose each predecessor once"))
    return row


def save_activity(db, user, project, row, data):
    _activity_package(db, project, data)
    if data.package_id != row.package_id:
        raise HTTPException(422, "An activity stays on its work package")
    key = data.code.casefold()
    taken = db.query(ConstructionActivity).filter_by(project_id=project.id, code_key=key).first()
    if taken and taken.id != row.id:
        raise HTTPException(409, "Activity code already exists on this project")
    amount = Decimal(data.quantity).quantize(QTY)
    previous = Decimal(row.quantity).quantize(QTY)
    if amount != previous and len(data.quantity_reason.strip()) < 3:
        raise HTTPException(422, "A scope quantity change needs a reason")
    changed = db.execute(
        update(ConstructionActivity)
        .where(ConstructionActivity.id == row.id, ConstructionActivity.version == data.version)
        .values(
            template_id=data.template_id,
            code=data.code,
            code_key=key,
            name=data.name,
            description=data.description,
            quantity=amount,
            unit=data.unit,
            company_id=data.company_id,
            responsible_user_id=data.responsible_user_id,
            drawing_revision_id=data.drawing_revision_id,
            measurement_method=data.measurement_method,
            progress_weight=data.progress_weight,
            target_start=data.target_start,
            target_finish=data.target_finish,
            active=data.active,
            modified_by=user.id,
            modified_at=now(),
            version=data.version + 1,
        )
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Activity changed by another user; reload before saving")
    if amount != previous:
        db.add(
            ConstructionScopeChange(
                activity_id=row.id,
                previous_quantity=previous,
                new_quantity=amount,
                reason=data.quantity_reason.strip(),
                created_by=user.id,
            )
        )
    db.flush()
    db.refresh(row)
    _set_predecessors(db, row.id, _unique(data.predecessor_ids, "Choose each predecessor once"))
    return row


def _item_row(db, row):
    activity = db.get(ConstructionActivity, row.activity_id)
    revision_label = ""
    if row.drawing_revision_id:
        revision = db.get(DrawingRevision, row.drawing_revision_id)
        drawing = db.get(Drawing, revision.drawing_id) if revision else None
        if revision and drawing:
            revision_label = f"{drawing.number} rev {revision.code}"
    return {
        "id": row.id,
        "activity_id": row.activity_id,
        "activity_code": activity.code if activity else "",
        "identifier": row.identifier,
        "description": row.description,
        "item_kind": row.item_kind,
        "quantity": qty(row.quantity) if row.quantity is not None else None,
        "drawing_revision_id": row.drawing_revision_id,
        "drawing_label": revision_label,
        "active": row.active,
        "version": row.version,
    }


def list_items(db, project):
    rows = db.query(ConstructionItem).filter_by(project_id=project.id).order_by(ConstructionItem.identifier).all()
    return [_item_row(db, row) for row in rows]


def _item_activity(db, project, activity_id):
    activity = _activity(db, project, activity_id)
    if not activity.active:
        raise HTTPException(409, "This activity is inactive")
    package = db.get(WorkPackage, activity.package_id)
    _draft_package(package)
    return activity


def add_item(db, user, project, data):
    _item_activity(db, project, data.activity_id)
    if data.drawing_revision_id:
        _released_revision(db, project, data.drawing_revision_id)
    key = data.identifier.casefold()
    if db.query(ConstructionItem).filter_by(project_id=project.id, identifier_key=key).first():
        raise HTTPException(409, "Work item identifier already exists on this project")
    row = ConstructionItem(
        organization_id=project.organization_id,
        project_id=project.id,
        activity_id=data.activity_id,
        identifier=data.identifier,
        identifier_key=key,
        description=data.description,
        item_kind=data.item_kind,
        quantity=data.quantity,
        drawing_revision_id=data.drawing_revision_id,
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def save_item(db, user, project, row, data):
    activity = _item_activity(db, project, data.activity_id)
    if activity.id != row.activity_id:
        raise HTTPException(422, "A work item stays on its activity")
    if data.drawing_revision_id:
        _released_revision(db, project, data.drawing_revision_id)
    key = data.identifier.casefold()
    taken = db.query(ConstructionItem).filter_by(project_id=project.id, identifier_key=key).first()
    if taken and taken.id != row.id:
        raise HTTPException(409, "Work item identifier already exists on this project")
    changed = db.execute(
        update(ConstructionItem)
        .where(ConstructionItem.id == row.id, ConstructionItem.version == data.version)
        .values(
            identifier=data.identifier,
            identifier_key=key,
            description=data.description,
            item_kind=data.item_kind,
            quantity=data.quantity,
            drawing_revision_id=data.drawing_revision_id,
            active=data.active,
            modified_by=user.id,
            modified_at=now(),
            version=data.version + 1,
        )
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Work item changed by another user; reload before saving")
    db.flush()
    db.refresh(row)
    return row


