"""Personnel register and workforce lists.

A personnel record is not a login. Saving one does not create a user, a project
membership, or a role. Linking a login only stores the reference. Ending
employment does not deactivate the login; it asks an organization administrator
to review that access.
"""

from collections import Counter

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.domains.identity_projects.models import Company, Discipline, Project, ProjectCompany, User
from app.domains.identity_projects.security import holds

from .models import MASTER_KINDS, PERSONNEL_STATUSES, PERSONNEL_TYPES, Personnel, WorkforceMaster, now

NOTE = (
    "A personnel record is not a login. Saving a worker does not grant access to ZerroBuild, "
    "and a project role is still given only through project members. Contact, emergency, and "
    "identity details are restricted."
)
RESTRICTED_FIELDS = ("contact_number", "emergency_contact", "date_of_birth", "address", "identity_reference")
MASTER_FIELD = {"designation_id": "Designation", "trade_id": "Trade", "grade_id": "Skill grade"}


def sees_restricted(db, user, project):
    return holds(db, user, project, "hr.restricted")


def project_companies(db, project):
    rows = (
        db.query(Company)
        .join(ProjectCompany, ProjectCompany.company_id == Company.id)
        .filter(ProjectCompany.project_id == project.id, ProjectCompany.active.is_(True))
        .order_by(Company.name)
        .all()
    )
    return rows


def _company_ids(db, project):
    return {row.id for row in project_companies(db, project)}


def masters(db, organization_id):
    return (
        db.query(WorkforceMaster)
        .filter_by(organization_id=organization_id)
        .order_by(WorkforceMaster.kind, WorkforceMaster.name)
        .all()
    )


def present_master(row):
    return {"id": row.id, "kind": row.kind, "name": row.name, "active": row.active, "version": row.version}


def add_master(db, user, data):
    if data.kind not in MASTER_KINDS:
        raise HTTPException(422, "Choose a listed workforce list")
    key = data.name.strip().casefold()
    if db.query(WorkforceMaster).filter_by(organization_id=user.organization_id, kind=data.kind, name_key=key).first():
        raise HTTPException(409, f"{data.kind} {data.name} is already listed")
    row = WorkforceMaster(
        organization_id=user.organization_id,
        kind=data.kind,
        name=data.name.strip(),
        name_key=key,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def save_master(db, user, row, data):
    key = data.name.strip().casefold()
    clash = (
        db.query(WorkforceMaster)
        .filter(
            WorkforceMaster.organization_id == row.organization_id,
            WorkforceMaster.kind == row.kind,
            WorkforceMaster.name_key == key,
            WorkforceMaster.id != row.id,
        )
        .first()
    )
    if clash:
        raise HTTPException(409, f"{row.kind} {data.name} is already listed")
    changed = db.execute(
        update(WorkforceMaster)
        .where(WorkforceMaster.id == row.id, WorkforceMaster.version == data.version)
        .values(name=data.name.strip(), name_key=key, active=data.active, version=data.version + 1)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This list value changed; reload before saving")
    db.flush()
    db.refresh(row)
    return row


def _check(db, user, project, data, current=None):
    if data.personnel_type not in PERSONNEL_TYPES:
        raise HTTPException(422, "Choose Employee, Contract Worker, Temporary Worker, or Consultant")
    if data.status not in PERSONNEL_STATUSES:
        raise HTTPException(422, "Choose Active, Inactive, or Separated")
    company = db.get(Company, data.company_id)
    if not company or company.organization_id != project.organization_id:
        raise HTTPException(422, "Choose an employing company")
    if company.id not in _company_ids(db, project):
        raise HTTPException(422, "The employing company is not active on this project")
    for field, kind in MASTER_FIELD.items():
        value = getattr(data, field)
        if value is None:
            if field == "grade_id":
                continue
            raise HTTPException(422, f"Choose a {kind.lower()}")
        row = db.get(WorkforceMaster, value)
        if not row or row.organization_id != project.organization_id or row.kind != kind:
            raise HTTPException(422, f"Choose a {kind.lower()} from the workforce list")
        if not row.active and (current is None or getattr(current, field) != value):
            raise HTTPException(422, f"{kind} {row.name} is no longer active")
    if data.discipline_id is not None and not db.get(Discipline, data.discipline_id):
        raise HTTPException(422, "Choose a listed discipline")
    if data.end_date and data.end_date < data.start_date:
        raise HTTPException(422, "Employment end date cannot be before the start date")
    if data.status == "Separated" and not data.end_date:
        raise HTTPException(422, "Enter the employment end date when a person is separated")
    if data.supervisor_id is not None:
        boss = db.get(Personnel, data.supervisor_id)
        if not boss or boss.organization_id != project.organization_id:
            raise HTTPException(422, "Choose a supervisor from the personnel register")
        if current is not None and boss.id == current.id:
            raise HTTPException(422, "A person cannot supervise themselves")
    if data.user_id is not None:
        login = db.get(User, data.user_id)
        if not login or login.organization_id != project.organization_id:
            raise HTTPException(422, "Choose a login account in this organization")
        taken = db.query(Personnel).filter(Personnel.user_id == data.user_id)
        if current is not None:
            taken = taken.filter(Personnel.id != current.id)
        if taken.first():
            raise HTTPException(409, "That login account is already linked to another person")
    code_key = data.code.strip().casefold()
    clash = db.query(Personnel).filter(Personnel.company_id == data.company_id, Personnel.code_key == code_key)
    if current is not None:
        clash = clash.filter(Personnel.id != current.id)
    if clash.first():
        raise HTTPException(409, f"Worker code {data.code} is already used by {company.name}")
    return code_key


def _restricted_values(db, user, project, data, current=None):
    allowed = sees_restricted(db, user, project)
    if allowed:
        return {field: getattr(data, field) for field in RESTRICTED_FIELDS}
    supplied = any(getattr(data, field) not in ("", None) for field in RESTRICTED_FIELDS)
    if current is None and supplied:
        raise HTTPException(403, "Contact, emergency, and identity details need restricted HR access")
    return {}


def _access_review(db, project, person):
    """Ending employment asks for a login review. It does not deactivate the login."""
    if person.status != "Separated" or not person.user_id:
        return
    login = db.get(User, person.user_id)
    if not login or not login.active:
        return
    from app.domains.coordination.jobs import notify

    admins = db.query(User).filter_by(organization_id=project.organization_id, organization_admin=True, active=True).all()
    for admin in admins:
        notify(
            db,
            admin,
            "Login access review needed",
            "A person whose employment ended still has an active login. Review that access in People & access.",
            f"hr:personnel:{person.id}:access-review:{person.version}:{admin.id}",
            project_id=project.id,
            link=f"/projects/{project.id}",
        )


def add_person(db: Session, user, project: Project, data):
    code_key = _check(db, user, project, data)
    restricted = _restricted_values(db, user, project, data)
    person = Personnel(
        organization_id=project.organization_id,
        company_id=data.company_id,
        code=data.code.strip(),
        code_key=code_key,
        full_name=data.full_name.strip(),
        personnel_type=data.personnel_type,
        designation_id=data.designation_id,
        trade_id=data.trade_id,
        grade_id=data.grade_id,
        discipline_id=data.discipline_id,
        start_date=data.start_date,
        end_date=data.end_date,
        supervisor_id=data.supervisor_id,
        status=data.status,
        user_id=data.user_id,
        created_by=user.id,
        modified_by=user.id,
        **restricted,
    )
    db.add(person)
    db.flush()
    _access_review(db, project, person)
    return person


def save_person(db: Session, user, project: Project, person: Personnel, data):
    if person.company_id not in _company_ids(db, project):
        raise HTTPException(404, "Person not found on this project")
    code_key = _check(db, user, project, data, current=person)
    values = {
        "company_id": data.company_id,
        "code": data.code.strip(),
        "code_key": code_key,
        "full_name": data.full_name.strip(),
        "personnel_type": data.personnel_type,
        "designation_id": data.designation_id,
        "trade_id": data.trade_id,
        "grade_id": data.grade_id,
        "discipline_id": data.discipline_id,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "supervisor_id": data.supervisor_id,
        "status": data.status,
        "user_id": data.user_id,
        "modified_by": user.id,
        "modified_at": now(),
        "version": data.version + 1,
        **_restricted_values(db, user, project, data, current=person),
    }
    changed = db.execute(
        update(Personnel).where(Personnel.id == person.id, Personnel.version == data.version).values(**values)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This person changed; reload before saving")
    db.flush()
    db.refresh(person)
    _access_review(db, project, person)
    return person


def present_person(db, person, restricted, names):
    login = db.get(User, person.user_id) if person.user_id else None
    boss = db.get(Personnel, person.supervisor_id) if person.supervisor_id else None
    row = {
        "id": person.id,
        "code": person.code,
        "full_name": person.full_name,
        "company_id": person.company_id,
        "company_name": names["company"].get(person.company_id, ""),
        "personnel_type": person.personnel_type,
        "designation_id": person.designation_id,
        "designation": names["master"].get(person.designation_id, ""),
        "trade_id": person.trade_id,
        "trade": names["master"].get(person.trade_id, ""),
        "grade_id": person.grade_id,
        "grade": names["master"].get(person.grade_id, "") if person.grade_id else "",
        "discipline_id": person.discipline_id,
        "discipline": names["discipline"].get(person.discipline_id, "") if person.discipline_id else "",
        "start_date": person.start_date.isoformat(),
        "end_date": person.end_date.isoformat() if person.end_date else None,
        "supervisor_id": person.supervisor_id,
        "supervisor_name": boss.full_name if boss else "",
        "status": person.status,
        "user_id": person.user_id,
        "login_name": login.name if login else "",
        "login_active": bool(login and login.active),
        "access_review": bool(person.status == "Separated" and login and login.active),
        "restricted_visible": restricted,
        "version": person.version,
    }
    for field in RESTRICTED_FIELDS:
        value = getattr(person, field)
        if not restricted:
            row[field] = None
        elif field == "date_of_birth":
            row[field] = value.isoformat() if value else None
        else:
            row[field] = value
    return row


def board(db: Session, user, project: Project):
    companies = project_companies(db, project)
    company_ids = [row.id for row in companies]
    people = (
        db.query(Personnel)
        .filter(Personnel.company_id.in_(company_ids or [-1]))
        .order_by(Personnel.full_name, Personnel.id)
        .all()
    )
    master_rows = masters(db, project.organization_id)
    disciplines = db.query(Discipline).order_by(Discipline.name).all()
    names = {
        "company": {row.id: row.name for row in companies},
        "master": {row.id: row.name for row in master_rows},
        "discipline": {row.id: row.name for row in disciplines},
    }
    restricted = sees_restricted(db, user, project)
    rows = [present_person(db, person, restricted, names) for person in people]
    active = [row for row in rows if row["status"] == "Active"]
    logins = (
        db.query(User)
        .filter_by(organization_id=project.organization_id, active=True)
        .order_by(User.name)
        .all()
    )
    payload = {
        "note": NOTE,
        "restricted_visible": restricted,
        "personnel": rows,
        "masters": [present_master(row) for row in master_rows],
        "master_kinds": list(MASTER_KINDS),
        "personnel_types": list(PERSONNEL_TYPES),
        "statuses": list(PERSONNEL_STATUSES),
        "companies": [{"id": row.id, "name": row.name} for row in companies],
        "disciplines": [{"id": row.id, "name": row.name} for row in disciplines],
        "logins": [{"id": row.id, "name": row.name, "email": row.email} for row in logins],
        "counts": {
            "personnel": len(rows),
            "active": len(active),
            "inactive": sum(1 for row in rows if row["status"] == "Inactive"),
            "separated": sum(1 for row in rows if row["status"] == "Separated"),
            "without_login": sum(1 for row in rows if not row["user_id"]),
            "access_reviews": sum(1 for row in rows if row["access_review"]),
        },
        "by_type": dict(Counter(row["personnel_type"] for row in active)),
        "by_company": dict(Counter(row["company_name"] for row in active)),
        "by_trade": dict(Counter(row["trade"] for row in active)),
        "count_note": "Counts are distinct people employed by companies active on this project. They are not deployment, attendance, or availability.",
    }
    from . import attendance, credentials, deployments, leave, monitor, offboarding

    deployments.supplement(db, user, project, payload, names)
    attendance.supplement(db, user, project, payload, names)
    leave.supplement(db, user, project, payload, names)
    credentials.supplement(db, user, project, payload, names)
    offboarding.supplement(db, user, project, payload)
    return monitor.supplement(db, user, project, payload)
