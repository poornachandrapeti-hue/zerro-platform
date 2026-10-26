from fastapi import Request
from ..config import get_settings
from ..authoritative_projects import fetch_project_master
from ..project_provisioning import provision_authorized_projects
from ..project_identity import load_project_mapping, to_siteforge_code
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..auth import CurrentUser, ensure_discipline_access, get_current_user
from ..database import get_db
from ..models import Contractor, Discipline, Project, SubTask, WorkPackage
from ..schemas import (
    ContractorCreate,
    ContractorOut,
    ContractorUpdate,
    DisciplineOut,
    ProgressUpdate,
    ProjectCreate,
    ProjectDashboard,
    ProjectListItem,
    SubTaskCreate,
    SubTaskOut,
    SubTaskUpdate,
    WorkPackageCreate,
    WorkPackageOut,
    WorkPackageUpdate,
)


router = APIRouter(prefix="/api", tags=["Projects"])
DbSession = Annotated[Session, Depends(get_db)]
User = Annotated[CurrentUser, Depends(get_current_user)]
WRITE_ROLES = {"CMD", "PROJECT_DIRECTOR", "PROJECT_MANAGER", "DISCIPLINE_HEAD"}
PROJECT_CREATE_ROLES = {"CMD", "PROJECT_DIRECTOR", "PROJECT_MANAGER"}


def weighted_progress(items: list, field: str) -> float:
    total_weight = sum(Decimal(item.weight) for item in items)
    if not total_weight:
        return 0.0
    weighted = sum(Decimal(item.weight) * Decimal(getattr(item, field)) for item in items)
    return round(float(weighted / total_weight), 2)


def visible_disciplines(project: Project, user: CurrentUser) -> list[Discipline]:
    allowed = user.discipline_codes if user.project_code == project.code else frozenset(
        code for grant_code, grant in user.grants if grant_code == project.code for code in grant.get("cc_disciplines", [])
    )
    return [item for item in project.disciplines if item.code in allowed]


def require_write_access(user: CurrentUser) -> None:
    if user.role not in WRITE_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Read-only role")


def refresh_package_progress(package: WorkPackage) -> None:
    tasks = package.sub_tasks
    if not tasks:
        return
    package.actual_progress = Decimal(str(weighted_progress(tasks, "actual_progress")))
    package.planned_progress = Decimal(str(weighted_progress(tasks, "planned_progress")))


def refresh_discipline_progress(discipline: Discipline) -> None:
    packages = discipline.work_packages
    for package in packages:
        if package.sub_tasks:
            refresh_package_progress(package)
    discipline.actual_progress = Decimal(str(weighted_progress(packages, "actual_progress")))
    discipline.planned_progress = Decimal(str(weighted_progress(packages, "planned_progress")))


def get_project_or_404(db: Session, project_id: int) -> Project:
    query = (
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.disciplines)
            .selectinload(Discipline.work_packages)
            .selectinload(WorkPackage.contractor),
            selectinload(Project.disciplines)
            .selectinload(Discipline.work_packages)
            .selectinload(WorkPackage.sub_tasks),
            selectinload(Project.milestones),
            selectinload(Project.risks),
        )
    )
    project = db.scalar(query)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def sync_authorized_projects(db: Session, user: CurrentUser) -> tuple[dict | None, dict, set[str]]:
    settings = get_settings()
    authority = fetch_project_master(settings.command_center_expected_org, settings) if settings.command_center_authoritative_projects else None
    mapping = load_project_mapping(settings.command_center_project_map) if authority is not None else {}
    allowed_codes = {code for code, grant in user.grants if grant.get("commercial") and grant.get("cc_disciplines")}
    if authority is not None:
        provision_authorized_projects(db, authority, allowed_codes, mapping, {code: set(grant.get("cc_disciplines", [])) for code, grant in user.grants if code in allowed_codes})
    return authority, mapping, allowed_codes


@router.get("/projects", response_model=list[ProjectListItem])
def list_projects(db: DbSession, user: User):
    authority, mapping, allowed_codes = sync_authorized_projects(db, user)
    projects = db.scalars(select(Project).options(selectinload(Project.disciplines)).order_by(Project.name)).all()
    return [
        ProjectListItem(
            id=project.id, code=project.code,
            name=(authority[to_siteforge_code(project.code, mapping).upper()]["name"] if authority is not None else project.name),
            client=project.client,
            location=(authority[to_siteforge_code(project.code, mapping).upper()]["location"] if authority is not None else project.location),
            status=(authority[to_siteforge_code(project.code, mapping).upper()]["status"] if authority is not None else project.status), overall_progress=weighted_progress(visible_disciplines(project, user), "actual_progress"),
            planned_progress=weighted_progress(visible_disciplines(project, user), "planned_progress"),
            planned_finish=project.planned_finish, forecast_finish=project.forecast_finish,
        )
        for project in projects if project.code in allowed_codes and (authority is None or to_siteforge_code(project.code, mapping).upper() in authority)
    ]


@router.post("/projects", response_model=ProjectListItem, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: DbSession, user: User):
    if get_settings().command_center_authoritative_projects:
        raise HTTPException(409, "Projects must be created in ZerroBuild")
    if user.role not in PROJECT_CREATE_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only CMD / Director / PM can create projects")
    if payload.planned_finish < payload.start_date or payload.forecast_finish < payload.start_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Finish dates must be on or after start date")

    project = Project(
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        client=payload.client.strip(),
        location=payload.location.strip(),
        start_date=payload.start_date,
        planned_finish=payload.planned_finish,
        forecast_finish=payload.forecast_finish,
        approved_budget=payload.approved_budget,
        currency=payload.currency.strip().upper(),
        status=payload.status.strip(),
    )
    db.add(project)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project code already exists")

    budget = payload.approved_budget
    discipline_specs = [
        ("MECHANICAL", "Mechanical", Decimal("40"), budget * Decimal("0.40")),
        ("ELECTRICAL", "Electrical", Decimal("30"), budget * Decimal("0.30")),
        ("CIVIL", "Civil", Decimal("30"), budget * Decimal("0.30")),
    ]
    for code, name, weight, disc_budget in discipline_specs:
        db.add(
            Discipline(
                project_id=project.id,
                code=code,
                name=name,
                weight=weight,
                planned_progress=Decimal("0"),
                actual_progress=Decimal("0"),
                budget=disc_budget,
                target_date=payload.planned_finish,
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project code already exists")
    db.refresh(project)
    return ProjectListItem(
        id=project.id,
        code=project.code,
        name=project.name,
        client=project.client,
        location=project.location,
        status=project.status,
        overall_progress=0,
        planned_progress=0,
        planned_finish=project.planned_finish,
        forecast_finish=project.forecast_finish,
    )


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: DbSession, user: User):
    if get_settings().command_center_authoritative_projects:
        raise HTTPException(409, "Projects must be managed in ZerroBuild")
    if user.role not in PROJECT_CREATE_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only CMD / Director / PM can delete projects")
    project = get_project_or_404(db, project_id)
    db.delete(project)
    db.commit()
    return None


@router.get("/projects/{project_id}/dashboard", response_model=ProjectDashboard)
def project_dashboard(project_id: int, db: DbSession, user: User):
    authority, mapping, _ = sync_authorized_projects(db, user)
    project = get_project_or_404(db, project_id)
    source = (authority or {}).get(to_siteforge_code(project.code, mapping).upper(), {})
    disciplines = visible_disciplines(project, user)
    if not disciplines:
        raise HTTPException(403, "No authorized disciplines")
    permitted_codes = {item.code for item in disciplines}
    packages = [package for item in disciplines for package in item.work_packages]
    # The whole-project budget is shown only to viewers entitled to every discipline.
    full_scope = {item.code for item in project.disciplines} <= permitted_codes
    return ProjectDashboard(
        id=project.id, code=project.code, name=project.name, client=project.client, location=project.location,
        status=project.status, start_date=project.start_date, planned_finish=project.planned_finish,
        forecast_finish=project.forecast_finish,
        approved_budget=project.approved_budget if full_scope else sum((d.budget for d in disciplines), Decimal("0")),
        currency=project.currency, main_contractor=(source.get("main_contractor") or "")[:200],
        overall_progress=weighted_progress(disciplines, "actual_progress"),
        planned_progress=weighted_progress(disciplines, "planned_progress"),
        budget_committed=sum((package.committed_cost for package in packages), Decimal("0")),
        actual_cost=sum((package.actual_cost for package in packages), Decimal("0")),
        disciplines=[DisciplineOut.model_validate(item) for item in disciplines],
        milestones=[item for item in project.milestones if item.discipline_code in permitted_codes],
        risks=[item for item in project.risks if item.discipline_code in permitted_codes],
    )


@router.get("/projects/{project_id}/disciplines/{discipline_code}", response_model=DisciplineOut)
def discipline_details(project_id: int, discipline_code: str, db: DbSession, user: User):
    ensure_discipline_access(user, discipline_code)
    project = get_project_or_404(db, project_id)
    discipline = next((item for item in project.disciplines if item.code == discipline_code.upper()), None)
    if not discipline:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discipline not found")
    return discipline


@router.get("/contractors", response_model=list[ContractorOut])
def list_contractors(db: DbSession, user: User):
    return db.scalars(select(Contractor).order_by(Contractor.name)).all()


@router.post("/contractors", response_model=ContractorOut, status_code=status.HTTP_201_CREATED)
def create_contractor(payload: ContractorCreate, db: DbSession, user: User):
    require_write_access(user)
    contractor = Contractor(
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        contact_name=payload.contact_name.strip(),
        phone=payload.phone.strip(),
    )
    db.add(contractor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Contractor code or name already exists")
    db.refresh(contractor)
    return contractor


@router.patch("/contractors/{contractor_id}", response_model=ContractorOut)
def update_contractor(contractor_id: int, payload: ContractorUpdate, db: DbSession, user: User):
    require_write_access(user)
    contractor = db.get(Contractor, contractor_id)
    if not contractor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(contractor, key, value.strip() if isinstance(value, str) else value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Contractor name already exists")
    db.refresh(contractor)
    return contractor


@router.patch("/work-packages/{package_id}/progress", response_model=WorkPackageOut)
def update_progress(package_id: int, payload: ProgressUpdate, db: DbSession, user: User):
    package = db.scalar(
        select(WorkPackage)
        .where(WorkPackage.id == package_id)
        .options(
            selectinload(WorkPackage.contractor),
            selectinload(WorkPackage.discipline).selectinload(Discipline.work_packages),
        )
    )
    if not package:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work package not found")
    require_write_access(user)
    ensure_discipline_access(user, package.discipline.code)
    package.actual_progress = payload.actual_progress
    package.actual_cost = payload.actual_cost
    package.status = payload.status
    refresh_discipline_progress(package.discipline)
    db.commit()
    db.refresh(package)
    return package


def get_discipline_or_404(db: Session, project_id: int, discipline_code: str) -> Discipline:
    discipline = db.scalar(
        select(Discipline)
        .where(Discipline.project_id == project_id, Discipline.code == discipline_code.upper())
        .options(selectinload(Discipline.work_packages))
    )
    if not discipline:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discipline not found")
    return discipline


@router.post(
    "/projects/{project_id}/disciplines/{discipline_code}/work-packages",
    response_model=WorkPackageOut,
    status_code=status.HTTP_201_CREATED,
)
def create_work_package(
    project_id: int,
    discipline_code: str,
    payload: WorkPackageCreate,
    db: DbSession,
    user: User,
):
    require_write_access(user)
    ensure_discipline_access(user, discipline_code)
    if not db.get(Project, project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    discipline = get_discipline_or_404(db, project_id, discipline_code)
    contractor = db.get(Contractor, payload.contractor_id)
    if not contractor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor not found")
    if payload.target_date < payload.start_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target date must be on or after start date")

    package = WorkPackage(
        discipline_id=discipline.id,
        contractor_id=contractor.id,
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        area=payload.area.strip(),
        weight=payload.weight,
        planned_progress=payload.planned_progress,
        actual_progress=payload.actual_progress,
        budget=payload.budget,
        committed_cost=payload.committed_cost,
        actual_cost=payload.actual_cost,
        start_date=payload.start_date,
        target_date=payload.target_date,
        status=payload.status.strip(),
    )
    db.add(package)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Work package code already exists")

    discipline = get_discipline_or_404(db, project_id, discipline_code)
    refresh_discipline_progress(discipline)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Work package code already exists")

    created = db.scalar(
        select(WorkPackage)
        .where(WorkPackage.id == package.id)
        .options(selectinload(WorkPackage.contractor))
    )
    return created


@router.patch("/work-packages/{package_id}", response_model=WorkPackageOut)
def update_work_package(package_id: int, payload: WorkPackageUpdate, db: DbSession, user: User):
    package = db.scalar(
        select(WorkPackage)
        .where(WorkPackage.id == package_id)
        .options(
            selectinload(WorkPackage.contractor),
            selectinload(WorkPackage.discipline).selectinload(Discipline.work_packages),
        )
    )
    if not package:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work package not found")
    require_write_access(user)
    ensure_discipline_access(user, package.discipline.code)

    data = payload.model_dump(exclude_unset=True)
    if "contractor_id" in data:
        contractor = db.get(Contractor, data["contractor_id"])
        if not contractor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor not found")
        package.contractor_id = data.pop("contractor_id")

    for key, value in data.items():
        setattr(package, key, value.strip() if isinstance(value, str) else value)

    if package.target_date < package.start_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target date must be on or after start date")

    refresh_discipline_progress(package.discipline)
    db.commit()
    db.refresh(package)
    return package


def get_package_for_write(db: Session, package_id: int) -> WorkPackage:
    package = db.scalar(
        select(WorkPackage)
        .where(WorkPackage.id == package_id)
        .options(
            selectinload(WorkPackage.contractor),
            selectinload(WorkPackage.sub_tasks),
            selectinload(WorkPackage.discipline).selectinload(Discipline.work_packages).selectinload(WorkPackage.sub_tasks),
        )
    )
    if not package:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work package not found")
    return package


@router.post("/work-packages/{package_id}/sub-tasks", response_model=SubTaskOut, status_code=status.HTTP_201_CREATED)
def create_sub_task(package_id: int, payload: SubTaskCreate, db: DbSession, user: User):
    package = get_package_for_write(db, package_id)
    require_write_access(user)
    ensure_discipline_access(user, package.discipline.code)
    if payload.target_date and payload.start_date and payload.target_date < payload.start_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target date must be on or after start date")

    task = SubTask(
        work_package_id=package.id,
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        owner=payload.owner.strip(),
        weight=payload.weight,
        planned_progress=payload.planned_progress,
        actual_progress=payload.actual_progress,
        status=payload.status.strip(),
        start_date=payload.start_date,
        target_date=payload.target_date,
        notes=payload.notes.strip(),
    )
    db.add(task)
    db.flush()
    refresh_discipline_progress(package.discipline)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/sub-tasks/{task_id}", response_model=SubTaskOut)
def update_sub_task(task_id: int, payload: SubTaskUpdate, db: DbSession, user: User):
    task = db.scalar(
        select(SubTask)
        .where(SubTask.id == task_id)
        .options(
            selectinload(SubTask.work_package)
            .selectinload(WorkPackage.discipline)
            .selectinload(Discipline.work_packages)
            .selectinload(WorkPackage.sub_tasks)
        )
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-task not found")
    require_write_access(user)
    ensure_discipline_access(user, task.work_package.discipline.code)

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(task, key, value.strip() if isinstance(value, str) else value)

    if task.target_date and task.start_date and task.target_date < task.start_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target date must be on or after start date")

    refresh_discipline_progress(task.work_package.discipline)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/sub-tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sub_task(task_id: int, db: DbSession, user: User):
    task = db.scalar(
        select(SubTask)
        .where(SubTask.id == task_id)
        .options(
            selectinload(SubTask.work_package)
            .selectinload(WorkPackage.discipline)
            .selectinload(Discipline.work_packages)
            .selectinload(WorkPackage.sub_tasks)
        )
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-task not found")
    require_write_access(user)
    ensure_discipline_access(user, task.work_package.discipline.code)
    discipline = task.work_package.discipline
    db.delete(task)
    db.flush()
    refresh_discipline_progress(discipline)
    db.commit()
    return None



@router.get("/projects/{project_id}/live-progress")
def live_verified_progress(project_id: int, db: DbSession, user: User):
    """On-demand source data, scoped to authenticated SiteForge disciplines; never uses demo figures."""
    import json
    import httpx
    from fastapi import HTTPException
    from ..config import get_settings
    cfg = get_settings()
    if not cfg.vision360_source_url or not cfg.vision360_service_key:
        raise HTTPException(503, "Live progress integration is disabled")
    project = get_project_or_404(db, project_id)
    if project.code != user.project_code:
        raise HTTPException(403, "Project scope denied")
    grant = dict(user.grants).get(project.code)
    if not grant or not grant.get("commercial"):
        raise HTTPException(403, "Commercial reporting permission required")
    try:
        mapping = load_project_mapping(cfg.command_center_project_map)
        source_code = to_siteforge_code(project.code, mapping)
        # URL supplied by administrator, not caller. Avoid redirects to unintended hosts.
        base = cfg.vision360_source_url.rstrip("/")
        if not (base.startswith("https://") or base.startswith("http://siteforge-backend:") or base.startswith("http://backend:")):
            raise HTTPException(503, "Source URL must be HTTPS or trusted internal Docker service")
        with httpx.Client(timeout=25.0, follow_redirects=False) as client:
            result = client.get(f"{base}/api/integration/vision360/projects/{source_code}/verified-progress",
                headers={"X-Vision-Service-Key":cfg.vision360_service_key})
        result.raise_for_status()
        data = result.json()
        if data.get("project_code") != source_code:
            raise ValueError("Source project mismatch")
        # Source discipline IDs are authoritative; codes verified by phase 4 grant mapping.
        allowed_ids = set(map(str, grant.get("discipline_ids", [])))
        allowed_names = grant.get("discipline_names", {})
        dmap = json.loads(cfg.command_center_discipline_map)
        packages = [p for p in data["packages"] if str(p["discipline_id"]) in allowed_ids
            and allowed_names.get(str(p["discipline_id"])) == p["discipline_name"]
            and dmap.get(p["discipline_name"]) in user.discipline_codes]
        # Date-based progress is a reference only, NOT an approved time-phased baseline.
        from datetime import date, datetime
        as_of = datetime.fromisoformat(data["generated_at"].replace("Z", "+00:00")).date()
        for package in packages:
            start, finish = package.get("planned_start"), package.get("planned_finish")
            package["date_reference_percent"] = None
            package["date_reference_note"] = "No valid work-package planned dates"
            if start and finish:
                try:
                    begin, end = date.fromisoformat(start), date.fromisoformat(finish)
                    if begin <= end:
                        span = (end - begin).days
                        percentage = (100.0 if as_of >= end else 0.0 if as_of < begin else
                                      100.0 * (as_of - begin).days / span if span else 100.0)
                        package["date_reference_percent"] = round(max(0.0, min(100.0, percentage)), 1)
                        package["date_reference_note"] = "Linear elapsed-time reference; not an approved quantity baseline"
                except (ValueError, TypeError):
                    pass
        from ..baseline_comparison import load_approved_manifest, apply_baseline
        # SiteForge is authoritative when it contains an approved revision. A configured
        # local file remains a fallback ONLY when SiteForge has no approved revision.
        from ..baseline_comparison import load_approved_document
        with httpx.Client(timeout=25.0, follow_redirects=False) as client:
            schedule_response = client.get(
                f"{base}/api/integration/vision360/projects/{source_code}/approved-baseline",
                headers={"X-Vision-Service-Key": cfg.vision360_service_key},
            )
        if schedule_response.status_code == 404:
            # Older SiteForge backend: fail closed rather than silently using stale data.
            raise HTTPException(503, "SiteForge Planning baseline API is not deployed")
        schedule_response.raise_for_status()
        source_schedule = schedule_response.json()
        if source_schedule.get("project_code") != source_code:
            raise ValueError("Planning source project mismatch")
        if source_schedule.get("status") == "approved":
            baseline = load_approved_document(source_schedule["baseline"], source_code)
            baseline_origin = "siteforge_planning"
        elif source_schedule.get("status") == "not_configured":
            baseline = load_approved_manifest(cfg.command_center_approved_baseline_path, source_code)
            baseline_origin = "server_file_fallback" if baseline else "none"
        else:
            raise ValueError("Unrecognized planning revision status")
        if not 0 <= cfg.command_center_delay_threshold_pp <= 100:
            raise ValueError("Invalid delay threshold")
        alerts, baseline_status = apply_baseline(packages, baseline, as_of, cfg.command_center_delay_threshold_pp)
        baseline_info = ({"status":"approved", "revision":baseline[0]["revision"], "approval_reference":baseline[0]["approval_reference"], "approved_on":baseline[0]["approved_on"]}
            if baseline else {"status":"not_configured"})
        return {"source":"siteforge", "project_code":project.code, "generated_at":data["generated_at"],
            "measurement":data["measurement"], "packages":packages, "package_count":len(packages),
            "baseline_method":"linear_date_reference_unapproved", "approved_baseline":{**baseline_info,"origin":baseline_origin}, "baseline_status":baseline_status, "alerts":alerts}
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, KeyError, TypeError, OSError, json.JSONDecodeError):
        raise HTTPException(502, "Verified source progress is unavailable or invalid")


@router.get("/projects/{project_id}/planning-monitor")
def planning_monitor(project_id: int, db: DbSession, user: User):
    """Approved SiteForge planning summary; require verified full-project entitlement."""
    import json
    import httpx
    from ..config import get_settings
    cfg = get_settings()
    project = get_project_or_404(db, project_id)
    if user.project_code != project.code:
        raise HTTPException(403, "Project scope denied")
    grant = dict(user.grants).get(project.code)
    if not grant or not grant.get("commercial") or grant.get("full_scope") is not True:
        raise HTTPException(403, "Full-project and commercial reporting permissions required")
    actual_disciplines = {d.code for d in project.disciplines}
    if not actual_disciplines or set(user.discipline_codes) != actual_disciplines:
        raise HTTPException(403, "Complete discipline entitlement required")
    if not cfg.vision360_source_url or not cfg.vision360_service_key:
        raise HTTPException(503, "Planning integration is disabled")
    try:
        mapping = load_project_mapping(cfg.command_center_project_map)
        source_code = to_siteforge_code(project.code, mapping)
        base = cfg.vision360_source_url.rstrip("/")
        if not (base.startswith("https://") or base.startswith("http://siteforge-backend:") or base.startswith("http://backend:")):
            raise HTTPException(503, "Untrusted planning integration URL")
        with httpx.Client(timeout=25.0, follow_redirects=False) as client:
            response = client.get(f"{base}/api/integration/vision360/projects/{source_code}/planning-monitor",
                headers={"X-Vision-Service-Key": cfg.vision360_service_key})
        response.raise_for_status()
        data = response.json()
        if data.get("source") != "siteforge_planning" or data.get("project_code") != source_code:
            raise ValueError("Source project mismatch")
        return data
    except HTTPException:
        raise
    except (ValueError, KeyError, TypeError, httpx.HTTPError, json.JSONDecodeError):
        raise HTTPException(502, "Approved planning summary unavailable")


@router.get('/projects/{project_id}/financial-monitoring')
@router.get('/projects/{project_id}/financial-procurement-monitoring')
def financial_monitoring(project_id:int,db:DbSession,user:User,request:Request):
    """Command Center read-only budget view; no fabricated operational actuals."""
    import httpx
    from ..config import get_settings
    from ..project_identity import load_project_mapping,to_siteforge_code
    cfg=get_settings()
    project=get_project_or_404(db,project_id)
    if project.code != user.project_code:raise HTTPException(403,'Project scope denied')
    grant=dict(user.grants).get(project.code)
    if not grant or not grant.get('commercial'):raise HTTPException(403,'Commercial reporting permission required')
    if not grant.get('full_scope'):raise HTTPException(403,'Financial monitoring requires full-project financial scope')
    if not cfg.command_center_identity_url or not cfg.command_center_identity_service_key:raise HTTPException(503,'Financial source unavailable')
    base=cfg.command_center_identity_url.rstrip('/')
    if not (base.startswith('https://') or base.startswith('http://siteforge-backend:') or base.startswith('http://backend:')):raise HTTPException(503,'Untrusted financial data source')
    try:
        mapping=load_project_mapping(cfg.command_center_project_map)
        source_code=to_siteforge_code(project.code,mapping)
        # Lookup authoritative source ID through already service-protected project master.
        with httpx.Client(timeout=15,follow_redirects=False) as client:
            master=client.get(f'{base}/api/integrations/command-center/project-master/{cfg.command_center_expected_org}',headers={'X-ZerroR-Service-Key':cfg.command_center_identity_service_key})
            master.raise_for_status()
            matches=[x for x in master.json() if x['code'].upper()==source_code.upper()]
            if len(matches)!=1:raise HTTPException(404,'Authoritative project not found')
            endpoint="internal-procurement-monitoring" if request.url.path.endswith("financial-procurement-monitoring") else "internal-summary"
            result=client.get(f"{base}/api/projects/{matches[0]['id']}/financials/{endpoint}",headers={'X-ZerroR-Service-Key':cfg.command_center_identity_service_key})
            result.raise_for_status()
        data=result.json()
        if data.get('project_code','').upper()!=source_code.upper():raise HTTPException(502,'Project mismatch')
        return data
    except httpx.HTTPError:
        raise HTTPException(503,'Financial source unavailable; no financial data substituted')


@router.get('/projects/{project_id}/financial-evidence')
def project_financial_evidence(project_id:int,category:str,db:DbSession,user:User,currency:str|None=None):
    """Authorized read-only proxy; project and commercial grant required."""
    import httpx
    from ..config import get_settings
    from ..project_identity import load_project_mapping,to_siteforge_code
    cfg=get_settings()
    project=get_project_or_404(db,project_id)
    if project.code!=user.project_code:raise HTTPException(403,'Project scope denied')
    grant=dict(user.grants).get(project.code)
    if not grant or not grant.get('commercial') or not grant.get('full_scope'):
        raise HTTPException(403,'Full-scope commercial reporting permission required')
    if not cfg.command_center_identity_url or not cfg.command_center_identity_service_key:
        raise HTTPException(503,'Financial source unavailable')
    base=cfg.command_center_identity_url.rstrip('/')
    if not (base.startswith('https://') or base.startswith('http://siteforge-backend:') or base.startswith('http://backend:')):
        raise HTTPException(503,'Untrusted financial data source')
    try:
        source_code=to_siteforge_code(project.code,load_project_mapping(cfg.command_center_project_map))
        with httpx.Client(timeout=15,follow_redirects=False) as client:
            master=client.get(f'{base}/api/integrations/command-center/project-master/{cfg.command_center_expected_org}',headers={'X-ZerroR-Service-Key':cfg.command_center_identity_service_key})
            master.raise_for_status()
            matches=[x for x in master.json() if x['code'].upper()==source_code.upper()]
            if len(matches)!=1:raise HTTPException(404,'Authoritative project not found')
            result=client.get(f"{base}/api/projects/{matches[0]['id']}/financials/internal-financial-evidence",params={"category":category,"currency":currency} if currency else {"category":category},headers={'X-ZerroR-Service-Key':cfg.command_center_identity_service_key})
            result.raise_for_status()
        data=result.json()
        if data.get('project_code','').upper()!=source_code.upper():raise HTTPException(502,'Project mismatch')
        if data.get('category')!=category:raise HTTPException(502,'Evidence category mismatch')
        return data
    except httpx.HTTPError:
        raise HTTPException(503,'Financial source unavailable; no fallback to manual financial values')


@router.get('/projects/{project_id}/financial-intelligence')
def project_financial_intelligence(project_id:int,db:DbSession,user:User):
    """Authorized read-only proxy; project and commercial grant required."""
    import httpx
    from ..config import get_settings
    from ..project_identity import load_project_mapping,to_siteforge_code
    cfg=get_settings()
    project=get_project_or_404(db,project_id)
    if project.code!=user.project_code:raise HTTPException(403,'Project scope denied')
    grant=dict(user.grants).get(project.code)
    if not grant or not grant.get('commercial') or not grant.get('full_scope'):
        raise HTTPException(403,'Full-scope commercial reporting permission required')
    if not cfg.command_center_identity_url or not cfg.command_center_identity_service_key:
        raise HTTPException(503,'Financial source unavailable')
    base=cfg.command_center_identity_url.rstrip('/')
    if not (base.startswith('https://') or base.startswith('http://siteforge-backend:') or base.startswith('http://backend:')):
        raise HTTPException(503,'Untrusted financial data source')
    try:
        source_code=to_siteforge_code(project.code,load_project_mapping(cfg.command_center_project_map))
        with httpx.Client(timeout=15,follow_redirects=False) as client:
            master=client.get(f'{base}/api/integrations/command-center/project-master/{cfg.command_center_expected_org}',headers={'X-ZerroR-Service-Key':cfg.command_center_identity_service_key})
            master.raise_for_status()
            matches=[x for x in master.json() if x['code'].upper()==source_code.upper()]
            if len(matches)!=1:raise HTTPException(404,'Authoritative project not found')
            result=client.get(f"{base}/api/projects/{matches[0]['id']}/financials/internal-financial-intelligence",headers={'X-ZerroR-Service-Key':cfg.command_center_identity_service_key})
            result.raise_for_status()
        data=result.json()
        if data.get('project_code','').upper()!=source_code.upper():raise HTTPException(502,'Project mismatch')
        return data
    except httpx.HTTPError:
        raise HTTPException(503,'Financial source unavailable; no fallback to manual financial values')

@router.get('/projects/{project_id}/contract-intelligence')
def project_contract_intelligence(project_id:int,db:DbSession,user:User):
    """Read-only, project-mapped source reporting. Never substitute invented zero KPIs."""
    import httpx
    from ..config import get_settings
    from ..project_identity import load_project_mapping,to_siteforge_code
    cfg=get_settings()
    project=get_project_or_404(db,project_id)
    if project.code != user.project_code:raise HTTPException(403,'Project scope denied')
    grant=dict(user.grants).get(project.code)
    if not grant or not grant.get('commercial') or not grant.get('full_scope'):
        raise HTTPException(403,'Full-project commercial reporting permission required')
    if not cfg.command_center_identity_url or not cfg.command_center_identity_service_key:
        raise HTTPException(503,'Contracts source unavailable')
    base=cfg.command_center_identity_url.rstrip('/')
    if not (base.startswith('https://') or base.startswith('http://siteforge-backend:') or base.startswith('http://backend:')):
        raise HTTPException(503,'Untrusted Contracts source')
    code=to_siteforge_code(project.code,load_project_mapping(cfg.command_center_project_map))
    headers={'X-ZerroR-Service-Key':cfg.command_center_identity_service_key}
    try:
        with httpx.Client(timeout=15,follow_redirects=False) as client:
            r=client.get(f'{base}/api/integrations/command-center/project-master/{cfg.command_center_expected_org}',headers=headers)
            r.raise_for_status()
            matches=[m for m in r.json() if m['code'].upper()==code.upper()]
            if len(matches)!=1:raise HTTPException(404,'Authoritative project mapping unavailable')
            data=client.get(f"{base}/api/projects/{matches[0]['id']}/contracts/internal-intelligence",headers=headers)
            data.raise_for_status()
        result=data.json()
        if result.get('project_id')!=matches[0]['id'] or not result.get('read_only'):
            raise HTTPException(502,'Invalid Contracts source response')
        return result
    except httpx.HTTPError:
        raise HTTPException(503,'Contracts source unavailable; no substituted totals')
