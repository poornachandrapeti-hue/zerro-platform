"""Quality dashboard counts and in-app alerts.

Counts use quality records only. Email stays off. Opening the dashboard does
not accept work, release a hold, or certify billing.
"""

from datetime import date, timedelta
from decimal import Decimal

from app.domains.coordination.jobs import notify
from app.domains.identity_projects.models import Membership, Role, User
from app.domains.supply_chain.models import GoodsReceipt, GoodsReceiptLine

from .competence import CALIBRATION_NOTE, QUALIFICATION_NOTE
from .findings import HOLD_OPEN, OPEN_NCR
from .material import line_balance
from .models import (
    Calibration,
    Concession,
    ConstructionRequest,
    MaterialInspection,
    Nonconformance,
    Qualification,
    QualityDocument,
    QualityForm,
    QualityDossier,
    QualityHold,
    QualityOffer,
    QualityPunch,
)

NOTE = (
    "These counts come from quality records on this project. "
    "Qualifications and calibrations are kept by Quality. HR and Equipment are not the source. "
    "Alerts stay in the workspace. Email stays off. This does not accept work or certify billing."
)
WINDOW = 30


def _qa(db, project):
    people = []
    seen = set()
    for member in db.query(Membership).filter_by(project_id=project.id, active=True):
        if member.user_id in seen:
            continue
        person = db.get(User, member.user_id)
        role = db.get(Role, member.role_id)
        if person and person.active and role and role.name == "QA/QC":
            seen.add(person.id)
            people.append(person)
    return people


def _due_state(due, today):
    if due < today:
        return "Expired"
    if due <= today + timedelta(days=WINDOW):
        return "Expiring"
    return ""


def raise_alerts(db, project):
    today = date.today()
    people = _qa(db, project)
    for row in db.query(Qualification).filter_by(project_id=project.id, status="Approved"):
        state = _due_state(row.valid_to, today)
        if not state:
            continue
        title = "Qualification expired" if state == "Expired" else "Qualification expiring"
        for person in people:
            notify(
                db,
                person,
                title,
                f"{row.number} is {state.lower()} on {row.valid_to.isoformat()}. This does not accept work or certify billing.",
                f"quality.qualification.{row.id}.{state.lower()}",
                project_id=project.id,
                link=f"/projects/{project.id}",
            )
    for row in db.query(Calibration).filter_by(project_id=project.id, status="Approved"):
        state = _due_state(row.due_on, today)
        if not state:
            continue
        title = "Calibration expired" if state == "Expired" else "Calibration expiring"
        for person in people:
            notify(
                db,
                person,
                title,
                f"{row.number} is {state.lower()} on {row.due_on.isoformat()}. This does not accept work or certify billing.",
                f"quality.calibration.{row.id}.{state.lower()}",
                project_id=project.id,
                link=f"/projects/{project.id}",
            )
    for row in db.query(Nonconformance).filter(
        Nonconformance.project_id == project.id,
        Nonconformance.status.in_(tuple(OPEN_NCR)),
        Nonconformance.target_on < today,
    ):
        owner = db.get(User, row.owner_id)
        recipients = list(people)
        if owner and owner.active and owner not in recipients:
            recipients.append(owner)
        for person in recipients:
            notify(
                db,
                person,
                "NCR overdue",
                f"{row.number} is past {row.target_on.isoformat()}. Elapsed time does not close it or certify billing.",
                f"quality.ncr.{row.id}.overdue",
                project_id=project.id,
                link=f"/projects/{project.id}",
            )


def _first_pass(db, project):
    rows = (
        db.query(ConstructionRequest)
        .filter_by(project_id=project.id, status="Approved")
        .order_by(ConstructionRequest.id)
        .all()
    )
    seen = set()
    accepted = partial = rejected = 0
    for row in rows:
        if row.follows_id or row.activity_id in seen:
            continue
        seen.add(row.activity_id)
        if row.outcome == "Accepted":
            accepted += 1
        elif row.outcome == "Partially Accepted":
            partial += 1
        elif row.outcome == "Rejected":
            rejected += 1
    reinspections = (
        db.query(ConstructionRequest)
        .filter(
            ConstructionRequest.project_id == project.id,
            ConstructionRequest.follows_id.is_not(None),
            ConstructionRequest.status != "Cancelled",
        )
        .count()
    )
    return {
        "accepted": accepted,
        "partial": partial,
        "rejected": rejected,
        "originals": accepted + partial + rejected,
        "reinspections": reinspections,
    }


def _pending_reviews(db, project):
    total = 0
    for model in (QualityOffer, ConstructionRequest, MaterialInspection, QualityDocument, QualityForm, Concession):
        total += db.query(model).filter_by(project_id=project.id, status="Pending Review").count()
    total += db.query(Nonconformance).filter(
        Nonconformance.project_id == project.id,
        Nonconformance.status.in_(("Pending Review", "Pending Verification")),
    ).count()
    total += db.query(QualityHold).filter_by(project_id=project.id, status="Pending Release").count()
    total += db.query(Qualification).filter_by(project_id=project.id, status="Pending Review").count()
    total += db.query(Calibration).filter_by(project_id=project.id, status="Pending Review").count()
    return total


def _material_lines(db, project):
    count = 0
    for receipt in db.query(GoodsReceipt).filter_by(project_id=project.id, status="Posted"):
        for line in db.query(GoodsReceiptLine).filter_by(goods_receipt_id=receipt.id):
            balance = line_balance(db, line)
            if Decimal(balance["pending"]) > 0:
                count += 1
    return count


def _expiring(db, project, today):
    rows = []
    for row in db.query(Qualification).filter_by(project_id=project.id, status="Approved"):
        state = _due_state(row.valid_to, today)
        if state:
            person = db.get(User, row.person_id)
            rows.append(
                {
                    "kind": "Qualification",
                    "number": row.number,
                    "label": person.name if person else "",
                    "due": row.valid_to.isoformat(),
                    "state": state,
                }
            )
    for row in db.query(Calibration).filter_by(project_id=project.id, status="Approved"):
        state = _due_state(row.due_on, today)
        if state:
            rows.append(
                {
                    "kind": "Calibration",
                    "number": row.number,
                    "label": row.equipment_code,
                    "due": row.due_on.isoformat(),
                    "state": state,
                }
            )
    return rows


def board(db, project):
    today = date.today()
    passed = _first_pass(db, project)
    expiring = _expiring(db, project, today)
    impacts = []
    for row in db.query(Qualification).filter_by(project_id=project.id, status="Withdrawn"):
        person = db.get(User, row.person_id)
        from .competence import _affected

        impacts.append(
            {
                "number": row.number,
                "person": person.name if person else "",
                "reason": row.withdrawal_reason,
                "inspections": _affected(db, row),
            }
        )
    return {
        "note": NOTE,
        "qualification_note": QUALIFICATION_NOTE,
        "calibration_note": CALIBRATION_NOTE,
        "open_ncrs": db.query(Nonconformance).filter(
            Nonconformance.project_id == project.id, Nonconformance.status.in_(tuple(OPEN_NCR))
        ).count(),
        "overdue_ncrs": db.query(Nonconformance).filter(
            Nonconformance.project_id == project.id,
            Nonconformance.status.in_(tuple(OPEN_NCR)),
            Nonconformance.target_on < today,
        ).count(),
        "active_holds": db.query(QualityHold).filter(
            QualityHold.project_id == project.id, QualityHold.status.in_(tuple(HOLD_OPEN))
        ).count(),
        "pending_reviews": _pending_reviews(db, project),
        "pending_material_lines": _material_lines(db, project),
        "blocking_punches": db.query(QualityPunch).filter(
            QualityPunch.project_id == project.id,
            QualityPunch.blocking.is_(True),
            QualityPunch.status.in_(("Open", "Pending Closure", "Closure Returned")),
        ).count(),
        "approved_dossiers": db.query(QualityDossier).filter_by(project_id=project.id, status="Approved").count(),
        "first_pass": passed,
        "expiring": expiring,
        "impacts": impacts,
    }
