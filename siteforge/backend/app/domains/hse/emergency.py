"""Emergency preparedness records.

Contacts, muster points, equipment locations, plan references, and drills are
records. They do not place the emergency call and they do not hold work.
Phone and email stay on the project contact.
"""

from datetime import timedelta

from fastapi import HTTPException

from app.domains.identity_projects.contacts import present
from app.domains.identity_projects.models import ProjectContact

from .models import (
    HseDocument,
    HseDrill,
    HseDrillAck,
    HseEmergencyContact,
    HseEmergencyGear,
    HseEmergencyPlan,
    HseEmergencyRule,
    HseMusterPoint,
    now,
)
from .service import _bump

EMERGENCY_NOTE = (
    "This record does not start or replace the emergency response. "
    "Notifications are supplementary. Name the approved communication procedure. "
    "This application does not place the emergency call, and these records do not hold work."
)
CONTACT_NOTE = "Phone and email stay on the project contact. This record does not copy them."
GEAR_NOTE = "This names where emergency equipment is kept. The equipment register is not the source."
DRILL_NOTE = "Attendance is an acknowledgment on this drill. A crew assignment is not attendance."
FINDING_NOTE = "A finding on this drill is not an action. Open Actions to record one."
SUGGESTED_RESPONSE_ROLES = ("Incident controller", "First aid", "Muster warden")


def _key(value):
    return value.strip().casefold()


def _today():
    return now().date()


def _rule(db, project_id):
    return db.query(HseEmergencyRule).filter_by(project_id=project_id).first()


def _member():
    from .service import _area, _member, _tell, _watchers

    return _area, _member, _tell, _watchers


def save_rule(db, user, project, data):
    row = _rule(db, project.id)
    if row:
        row.procedure = data.procedure.strip()
        row.review_days = data.review_days
        return row
    row = HseEmergencyRule(
        organization_id=project.organization_id,
        project_id=project.id,
        procedure=data.procedure.strip(),
        review_days=data.review_days,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def _contact(db, project, contact_id):
    row = db.get(ProjectContact, contact_id)
    if not row or row.project_id != project.id or not row.active:
        raise HTTPException(422, "Choose an active project contact")
    return row


def add_contact(db, user, project, data):
    contact = _contact(db, project, data.contact_id)
    if db.query(HseEmergencyContact).filter_by(project_id=project.id, contact_id=contact.id).first():
        raise HTTPException(409, "That contact is already on the emergency list")
    row = HseEmergencyContact(
        organization_id=project.organization_id,
        project_id=project.id,
        contact_id=contact.id,
        response_role=data.response_role.strip(),
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def verify_contact(db, user, project, row, version):
    contact = _contact(db, project, row.contact_id)
    if contact.user_id and contact.user_id == user.id:
        raise HTTPException(403, "You cannot verify your own emergency contact")
    if row.status != "Recorded":
        raise HTTPException(409, "This emergency contact is already verified")
    rule = _rule(db, project.id)
    due = None
    if rule and rule.review_days:
        due = _today() + timedelta(days=rule.review_days)
    _bump(
        db,
        HseEmergencyContact,
        row,
        version,
        {"status": "Verified", "verified_by": user.id, "verified_at": now(), "review_due_on": due},
    )
    return row


def display_status(row):
    if row.status == "Verified" and row.review_due_on and row.review_due_on < _today():
        return "Review due"
    return row.status


def add_muster(db, user, project, data):
    area, _, _, _ = _member()
    area(db, project, data.area_id)
    key = _key(data.name)
    if db.query(HseMusterPoint).filter_by(project_id=project.id, name_key=key).first():
        raise HTTPException(409, "That muster point already exists")
    row = HseMusterPoint(
        organization_id=project.organization_id,
        project_id=project.id,
        name=data.name.strip(),
        name_key=key,
        area_id=data.area_id,
        note=data.note.strip(),
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def add_gear(db, user, project, data):
    area, _, _, _ = _member()
    area(db, project, data.area_id)
    key = _key(data.name)
    if db.query(HseEmergencyGear).filter_by(project_id=project.id, name_key=key).first():
        raise HTTPException(409, "That equipment location already exists")
    row = HseEmergencyGear(
        organization_id=project.organization_id,
        project_id=project.id,
        name=data.name.strip(),
        name_key=key,
        area_id=data.area_id,
        location=data.location.strip(),
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def add_plan(db, user, project, data):
    if data.document_id:
        document = db.get(HseDocument, data.document_id)
        if not document or document.project_id != project.id:
            raise HTTPException(422, "Choose an HSE document on this project")
    key = _key(data.number)
    if db.query(HseEmergencyPlan).filter_by(project_id=project.id, number_key=key).first():
        raise HTTPException(409, "That emergency plan number already exists")
    row = HseEmergencyPlan(
        organization_id=project.organization_id,
        project_id=project.id,
        number=data.number.strip(),
        number_key=key,
        title=data.title.strip(),
        engineering_reference=data.engineering_reference.strip(),
        document_id=data.document_id,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def add_drill(db, user, project, data):
    key = _key(data.number)
    if db.query(HseDrill).filter_by(project_id=project.id, number_key=key).first():
        raise HTTPException(409, "That drill number already exists")
    row = HseDrill(
        organization_id=project.organization_id,
        project_id=project.id,
        number=data.number.strip(),
        number_key=key,
        title=data.title.strip(),
        planned_on=data.planned_on,
        findings=data.findings.strip(),
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def hold_drill(db, row, version):
    if row.status != "Planned":
        raise HTTPException(409, "Only a planned drill can be marked held")
    _bump(db, HseDrill, row, version, {"status": "Held"})
    return row


def acknowledge(db, project, row, data):
    _, member, _, _ = _member()
    if row.status != "Held":
        raise HTTPException(409, "Acknowledge attendance after the drill is held")
    member(db, project, data.member_id, "attendee")
    if db.query(HseDrillAck).filter_by(drill_id=row.id, member_id=data.member_id).first():
        raise HTTPException(409, "That person is already acknowledged on this drill")
    ack = HseDrillAck(drill_id=row.id, member_id=data.member_id, evidence=data.evidence.strip())
    db.add(ack)
    db.flush()
    return ack


def _name(db, user_id):
    from app.domains.identity_projects.models import User

    if not user_id:
        return ""
    person = db.get(User, user_id)
    return person.name if person else ""


def contact_view(db, user, project, row):
    contact = db.get(ProjectContact, row.contact_id)
    shown = present(db, user, project, contact) if contact else {}
    return {
        "id": row.id,
        "contact_id": row.contact_id,
        "name": shown.get("name", ""),
        "function": shown.get("function", ""),
        "phone": shown.get("phone"),
        "email": shown.get("email"),
        "details_visible": shown.get("details_visible", False),
        "response_role": row.response_role,
        "status": display_status(row),
        "stored_status": row.status,
        "review_due_on": row.review_due_on.isoformat() if row.review_due_on else None,
        "version": row.version,
        "statement": CONTACT_NOTE,
    }


def drill_view(db, row):
    acks = db.query(HseDrillAck).filter_by(drill_id=row.id).all()
    return {
        "id": row.id,
        "number": row.number,
        "title": row.title,
        "planned_on": row.planned_on.isoformat(),
        "status": row.status,
        "findings": row.findings,
        "version": row.version,
        "statement": DRILL_NOTE,
        "finding_note": FINDING_NOTE,
        "acknowledgments": [{"member_name": _name(db, item.member_id), "evidence": item.evidence} for item in acks],
    }


def _remind(db, project, rows):
    _, _, tell, watchers = _member()
    people = watchers(db, project)
    told = False
    for row in rows:
        if display_status(row) != "Review due":
            continue
        tell(
            db,
            project,
            people,
            "Emergency contact review is due",
            f"{contact_name(db, row)} is due for review. This notice does not place the emergency call.",
            f"hse.emergency.contact.{row.id}.review",
        )
        told = True
    if told:
        db.commit()


def contact_name(db, row):
    contact = db.get(ProjectContact, row.contact_id)
    return contact.name if contact else "Emergency contact"


def supplement(db, user, project, payload):
    from app.domains.identity_projects.contacts import list_contacts

    rule = _rule(db, project.id)
    contacts = db.query(HseEmergencyContact).filter_by(project_id=project.id).order_by(HseEmergencyContact.id.desc()).all()
    _remind(db, project, contacts)
    drills = db.query(HseDrill).filter_by(project_id=project.id).order_by(HseDrill.id.desc()).all()
    payload["emergency_note"] = EMERGENCY_NOTE
    payload["gear_note"] = GEAR_NOTE
    payload["drill_note"] = DRILL_NOTE
    payload["drill_finding_note"] = FINDING_NOTE
    payload["suggested_response_roles"] = list(SUGGESTED_RESPONSE_ROLES)
    payload["emergency_rule"] = {
        "procedure": rule.procedure if rule else "",
        "review_days": rule.review_days if rule else None,
    }
    payload["project_contacts"] = list_contacts(db, user, project)
    payload["emergency_contacts"] = [contact_view(db, user, project, row) for row in contacts]
    payload["muster_points"] = [
        {"id": row.id, "name": row.name, "note": row.note}
        for row in db.query(HseMusterPoint).filter_by(project_id=project.id).order_by(HseMusterPoint.name)
    ]
    payload["emergency_gear"] = [
        {"id": row.id, "name": row.name, "location": row.location, "statement": GEAR_NOTE}
        for row in db.query(HseEmergencyGear).filter_by(project_id=project.id).order_by(HseEmergencyGear.name)
    ]
    payload["emergency_plans"] = [
        {"id": row.id, "number": row.number, "title": row.title, "engineering_reference": row.engineering_reference}
        for row in db.query(HseEmergencyPlan).filter_by(project_id=project.id).order_by(HseEmergencyPlan.id.desc())
    ]
    payload["drills"] = [drill_view(db, row) for row in drills]
    payload["counts"]["emergency_contacts"] = len(contacts)
    payload["counts"]["emergency_reviews_due"] = sum(display_status(row) == "Review due" for row in contacts)
    payload["counts"]["drills"] = len(drills)
    return payload


def work_line():
    return {"emergency_note": EMERGENCY_NOTE}
