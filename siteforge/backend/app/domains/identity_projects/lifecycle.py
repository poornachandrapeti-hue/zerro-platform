from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import update

from .models import Project
from .schemas import ProjectIn

ALLOWED = {
    "Draft": {"Planned", "Cancelled"},
    "Planned": {"On Hold", "Cancelled"},
    "Active": {"On Hold", "Completed", "Cancelled"},
    "On Hold": {"Cancelled"},
    "Completed": set(),
    "Cancelled": set(),
}


def project_input(db, project, **overrides):
    from .router import company_roles, discipline_payload

    records = discipline_payload(db, project.id)
    main, pmc, subs = company_roles(db, project.id)
    values = dict(
        code=project.code,
        name=project.name,
        description=project.description,
        project_type=project.project_type,
        status=project.status,
        site_name=project.site_name,
        address=project.address,
        country=project.country,
        state=project.state,
        city=project.city,
        postal_code=project.postal_code,
        timezone=project.timezone,
        latitude=project.latitude,
        longitude=project.longitude,
        planned_start=project.planned_start,
        planned_finish=project.planned_finish,
        actual_start=project.actual_start,
        actual_finish=project.actual_finish,
        client_company_id=project.client_company_id,
        main_contractor_company_id=main,
        pmc_company_id=pmc,
        subcontractor_ids=subs,
        lead_pm_id=project.lead_pm_id,
        discipline_ids=[row["discipline_id"] for row in records if row["active"]],
        disciplines=records,
        hold_reason=project.hold_reason,
        cancellation_reason=project.cancellation_reason,
        contract_number=project.contract_number or "",
        contract_date=project.contract_date,
        contract_value=project.contract_value,
        currency=project.currency or "",
    )
    values.update(overrides)
    return ProjectIn(**values)


def apply_transition(db, user, project, target, reason, version):
    from .router import audit, sync_project, validate_project

    if target not in ALLOWED.get(project.status, set()):
        raise HTTPException(409, "That status change is not allowed")
    if target in {"On Hold", "Completed", "Cancelled"} and not (reason or "").strip():
        raise HTTPException(422, "A reason is required for this status change")
    data = project_input(
        db,
        project,
        status=target,
        hold_reason=reason if target == "On Hold" else project.hold_reason,
        cancellation_reason=reason
        if target == "Cancelled"
        else project.cancellation_reason,
    )
    validate_project(db, user, data)
    result = db.execute(
        update(Project)
        .where(Project.id == project.id, Project.version == version)
        .values(
            status=target,
            hold_reason=data.hold_reason,
            cancellation_reason=data.cancellation_reason,
            version=version + 1,
            modified_by=user.id,
            modified_at=datetime.now(timezone.utc),
        )
    )
    if result.rowcount != 1:
        raise HTTPException(409, "Project changed by another user; reload before saving")
    db.refresh(project)
    sync_project(db, user, project, data)
    audit(
        db,
        user,
        "transition",
        "projects",
        project.id,
        {"status": target, "reason": reason},
        project_id=project.id,
    )
    return project


def apply_activation(db, user, project, expected_version):
    from .router import audit, sync_project, validate_project

    db.refresh(project)
    if project.version != expected_version:
        raise HTTPException(
            409, "The project changed after submission. Return it for correction"
        )
    if project.status == "Active":
        return project
    if project.status not in {"Draft", "Planned", "On Hold"}:
        raise HTTPException(409, "Project cannot be activated from its current status")
    data = project_input(db, project, status="Active")
    validate_project(db, user, data)
    result = db.execute(
        update(Project)
        .where(Project.id == project.id, Project.version == expected_version)
        .values(
            status="Active",
            version=expected_version + 1,
            modified_by=user.id,
            modified_at=datetime.now(timezone.utc),
        )
    )
    if result.rowcount != 1:
        raise HTTPException(
            409, "The project changed after submission. Return it for correction"
        )
    db.refresh(project)
    sync_project(db, user, project, data)
    audit(
        db,
        user,
        "activate",
        "projects",
        project.id,
        {"status": "Active"},
        project_id=project.id,
    )
    return project
