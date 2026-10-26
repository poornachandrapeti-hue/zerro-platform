import re
import secrets, time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from sqlalchemy import select, delete, update
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.config import settings
from . import contacts
from .models import *
from .schemas import *
from .security import (
    authenticated,
    admin,
    permitted,
    holds,
    hash_token,
    session_cookie_name,
    verify_password,
    hasher,
    DUMMY_HASH,
)

PROJECT_TYPES = {
    "Industrial Plant",
    "Refinery",
    "Power Plant",
    "Infrastructure",
    "Oil & Gas",
    "Renewable Energy",
    "Commercial Buildings",
    "Residential Construction",
    "Water & Wastewater",
    "Mining & Minerals",
    "Marine & Ports",
    "Railways & Metro",
    "Airports & Aviation",
    "Pharmaceutical & Healthcare",
    "Data Centers & Technology",
    "Pipeline & Transmission",
    "Other"
}
CURRENCIES = {"INR", "USD", "EUR", "GBP", "AED", "SAR"}
COMMERCIAL_KEYS = ("contract_number", "contract_date", "contract_value", "currency")
COLUMN_EXCLUDE = {
    "discipline_ids",
    "disciplines",
    "main_contractor_company_id",
    "pmc_company_id",
    "subcontractor_ids",
}
POSTAL = {
    "india": re.compile(r"^\d{6}$"),
    "united states": re.compile(r"^\d{5}(?:-\d{4})?$"),
    "usa": re.compile(r"^\d{5}(?:-\d{4})?$"),
    "us": re.compile(r"^\d{5}(?:-\d{4})?$"),
    "united kingdom": re.compile(r"^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$", re.I),
    "uk": re.compile(r"^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$", re.I),
}

router = APIRouter(prefix="/api")
# Single-process local rate limiter. Production deployment requires a shared limiter.
attempts = defaultdict(deque)


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Duplicate value or invalid record reference")


def audit(db, u, action, resource, rid, details=None, project_id=None):
    db.add(
        Audit(
            organization_id=u.organization_id,
            actor_id=u.id,
            action=action,
            resource=resource,
            resource_id=rid,
            details=details or {},
            project_id=project_id,
        )
    )


def public_user(u):
    return dict(
        id=u.id,
        name=u.name,
        email=u.email,
        company_id=u.company_id,
        active=u.active,
        organization_admin=u.organization_admin,
    )


def company(db, u, cid):
    c = db.get(Company, cid)
    if not c or c.organization_id != u.organization_id:
        raise HTTPException(422, "Company outside organization")
    if not c.active:
        raise HTTPException(422, "Company inactive")
    return c


def project(db, u, pid):
    p = db.get(Project, pid)
    if not p or p.organization_id != u.organization_id:
        raise HTTPException(404, "Project not found")
    return p


def company_roles(db, project_id):
    rows = db.query(ProjectCompany).filter_by(project_id=project_id, active=True).all()
    main = next(
        (row.company_id for row in rows if row.participation_type == "Main Contractor"),
        None,
    )
    pmc = next((row.company_id for row in rows if row.participation_type == "PMC"), None)
    subs = [row.company_id for row in rows if row.participation_type == "Subcontractor"]
    return main, pmc, subs


def discipline_payload(db, project_id):
    return [
        {
            "discipline_id": row.discipline_id,
            "scope_description": row.scope_description or "",
            "active": bool(row.active),
        }
        for row in db.query(ProjectDiscipline).filter_by(project_id=project_id)
    ]


def project_dict(db, p, include_commercial=True):
    keys = [
        "id",
        "code",
        "name",
        "description",
        "project_type",
        "status",
        "site_name",
        "address",
        "country",
        "state",
        "city",
        "postal_code",
        "timezone",
        "latitude",
        "longitude",
        "planned_start",
        "planned_finish",
        "actual_start",
        "actual_finish",
        "client_company_id",
        "lead_pm_id",
        "hold_reason",
        "cancellation_reason",
        "contract_number",
        "contract_date",
        "currency",
        "version",
        "created_by",
        "modified_by",
        "created_at",
        "modified_at",
    ]
    data = {k: getattr(p, k) for k in keys}
    data["contract_value"] = (
        None
        if p.contract_value is None
        else format(Decimal(p.contract_value).quantize(Decimal("0.01")), "f")
    )
    client = db.get(Company, p.client_company_id) if p.client_company_id else None
    manager = db.get(User, p.lead_pm_id) if p.lead_pm_id else None
    data["client_name"] = client.name if client else ""
    data["lead_pm_name"] = manager.name if manager else ""
    main, pmc, subs = company_roles(db, p.id)
    data["main_contractor_company_id"] = main
    data["pmc_company_id"] = pmc
    data["subcontractor_ids"] = subs
    records = discipline_payload(db, p.id)
    data["disciplines"] = records
    data["discipline_ids"] = [row["discipline_id"] for row in records if row["active"]]
    if not include_commercial:
        for key in COMMERCIAL_KEYS:
            data.pop(key, None)
    return data


@router.post("/auth/login")
def login(
    data: Login, request: Request, response: Response, db: Session = Depends(get_db)
):
    if request.headers.get("origin") not in settings.origins:
        raise HTTPException(403, "Untrusted request origin")
    tick = time.monotonic()
    key = request.client.host if request.client else "unknown"
    q = attempts[key]
    while q and q[0] < tick - 60:
        q.popleft()
    if len(q) >= 10:
        raise HTTPException(429, "Too many attempts; retry in a minute")
    q.append(tick)
    u = db.query(User).filter_by(email=data.email.strip().lower()).first()
    valid = verify_password(u.password_hash if u else DUMMY_HASH, data.password)
    if not valid or not u or not u.active:
        raise HTTPException(401, "Invalid email or password")
    token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    cookie_name = session_cookie_name(request)
    previous = request.cookies.get(cookie_name, "")
    if previous:
        existing = db.get(LoginSession, hash_token(previous))
        if existing:
            db.delete(existing)
            db.flush()
    db.add(
        LoginSession(
            token_hash=hash_token(token),
            user_id=u.id,
            csrf_token=csrf,
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=settings.session_hours),
        )
    )
    audit(db, u, "login", "users", u.id)
    commit(db)
    response.set_cookie(
        cookie_name,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_hours * 3600,
        path="/",
    )
    return dict(user=public_user(u), csrf_token=csrf)


@router.get("/auth/me")
def me(
    request: Request, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    memberships = []
    for m in (
        db.query(Membership)
        .join(Project, Membership.project_id == Project.id)
        .filter(
            Membership.user_id == u.id,
            Membership.active == True,
            Project.organization_id == u.organization_id,
        )
    ):
        role = db.get(Role, m.role_id)
        permissions = list(role.permissions or [])
        project = db.get(Project, m.project_id)
        from app.domains.supply_chain.service import reviewer_can_view

        if project and "procurement.view" not in permissions and reviewer_can_view(db, u, project):
            permissions.append("procurement.view")
        memberships.append(
            dict(
                id=m.id,
                project_id=m.project_id,
                company_id=m.company_id,
                role=role.name,
                permissions=permissions,
                scope=m.scope,
                discipline_ids=m.discipline_ids,
            )
        )
    return dict(
        user=public_user(u),
        organization=db.get(Organization, u.organization_id).name,
        csrf_token=request.state.login_session.csrf_token,
        memberships=memberships,
    )


@router.post("/auth/logout")
def logout(
    request: Request,
    response: Response,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    db.delete(request.state.login_session)
    audit(db, u, "logout", "users", u.id)
    commit(db)
    response.delete_cookie(
        session_cookie_name(request),
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return {"ok": True}


@router.get("/catalog")
def catalog(u: User = Depends(authenticated), db: Session = Depends(get_db)):
    return dict(
        disciplines=[dict(id=d.id, name=d.name) for d in db.query(Discipline)],
        roles=[
            dict(id=r.id, name=r.name, permissions=r.permissions)
            for r in db.query(Role)
        ],
    )


@router.get("/companies")
def companies(
    u: User = Depends(admin),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    q = db.query(Company).filter_by(organization_id=u.organization_id)
    return dict(
        total=q.count(),
        items=[
            dict(
                id=c.id,
                name=c.name,
                company_type=c.company_type,
                active=c.active,
                version=c.version,
            )
            for c in q.order_by(Company.id).offset(offset).limit(limit)
        ],
    )


@router.post("/companies", status_code=201)
def create_company(
    data: CompanyIn, u: User = Depends(admin), db: Session = Depends(get_db)
):
    c = Company(
        organization_id=u.organization_id,
        name=data.name,
        name_key=data.name.casefold(),
        company_type=data.company_type,
        active=data.active,
    )
    db.add(c)
    db.flush()
    audit(db, u, "create", "companies", c.id, {"name": c.name})
    commit(db)
    return {"id": c.id}


@router.get("/users")
def users(
    u: User = Depends(admin),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    q = db.query(User).filter_by(organization_id=u.organization_id)
    return dict(
        total=q.count(),
        items=[public_user(x) for x in q.order_by(User.id).offset(offset).limit(limit)],
    )


@router.post("/users", status_code=201)
def create_user(data: UserIn, u: User = Depends(admin), db: Session = Depends(get_db)):
    if data.company_id:
        company(db, u, data.company_id)
    if db.query(User).filter_by(email=data.email).first():
        raise HTTPException(409, "Email already registered")
    x = User(
        organization_id=u.organization_id,
        name=data.name,
        email=data.email,
        company_id=data.company_id,
        organization_admin=data.organization_admin,
        password_hash=hasher.hash(data.password),
    )
    db.add(x)
    db.flush()
    audit(
        db,
        u,
        "create",
        "users",
        x.id,
        {"name": x.name, "organization_admin": x.organization_admin},
    )
    commit(db)
    return public_user(x)


@router.put("/users/{uid}")
def edit_user(
    uid: int, data: UserUpdate, u: User = Depends(admin), db: Session = Depends(get_db)
):
    db.execute(
        select(Organization)
        .where(Organization.id == u.organization_id)
        .with_for_update()
    ).scalar_one()
    x = db.get(User, uid)
    if not x or x.organization_id != u.organization_id:
        raise HTTPException(404, "User not found")
    if (
        x.organization_admin
        and x.active
        and (not data.active or not data.organization_admin)
    ):
        if (
            db.query(User)
            .filter_by(
                organization_id=u.organization_id, active=True, organization_admin=True
            )
            .count()
            <= 1
        ):
            raise HTTPException(409, "Cannot remove the last active administrator")
    if not data.active:
        if (
            db.query(Project)
            .filter(
                Project.organization_id == u.organization_id,
                Project.lead_pm_id == x.id,
                Project.status.in_(["Planned", "Active", "On Hold"]),
            )
            .first()
        ):
            raise HTTPException(
                409, "Replace the lead PM before deactivating this user"
            )
        db.execute(delete(LoginSession).where(LoginSession.user_id == uid))
    before = public_user(x)
    x.name = data.name
    x.active = data.active
    x.organization_admin = data.organization_admin
    if "company_id" in data.model_fields_set:
        if not data.company_id:
            raise HTTPException(422, "Employing company is required")
        company(db, u, data.company_id)
        x.company_id = data.company_id
    audit(db, u, "update", "users", uid, {"before": before, "after": public_user(x)})
    commit(db)
    return public_user(x)


def validate_project(db, u, data):
    if data.project_type not in PROJECT_TYPES:
        raise HTTPException(422, "Choose a project type from the list")
    pattern = POSTAL.get((data.country or "").casefold())
    if data.postal_code and pattern and not pattern.fullmatch(data.postal_code.strip()):
        raise HTTPException(422, "Postal code does not match the selected country")
    if data.contract_value is not None and data.contract_value < 0:
        raise HTTPException(422, "Contract value cannot be negative")
    if data.contract_value is not None and not data.currency:
        data.currency = "INR"
    if data.currency and data.currency not in CURRENCIES:
        raise HTTPException(422, "Currency is not supported")
    chosen = [
        data.client_company_id,
        data.main_contractor_company_id,
        data.pmc_company_id,
        *data.subcontractor_ids,
    ]
    chosen = [item for item in chosen if item]
    if len(chosen) != len(set(chosen)):
        raise HTTPException(
            422, "A company can have only one participation type on a project"
        )
    for cid in chosen:
        company(db, u, cid)
    if data.disciplines is not None:
        ids = [row.discipline_id for row in data.disciplines]
        if len(ids) != len(set(ids)):
            raise HTTPException(422, "Duplicate discipline")
        data.discipline_ids = [row.discipline_id for row in data.disciplines if row.active]
    if data.client_company_id:
        company(db, u, data.client_company_id)
    if data.lead_pm_id:
        pm = db.get(User, data.lead_pm_id)
        if (
            not pm
            or pm.organization_id != u.organization_id
            or not pm.active
            or not pm.company_id
        ):
            raise HTTPException(
                422,
                "Lead PM needs an active user and employing company in this organization",
            )
        company(db, u, pm.company_id)
    enabled = set(data.discipline_ids)
    if len(enabled) != len(data.discipline_ids):
        raise HTTPException(422, "Duplicate discipline")
    if enabled - {x.id for x in db.query(Discipline)}:
        raise HTTPException(422, "Unknown discipline")
    if (
        data.planned_start
        and data.planned_finish
        and data.planned_finish < data.planned_start
    ):
        raise HTTPException(422, "Planned finish precedes start")
    if data.actual_finish and not data.actual_start:
        raise HTTPException(422, "Actual finish requires actual start")
    if (
        data.actual_start
        and data.actual_finish
        and data.actual_finish < data.actual_start
    ):
        raise HTTPException(422, "Actual finish precedes start")
    today = datetime.now(ZoneInfo(data.timezone)).date()
    if any(d and d > today for d in [data.actual_start, data.actual_finish]):
        raise HTTPException(422, "Actual dates cannot be in the future")
    if data.status in ["Planned", "Active", "On Hold", "Completed"]:
        if not all(
            [
                data.client_company_id,
                data.lead_pm_id,
                data.site_name,
                data.country,
                data.state,
                data.city,
                data.planned_start,
                data.planned_finish,
                enabled,
            ]
        ):
            raise HTTPException(
                422,
                "Complete client, PM, location, planned dates and disciplines before activation",
            )
    if data.status in ["Active", "Completed"] and not data.actual_start:
        raise HTTPException(422, "Actual start required")
    if data.status == "Completed" and not data.actual_finish:
        raise HTTPException(422, "Actual completion required")
    if data.status == "On Hold" and not data.hold_reason:
        raise HTTPException(422, "Hold reason required")
    if data.status == "Cancelled" and not data.cancellation_reason:
        raise HTTPException(422, "Cancellation reason required")


def company_blocked(db, project_id, company_id):
    if (
        db.query(Membership)
        .filter_by(project_id=project_id, company_id=company_id, active=True)
        .first()
    ):
        return "Deactivate assignments before removing this company"
    from app.domains.engineering_documents.models import Drawing

    if db.query(Drawing).filter_by(project_id=project_id, company_id=company_id).first():
        return "This company is used by drawings"
    return None


def sync_project(db, u, p, data, stored_companies=None):
    existing = db.query(Membership).filter_by(project_id=p.id, active=True).all()
    previous = {
        row.discipline_id
        for row in db.query(ProjectDiscipline).filter_by(project_id=p.id, active=True)
    }
    disabled = previous - set(data.discipline_ids)
    if any(disabled & set(m.discipline_ids) for m in existing if m.scope == "SELECTED"):
        raise HTTPException(409, "Reassign memberships before removing disciplines")
    from app.domains.engineering_documents.models import Drawing

    for did in disabled:
        if db.query(Drawing).filter_by(project_id=p.id, discipline_id=did).first():
            raise HTTPException(409, "This discipline is used by drawings")
    kept = {
        row.discipline_id: row
        for row in db.query(ProjectDiscipline).filter_by(project_id=p.id)
    }
    records = data.disciplines
    if records is None:
        records = [
            DisciplineRecord(
                discipline_id=did,
                scope_description=kept[did].scope_description if did in kept else "",
                active=True,
            )
            for did in data.discipline_ids
        ]
    db.execute(delete(ProjectDiscipline).where(ProjectDiscipline.project_id == p.id))
    for row in records:
        db.add(
            ProjectDiscipline(
                project_id=p.id,
                discipline_id=row.discipline_id,
                scope_description=row.scope_description,
                active=row.active,
            )
        )

    def ensure(cid, kind, overwrite=True):
        if not cid:
            return
        pc = db.query(ProjectCompany).filter_by(project_id=p.id, company_id=cid).first()
        if not pc:
            db.add(
                ProjectCompany(project_id=p.id, company_id=cid, participation_type=kind)
            )
        else:
            pc.active = True
            if overwrite:
                pc.participation_type = kind

    if stored_companies is None:
        stored_main, stored_pmc, stored_subs = company_roles(db, p.id)
        stored_companies = {
            "client_company_id": p.client_company_id,
            "main_contractor_company_id": stored_main,
            "pmc_company_id": stored_pmc,
            "subcontractor_ids": list(stored_subs),
        }

    def drop(kind, company_id):
        if not company_id:
            return
        row = db.query(ProjectCompany).filter_by(
            project_id=p.id,
            company_id=company_id,
            participation_type=kind,
            active=True,
        ).first()
        if not row:
            return
        reason = company_blocked(db, p.id, company_id)
        if reason:
            raise HTTPException(409, reason)
        row.active = False

    def retire(kind, keep, stored):
        if isinstance(keep, list):
            for company_id in stored or []:
                if company_id not in keep:
                    drop(kind, company_id)
            return
        if stored and stored != keep:
            drop(kind, stored)

    ensure(data.client_company_id, "Owner")
    retire("Owner", data.client_company_id, stored_companies.get("client_company_id"))
    ensure(data.main_contractor_company_id, "Main Contractor")
    retire(
        "Main Contractor",
        data.main_contractor_company_id,
        stored_companies.get("main_contractor_company_id"),
    )
    ensure(data.pmc_company_id, "PMC")
    retire("PMC", data.pmc_company_id, stored_companies.get("pmc_company_id"))
    for cid in data.subcontractor_ids:
        ensure(cid, "Subcontractor")
    retire("Subcontractor", data.subcontractor_ids, stored_companies.get("subcontractor_ids"))

    if data.lead_pm_id:
        pm = db.get(User, data.lead_pm_id)
        selected = {
            data.client_company_id,
            data.main_contractor_company_id,
            data.pmc_company_id,
            *data.subcontractor_ids,
        }
        if pm.company_id not in selected:
            employer = db.query(ProjectCompany).filter_by(
                project_id=p.id, company_id=pm.company_id
            ).first()
            if not employer:
                db.add(
                    ProjectCompany(
                        project_id=p.id,
                        company_id=pm.company_id,
                        participation_type="Contractor",
                    )
                )
            else:
                employer.active = True
                employer.participation_type = "Contractor"
        db.flush()
        role = db.query(Role).filter_by(name="Project Manager").one()
        m = (
            db.query(Membership)
            .filter_by(
                project_id=p.id,
                user_id=pm.id,
                role_id=role.id,
                company_id=pm.company_id,
            )
            .first()
        )
        if m:
            m.active = True
            m.scope = "ALL"
            m.discipline_ids = []
        else:
            db.add(
                Membership(
                    project_id=p.id,
                    user_id=pm.id,
                    role_id=role.id,
                    company_id=pm.company_id,
                    scope="ALL",
                    discipline_ids=[],
                )
            )
    # Changing lead PM does not silently remove former PM access; admin reviews memberships explicitly.


def accessible_projects(db, u):
    q = db.query(Project).filter_by(organization_id=u.organization_id)
    if not u.organization_admin:
        ids = (
            select(Membership.project_id)
            .join(Role, Membership.role_id == Role.id)
            .where(Membership.user_id == u.id, Membership.active == True)
        )
        q = q.filter(Project.id.in_(ids))
    return q


@router.get("/projects")
def projects(
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: str = "",
    status: str = "",
    client_id: int = 0,
    discipline_id: int = 0,
):
    q = accessible_projects(db, u)
    if search:
        q = q.filter(
            Project.name.ilike("%" + search + "%")
            | Project.code.ilike("%" + search + "%")
        )
    if status:
        q = q.filter(Project.status == status)
    if client_id:
        q = q.filter(Project.client_company_id == client_id)
    if discipline_id:
        q = q.filter(
            Project.id.in_(
                select(ProjectDiscipline.project_id).where(
                    ProjectDiscipline.discipline_id == discipline_id,
                    ProjectDiscipline.active == True,
                )
            )
        )
    return dict(
        total=q.count(),
        items=[
            project_dict(db, p, include_commercial=False)
            for p in q.order_by(Project.id.desc()).offset(offset).limit(limit)
        ],
    )


@router.get("/projects/filters")
def project_filters(u: User = Depends(authenticated), db: Session = Depends(get_db)):
    rows = accessible_projects(db, u).all()
    client_ids = {row.client_company_id for row in rows if row.client_company_id}
    clients = []
    if client_ids:
        clients = [
            {"id": row.id, "name": row.name}
            for row in db.query(Company)
            .filter(Company.id.in_(client_ids))
            .order_by(Company.name)
        ]
    return {"clients": clients}


@router.get("/projects/{pid}")
def detail(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    p = project(db, u, pid)
    permitted(db, u, p, "projects.view")
    return project_dict(db, p, include_commercial=holds(db, u, p, "projects.commercial.view"))


@router.post("/projects", status_code=201)
def create_project(
    data: ProjectIn, u: User = Depends(admin), db: Session = Depends(get_db)
):
    validate_project(db, u, data)
    if (
        db.query(Project)
        .filter_by(organization_id=u.organization_id, code_key=data.code.casefold())
        .first()
    ):
        raise HTTPException(409, "Project code already exists; choose another code")
    values = data.model_dump(exclude=COLUMN_EXCLUDE)
    p = Project(
        **values,
        code_key=data.code.casefold(),
        organization_id=u.organization_id,
        created_by=u.id,
        modified_by=u.id,
    )
    db.add(p)
    db.flush()
    sync_project(db, u, p, data)
    audit(db, u, "create", "projects", p.id, {"code": p.code})
    commit(db)
    return project_dict(db, p)


@router.put("/projects/{pid}")
def edit_project(
    pid: int,
    data: ProjectUpdate,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    p = project(db, u, pid)
    permitted(db, u, p, "projects.edit")
    from .lifecycle import project_input

    current = project_input(db, p)
    carried = {}
    for key in [
        "client_company_id",
        "lead_pm_id",
        "main_contractor_company_id",
        "pmc_company_id",
    ]:
        if key not in data.model_fields_set:
            carried[key] = getattr(current, key)
    if "subcontractor_ids" not in data.model_fields_set:
        carried["subcontractor_ids"] = list(current.subcontractor_ids)
    if "disciplines" not in data.model_fields_set:
        carried["disciplines"] = current.disciplines
        carried["discipline_ids"] = list(current.discipline_ids)
    if carried:
        data = data.model_copy(update=carried)
    if not u.organization_admin:
        for key in [
            "code",
            "status",
            "client_company_id",
            "lead_pm_id",
            "main_contractor_company_id",
            "pmc_company_id",
        ]:
            if getattr(data, key) != getattr(current, key):
                raise HTTPException(
                    403,
                    "Administrator controls project identity, status, companies and PM",
                )
        if set(data.subcontractor_ids) != set(current.subcontractor_ids):
            raise HTTPException(403, "Administrator controls participating companies")
        if set(data.discipline_ids) != set(current.discipline_ids):
            raise HTTPException(403, "Administrator controls disciplines")
        if data.disciplines is not None:
            sent = sorted(
                (row.discipline_id, row.scope_description, row.active)
                for row in data.disciplines
            )
            stored = sorted(
                (row.discipline_id, row.scope_description, row.active)
                for row in (current.disciplines or [])
            )
            if sent != stored:
                raise HTTPException(403, "Administrator controls disciplines")
    if not holds(db, u, p, "projects.commercial.edit"):
        for key in COMMERCIAL_KEYS:
            if key not in data.model_fields_set:
                continue
            incoming = getattr(data, key)
            stored = getattr(current, key)
            same = (
                Decimal(str(incoming)) == Decimal(str(stored))
                if key == "contract_value" and incoming is not None and stored is not None
                else incoming == stored or (incoming in ("", None) and stored in ("", None))
            )
            if not same:
                raise HTTPException(403, "Commercial edit permission is required")
        data = data.model_copy(
            update={key: getattr(current, key) for key in COMMERCIAL_KEYS}
        )
    if data.status != p.status:
        raise HTTPException(409, "Use the status transition command")
    validate_project(db, u, data)
    before = {k: str(v) for k, v in project_dict(db, p).items()}
    values = data.model_dump(exclude=COLUMN_EXCLUDE | {"version"})
    values.update(
        code_key=data.code.casefold(),
        version=data.version + 1,
        modified_by=u.id,
        modified_at=datetime.now(timezone.utc),
    )
    result = db.execute(
        update(Project)
        .where(Project.id == pid, Project.version == data.version)
        .values(**values)
    )
    if result.rowcount != 1:
        raise HTTPException(
            409, "Project changed by another user; reload before saving"
        )
    sync_project(
        db,
        u,
        p,
        data,
        {
            "client_company_id": current.client_company_id,
            "main_contractor_company_id": current.main_contractor_company_id,
            "pmc_company_id": current.pmc_company_id,
            "subcontractor_ids": list(current.subcontractor_ids or []),
        },
    )
    audit(
        db,
        u,
        "update",
        "projects",
        pid,
        {"before": before, "after": {k: str(v) for k, v in values.items()}},
    )
    commit(db)
    db.refresh(p)
    return project_dict(
        db, p, include_commercial=holds(db, u, p, "projects.commercial.view")
    )


@router.get("/projects/{pid}/companies")
def participants(
    pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    p = project(db, u, pid)
    permitted(db, u, p, "projects.view")
    return [
        dict(
            id=x.id,
            company_id=x.company_id,
            name=db.get(Company, x.company_id).name,
            participation_type=x.participation_type,
            active=x.active,
            version=x.version,
        )
        for x in db.query(ProjectCompany).filter_by(project_id=pid)
    ]


@router.post("/projects/{pid}/companies", status_code=201)
def add_participant(
    pid: int,
    data: ParticipationIn,
    u: User = Depends(admin),
    db: Session = Depends(get_db),
):
    project(db, u, pid)
    company(db, u, data.company_id)
    x = ProjectCompany(project_id=pid, **data.model_dump())
    db.add(x)
    db.flush()
    audit(db, u, "create", "project_companies", x.id)
    commit(db)
    return {"id": x.id}


@router.get("/projects/{pid}/memberships")
def members(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = project(db, u, pid)
    permitted(db, u, found, "projects.view")
    return [
        dict(
            id=m.id,
            user_id=m.user_id,
            name=db.get(User, m.user_id).name,
            role_id=m.role_id,
            role=db.get(Role, m.role_id).name,
            company_id=m.company_id,
            scope=m.scope,
            discipline_ids=m.discipline_ids,
            active=m.active,
        )
        for m in db.query(Membership).filter_by(project_id=pid)
    ]


@router.post("/projects/{pid}/memberships", status_code=201)
def add_member(
    pid: int,
    data: MembershipIn,
    u: User = Depends(admin),
    db: Session = Depends(get_db),
):
    p = project(db, u, pid)
    x = db.get(User, data.user_id)
    if not x or x.organization_id != u.organization_id or not x.active:
        raise HTTPException(422, "Active user in organization required")
    company(db, u, data.company_id)
    if (
        not db.query(ProjectCompany)
        .filter_by(project_id=pid, company_id=data.company_id, active=True)
        .first()
    ):
        raise HTTPException(422, "Add company to project first")
    if not db.get(Role, data.role_id):
        raise HTTPException(422, "Unknown role")
    enabled = {
        d.discipline_id for d in db.query(ProjectDiscipline).filter_by(project_id=pid)
    }
    if data.scope == "SELECTED" and (
        not data.discipline_ids or set(data.discipline_ids) - enabled
    ):
        raise HTTPException(422, "Select enabled disciplines explicitly")
    if data.scope == "ALL" and data.discipline_ids:
        raise HTTPException(422, "ALL scope must have no selected disciplines")
    m = Membership(project_id=pid, **data.model_dump())
    db.add(m)
    db.flush()
    audit(db, u, "create", "memberships", m.id, data.model_dump(), project_id=pid)
    commit(db)
    return {"id": m.id}


@router.delete("/projects/{pid}/memberships/{mid}")
def revoke_member(
    pid: int, mid: int, u: User = Depends(admin), db: Session = Depends(get_db)
):
    p = project(db, u, pid)
    m = db.get(Membership, mid)
    if not m or m.project_id != pid:
        raise HTTPException(404, "Membership not found")
    if (
        p.lead_pm_id == m.user_id
        and db.get(Role, m.role_id).name == "Project Manager"
        and p.status in ["Planned", "Active", "On Hold"]
    ):
        raise HTTPException(409, "Replace the lead PM first")
    m.active = False
    audit(db, u, "deactivate", "memberships", mid, project_id=pid)
    commit(db)
    return {"ok": True}


@router.get("/projects/{pid}/areas")
def areas(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    p = project(db, u, pid)
    permitted(db, u, p, "projects.view")
    return [
        dict(
            id=a.id,
            code=a.code,
            name=a.name,
            area_type=a.area_type,
            parent_id=a.parent_id,
            description=a.description,
            active=a.active,
            version=a.version,
        )
        for a in db.query(Area).filter_by(project_id=pid)
    ]


@router.post("/projects/{pid}/areas", status_code=201)
def create_area(
    pid: int,
    data: AreaIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    p = project(db, u, pid)
    permitted(db, u, p, "projects.manage_areas")
    if data.parent_id:
        parent = db.get(Area, data.parent_id)
        if not parent or parent.project_id != pid or not parent.active:
            raise HTTPException(422, "Parent must belong to this project")
        if (data.area_type, parent.area_type) not in [
            ("Area", "Unit"),
            ("Block", "Area"),
        ]:
            raise HTTPException(422, "Use Unit → Area → Block hierarchy")
    elif data.area_type != "Unit":
        raise HTTPException(422, "Area/Block requires parent")
    a = Area(project_id=pid, code_key=data.code.casefold(), **data.model_dump())
    db.add(a)
    db.flush()
    audit(db, u, "create", "areas", a.id)
    commit(db)
    return {"id": a.id}


def _contact(db, pid, cid):
    row = db.get(ProjectContact, cid)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Contact not found")
    return row


@router.get("/projects/{pid}/contacts")
def project_contacts(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = project(db, u, pid)
    permitted(db, u, found, "projects.view")
    return contacts.list_contacts(db, u, found)


@router.post("/projects/{pid}/contacts", status_code=201)
def create_contact(
    pid: int,
    data: ContactIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = project(db, u, pid)
    permitted(db, u, found, "projects.contact.edit")
    row = contacts.add_contact(db, u, found, data)
    audit(db, u, "create", "project_contacts", row.id, {"name": row.name}, project_id=pid)
    commit(db)
    return contacts.present(db, u, found, row)


@router.put("/projects/{pid}/contacts/{cid}")
def update_contact(
    pid: int,
    cid: int,
    data: ContactUpdateIn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = project(db, u, pid)
    permitted(db, u, found, "projects.contact.edit")
    row = _contact(db, pid, cid)
    contacts.save_contact(db, u, found, row, data)
    audit(
        db,
        u,
        "update",
        "project_contacts",
        row.id,
        {"name": data.name, "active": data.active},
        project_id=pid,
    )
    commit(db)
    return contacts.present(db, u, found, row)


@router.get("/audit")
def audit_events(
    u: User = Depends(admin),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    q = db.query(Audit).filter_by(organization_id=u.organization_id)
    return dict(
        total=q.count(),
        items=[
            dict(
                id=x.id,
                action=x.action,
                resource=x.resource,
                resource_id=x.resource_id,
                actor_id=x.actor_id,
                details=x.details,
                created_at=x.created_at,
            )
            for x in q.order_by(Audit.id.desc()).offset(offset).limit(limit)
        ],
    )



def _command_center_grants(db: Session, u: User) -> list[dict]:
    """Single source of truth for both ticket issuance and live authorization."""
    from .models import Membership, Role, Project, ProjectDiscipline
    grants = []
    projects = db.query(Project).filter_by(organization_id=u.organization_id).all()
    for p in projects:
        permissions = set()
        discipline_ids = set()
        all_disciplines = False
        if u.organization_admin:
            permissions.update(("projects.view", "projects.commercial.view"))
            all_disciplines = True
        else:
            for m in db.query(Membership).filter_by(project_id=p.id, user_id=u.id, active=True):
                role = db.get(Role, m.role_id)
                if role:
                    permissions.update(role.permissions or [])
                if m.scope == "ALL":
                    all_disciplines = True
                else:
                    discipline_ids.update(m.discipline_ids or [])
        if "projects.view" not in permissions:
            continue
        enabled = db.query(ProjectDiscipline).filter_by(project_id=p.id, active=True).all()
        allowed_ids = [x.discipline_id for x in enabled if all_disciplines or x.discipline_id in discipline_ids]
        from .models import Discipline as SiteForgeDiscipline
        authorized_disciplines = db.query(SiteForgeDiscipline).filter(SiteForgeDiscipline.id.in_(allowed_ids)).all() if allowed_ids else []
        discipline_names = {str(x.id): x.name for x in authorized_disciplines}
        # Don't expand memberships into non-assigned disciplines.
        grants.append({"source_project_id": p.id, "code": p.code,
                       "commercial": "projects.commercial.view" in permissions,
                       "discipline_ids": allowed_ids, "discipline_names": discipline_names, "full_scope": all_disciplines})
    return grants

@router.post("/integrations/command-center/ticket")
def command_center_ticket(u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Issue read-only entitlements derived from active SiteForge project memberships."""
    from app.vision_ticket import issue_ticket
    from .models import Membership, Role, Project, ProjectDiscipline
    if not settings.command_center_sso_secret:
        raise HTTPException(503, "Command Center SSO is not configured")
    grants = _command_center_grants(db, u)
    if not grants:
        raise HTTPException(403, "No Command Center project viewing permissions")
    return {"ticket": issue_ticket(settings.command_center_sso_secret, {
        "sub": str(u.id), "org": str(u.organization_id), "role": "VIEWER",
        "grants": grants,
    })}


@router.get("/integrations/command-center/project-master/{organization_id}")
def command_center_project_master(organization_id: int, request: Request, db: Session = Depends(get_db)):
    """Service-only authoritative project identities, strictly scoped to one organization.

    Exposes the project header only: contract value and client name, never contract
    documents or partner details. Command Center shows these only to grants with
    projects.commercial.view, enforced through its live grants.
    """
    import hmac
    from .models import Company, ProjectCompany
    expected = settings.command_center_identity_service_key
    received = request.headers.get("X-ZerroR-Service-Key", "")
    if not expected or not hmac.compare_digest(received, expected):
        raise HTTPException(403, "Service authentication required")
    if organization_id <= 0:
        raise HTTPException(422, "Invalid organization")
    rows = db.scalars(select(Project).where(Project.organization_id == organization_id).order_by(Project.id)).all()
    companies = {c.id: c.name for c in db.scalars(select(Company).where(Company.organization_id == organization_id))}
    owners, main_contractors = {}, {}
    for pc in db.scalars(select(ProjectCompany).where(
            ProjectCompany.project_id.in_([p.id for p in rows] or [0]),
            ProjectCompany.participation_type.in_(("Owner", "Main Contractor")),
            ProjectCompany.active == True).order_by(ProjectCompany.id)):
        target = owners if pc.participation_type == "Owner" else main_contractors
        target.setdefault(pc.project_id, pc.company_id)
    return [{"id": p.id, "code": p.code, "name": p.name, "status": p.status,
             "location": p.site_name or p.city or "", "planned_start": p.planned_start.isoformat() if p.planned_start else None, "currency": p.currency, "planned_finish": p.planned_finish.isoformat() if p.planned_finish else None,
             "client": companies.get(p.client_company_id or owners.get(p.id), ""),
             "main_contractor": companies.get(main_contractors.get(p.id), ""),
             "contract_value": str(p.contract_value) if p.contract_value is not None else None}
            for p in rows]


@router.get("/integrations/command-center/live-grants/{user_id}")
def command_center_live_grants(user_id: int, request: Request, db: Session = Depends(get_db)):
    """Private, service-authenticated authority for Command Center request-time RBAC.

    Never expose this endpoint directly on the public gateway. Missing keys fail closed.
    """
    from hmac import compare_digest
    from .models import User as IdentityUser
    secret = settings.command_center_identity_service_key
    presented = request.headers.get("X-ZerroR-Service-Key", "")
    if not secret or not presented or not compare_digest(secret, presented):
        raise HTTPException(403, "Service authentication required")
    user = db.get(IdentityUser, user_id)
    if not user or not user.active or (settings.vision360_organization_id is not None and user.organization_id != settings.vision360_organization_id):
        raise HTTPException(404, "User is not active in the configured organization")
    return {"sub": str(user.id), "org": str(user.organization_id), "role": "VIEWER", "grants": _command_center_grants(db, user)}
