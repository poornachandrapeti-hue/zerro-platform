"""Project directory. A contact is not a membership and not an approver."""

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.domains.coordination.models import ApprovalPolicy, PolicyReviewer, PolicyStage

from .models import Company, Project, ProjectCompany, ProjectContact, User, now
from .security import holds


def sees_details(db, user, project):
    return holds(db, user, project, "projects.contact.view") or holds(
        db, user, project, "projects.contact.edit"
    )


def saved_approver(db, project_id, user_id):
    if not user_id:
        return False
    found = (
        db.query(PolicyReviewer.id)
        .join(PolicyStage, PolicyStage.id == PolicyReviewer.stage_id)
        .join(ApprovalPolicy, ApprovalPolicy.id == PolicyStage.policy_id)
        .filter(
            ApprovalPolicy.project_id == project_id,
            ApprovalPolicy.active.is_(True),
            PolicyReviewer.user_id == user_id,
        )
        .first()
    )
    return found is not None


def check_links(db, project, data):
    if data.company_id:
        link = (
            db.query(ProjectCompany)
            .filter_by(project_id=project.id, company_id=data.company_id, active=True)
            .first()
        )
        if not link:
            raise HTTPException(422, "Company is not active on this project")
    if data.user_id:
        person = db.get(User, data.user_id)
        if (
            not person
            or person.organization_id != project.organization_id
            or not person.active
        ):
            raise HTTPException(422, "User is not an active person in this organization")


def present(db, user, project, contact):
    visible = sees_details(db, user, project)
    company = db.get(Company, contact.company_id) if contact.company_id else None
    linked = db.get(User, contact.user_id) if contact.user_id else None
    approver = saved_approver(db, project.id, contact.user_id)
    return {
        "id": contact.id,
        "name": contact.name,
        "function": contact.function,
        "company_id": contact.company_id,
        "company_name": company.name if company else "",
        "user_id": contact.user_id,
        "user_name": linked.name if linked else "",
        "phone": contact.phone if visible else None,
        "email": contact.email if visible else None,
        "details_visible": visible,
        "note": contact.note,
        "active": contact.active,
        "version": contact.version,
        "approver": approver,
    }


def list_contacts(db: Session, user, project: Project):
    rows = (
        db.query(ProjectContact)
        .filter_by(project_id=project.id)
        .order_by(ProjectContact.function, ProjectContact.name, ProjectContact.id)
        .all()
    )
    return [present(db, user, project, row) for row in rows]


def add_contact(db: Session, user, project: Project, data):
    check_links(db, project, data)
    contact = ProjectContact(
        organization_id=project.organization_id,
        project_id=project.id,
        name=data.name,
        function=data.function,
        company_id=data.company_id,
        user_id=data.user_id,
        phone=data.phone,
        email=data.email,
        note=data.note,
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(contact)
    db.flush()
    return contact


def save_contact(db: Session, user, project: Project, contact: ProjectContact, data):
    check_links(db, project, data)
    changed = db.execute(
        update(ProjectContact)
        .where(ProjectContact.id == contact.id, ProjectContact.version == data.version)
        .values(
            name=data.name,
            function=data.function,
            company_id=data.company_id,
            user_id=data.user_id,
            phone=data.phone,
            email=data.email,
            note=data.note,
            active=data.active,
            modified_by=user.id,
            modified_at=now(),
            version=data.version + 1,
        )
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Contact changed by another user; reload before saving")
    db.flush()
    db.refresh(contact)
    return contact
