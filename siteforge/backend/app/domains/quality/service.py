"""Inspection offers for verified construction quantity.

A site engineer offers a released work package, or one activity, at the
verified quantity already stored. A saved quality reviewer accepts or rejects
that offer. Acceptance fills the accepted quantity. Rejection leaves the
package where construction left it. No billing certificate or commissioning
test is created.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import update

from app.domains.construction.models import ConstructionActivity, WorkPackage
from app.domains.construction.monitoring import _tell
from app.domains.construction.progress import activity_measures
from app.domains.construction.service import qty
from app.domains.coordination.service import REVIEW_GUARDS, review_payload
from app.domains.engineering_documents.workflow import submit_record
from app.domains.identity_projects.models import Membership, Role, User
from app.domains.identity_projects.security import permitted
from app.domains.supply_chain.service import _authority, _policy

from .models import QualityOffer, QualityOfferLine, now

INSPECTION = "quality.inspection"
OPEN = {"Draft", "Pending Review", "Returned for Correction"}
EDITABLE = {"Draft", "Returned for Correction"}
OFFERABLE = {"In Progress", "Physically Complete", "Handed Over"}
STATEMENT = (
    "This offer asks quality to accept the verified construction quantity. "
    "Acceptance fills the accepted quantity. It does not certify the work for billing "
    "or create a commissioning test."
)
WATCH = {"Site Engineer", "Discipline Head", "QA/QC", "Project Manager"}


def _bump(db, offer, version, values):
    changed = db.execute(
        update(QualityOffer)
        .where(QualityOffer.id == offer.id, QualityOffer.version == version)
        .values(version=version + 1, modified_at=now(), **values)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This inspection offer changed. Reload it and try again")
    db.refresh(offer)


def _latest_review(db, project, offer):
    from app.domains.coordination.models import ReviewInstance

    return (
        db.query(ReviewInstance)
        .filter_by(project_id=project.id, record_type=INSPECTION, record_id=offer.id)
        .order_by(ReviewInstance.id.desc())
        .first()
    )


def _lines(db, offer):
    return (
        db.query(QualityOfferLine)
        .filter_by(offer_id=offer.id)
        .order_by(QualityOfferLine.id)
        .all()
    )


def latest_acceptance(db, activity):
    return (
        db.query(QualityOfferLine)
        .join(QualityOffer, QualityOffer.id == QualityOfferLine.offer_id)
        .filter(
            QualityOfferLine.activity_id == activity.id,
            QualityOffer.status == "Approved",
        )
        .order_by(QualityOfferLine.id.desc())
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


def _policy_for(db, project, package):
    policy = _policy(db, project, INSPECTION, package.company_id, package.discipline_id)
    if not policy:
        raise HTTPException(422, "Mandatory reviewer configuration is missing")
    _authority(db, project, policy)
    return policy


def _blocking(db, package, activity_id, ignore_id=None):
    rows = (
        db.query(QualityOffer)
        .filter(QualityOffer.package_id == package.id, QualityOffer.status.in_(tuple(OPEN)))
        .all()
    )
    for row in rows:
        if row.id == ignore_id:
            continue
        if row.activity_id is None or activity_id is None or row.activity_id == activity_id:
            return row
    return None


def _activities(db, package, activity_id):
    query = db.query(ConstructionActivity).filter_by(package_id=package.id, active=True)
    if activity_id:
        query = query.filter(ConstructionActivity.id == activity_id)
    rows = query.order_by(ConstructionActivity.code).all()
    if activity_id and not rows:
        raise HTTPException(404, "Activity not found")
    if not rows:
        raise HTTPException(422, "Add the work before offering it for inspection")
    return rows


def _problem(db, package):
    if package.release_state != "Released":
        return "Inspection applies to a released work package"
    if package.status == "On Hold":
        return "Resume the work package before inspection"
    if package.status not in OFFERABLE:
        return "Inspection applies to released work"
    return None


def _freeze_activity(db, activity):
    measured = activity_measures(db, activity)
    weighted = measured["method"] == "Weighted milestones"
    if weighted:
        if measured["verified_percent"] != "100.00":
            raise HTTPException(422, f"{activity.code} is not fully verified")
        prior = latest_acceptance(db, activity)
        if prior and prior.accepted_percent is not None and prior.accepted_percent >= Decimal("100.00"):
            raise HTTPException(422, f"{activity.code} already has this verified quantity accepted")
        from app.domains.quality.requests import percent_accepted

        if not (prior and prior.accepted_percent is not None and prior.accepted_percent >= Decimal("100.00")) and percent_accepted(db, activity):
            raise HTTPException(422, f"{activity.code} already has this verified quantity accepted")
        return {
            "activity_id": activity.id,
            "code": activity.code,
            "name": activity.name,
            "method": measured["method"],
            "scope_quantity": None,
            "unit": "",
            "verified_quantity": None,
            "verified_percent": measured["verified_percent"],
        }
    verified = Decimal(measured["verified_quantity"] or "0")
    if verified <= 0:
        raise HTTPException(422, f"{activity.code} has no verified quantity to offer")
    prior = latest_acceptance(db, activity)
    if prior and prior.accepted_quantity is not None and prior.accepted_quantity >= verified:
        raise HTTPException(422, f"{activity.code} already has this verified quantity accepted")
    from app.domains.quality.requests import inspection_accepted

    if inspection_accepted(db, activity) > 0:
        raise HTTPException(422, f"{activity.code} already has this verified quantity accepted")
    return {
        "activity_id": activity.id,
        "code": activity.code,
        "name": activity.name,
        "method": measured["method"],
        "scope_quantity": measured["scope_quantity"],
        "unit": measured["unit"],
        "verified_quantity": qty(verified),
        "verified_percent": measured["verified_percent"],
    }


def _snapshot(db, package, activity_id):
    activities = [_freeze_activity(db, row) for row in _activities(db, package, activity_id)]
    return {
        "package_id": package.id,
        "package_code": package.code,
        "package_status": package.status,
        "release_state": package.release_state,
        "activities": activities,
        "statement": STATEMENT,
    }


def _replace_lines(db, offer, activities):
    db.query(QualityOfferLine).filter_by(offer_id=offer.id).delete()
    for row in activities:
        db.add(
            QualityOfferLine(
                offer_id=offer.id,
                activity_id=row["activity_id"],
                offered_quantity=Decimal(row["verified_quantity"]) if row["verified_quantity"] else None,
                offered_percent=Decimal(row["verified_percent"]) if row["verified_percent"] else None,
            )
        )
    db.flush()


def offer_view(db, user, project, offer):
    package = db.get(WorkPackage, offer.package_id)
    instance = _latest_review(db, project, offer)
    return {
        "id": offer.id,
        "number": offer.number,
        "package_id": offer.package_id,
        "activity_id": offer.activity_id,
        "package_code": package.code if package else "",
        "package_status": package.status if package else "",
        "release_state": package.release_state if package else "",
        "status": offer.status,
        "statement": offer.statement,
        "payload": offer.payload or {},
        "lines": [
            {
                "activity_id": line.activity_id,
                "offered_quantity": qty(line.offered_quantity) if line.offered_quantity is not None else None,
                "offered_percent": format(line.offered_percent, "f") if line.offered_percent is not None else None,
                "accepted_quantity": qty(line.accepted_quantity) if line.accepted_quantity is not None else None,
                "accepted_percent": format(line.accepted_percent, "f") if line.accepted_percent is not None else None,
            }
            for line in _lines(db, offer)
        ],
        "cancellation_reason": offer.cancellation_reason,
        "version": offer.version,
        "review": review_payload(db, user, instance) if instance else None,
    }


def _activity_row(db, activity):
    measured = activity_measures(db, activity)
    return {
        "id": activity.id,
        "code": activity.code,
        "name": activity.name,
        "method": measured["method"],
        "unit": measured["unit"],
        "scope_quantity": measured["scope_quantity"],
        "verified_quantity": measured["verified_quantity"],
        "verified_percent": measured["verified_percent"],
        "accepted_quantity": measured["accepted_quantity"],
        "accepted_note": measured["accepted_note"],
    }


def board(db, user, project):
    offers = (
        db.query(QualityOffer)
        .filter_by(project_id=project.id)
        .filter(QualityOffer.status != "Cancelled")
        .order_by(QualityOffer.id.desc())
        .all()
    )
    packages = (
        db.query(WorkPackage)
        .filter(
            WorkPackage.project_id == project.id,
            WorkPackage.release_state == "Released",
            WorkPackage.status.in_(tuple(OFFERABLE | {"On Hold"})),
        )
        .order_by(WorkPackage.code)
        .all()
    )
    return {
        "note": STATEMENT,
        "offers": [offer_view(db, user, project, row) for row in offers],
        "packages": [
            {
                "id": package.id,
                "code": package.code,
                "status": package.status,
                "version": package.version,
                "activities": [
                    _activity_row(db, activity)
                    for activity in db.query(ConstructionActivity)
                    .filter_by(package_id=package.id, active=True)
                    .order_by(ConstructionActivity.code)
                    .all()
                ],
            }
            for package in packages
        ],
    }


def add_offer(db, user, project, data):
    package = db.get(WorkPackage, data.package_id)
    if not package or package.project_id != project.id:
        raise HTTPException(404, "Work package not found")
    problem = _problem(db, package)
    if problem:
        raise HTTPException(409, problem)
    if _blocking(db, package, data.activity_id):
        raise HTTPException(409, "This work already has an open inspection offer")
    _activities(db, package, data.activity_id)
    key = data.number.strip().casefold()
    if db.query(QualityOffer).filter_by(project_id=project.id, number_key=key).first():
        raise HTTPException(409, "Inspection number already exists on this project")
    row = QualityOffer(
        organization_id=project.organization_id,
        project_id=project.id,
        package_id=package.id,
        activity_id=data.activity_id,
        number=data.number.strip(),
        number_key=key,
        statement=STATEMENT,
        payload={},
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def submit_offer(db, user, project, offer, version):
    if offer.status == "Returned for Correction":
        raise HTTPException(409, "A returned offer is resubmitted, not submitted again")
    if offer.status != "Draft":
        raise HTTPException(409, "Only a draft offer can be submitted")
    package = db.get(WorkPackage, offer.package_id)
    if not package or package.project_id != project.id:
        raise HTTPException(404, "Work package not found")
    problem = _problem(db, package)
    if problem:
        raise HTTPException(422, problem)
    if _blocking(db, package, offer.activity_id, ignore_id=offer.id):
        raise HTTPException(409, "This work already has an open inspection offer")
    policy = _policy_for(db, project, package)
    payload = _snapshot(db, package, offer.activity_id)
    _replace_lines(db, offer, payload["activities"])
    _bump(db, offer, version, {"status": "Pending Review", "payload": payload, "modified_by": user.id})
    return submit_record(db, user, project, INSPECTION, offer.id, offer.version, policy)


def apply_resubmit(db, user, instance, review_version):
    from app.domains.coordination.service import _close_tasks, _lock, _open_stage, current_stage
    from app.domains.identity_projects.models import Project

    if instance.record_type != INSPECTION:
        return
    if instance.state != "Returned":
        raise HTTPException(409, "Only a returned review can be resubmitted")
    if user.id != instance.submitted_by and not user.organization_admin:
        raise HTTPException(403, "Only the submitter can resubmit")
    project = db.get(Project, instance.project_id)
    offer = db.get(QualityOffer, instance.record_id)
    package = db.get(WorkPackage, offer.package_id) if offer else None
    if not project or not offer or not package or package.project_id != project.id:
        raise HTTPException(404, "Inspection offer not found")
    permitted(db, user, project, "quality.edit")
    if offer.status != "Returned for Correction":
        raise HTTPException(409, "Only a returned offer can be resubmitted")
    problem = _problem(db, package)
    if problem:
        raise HTTPException(422, problem)
    policy = _policy_for(db, project, package)
    payload = _snapshot(db, package, offer.activity_id)
    _replace_lines(db, offer, payload["activities"])
    _lock(db, instance, review_version)
    _close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    _bump(db, offer, offer.version, {"status": "Pending Review", "payload": payload, "modified_by": user.id})
    instance.record_version = offer.version
    instance.policy_id = policy.id
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def cancel_offer(db, user, offer, data):
    if offer.status == "Pending Review":
        raise HTTPException(409, "This offer is in review")
    if offer.status not in EDITABLE:
        raise HTTPException(409, "Only a draft offer can be cancelled here")
    _bump(
        db,
        offer,
        data.version,
        {"status": "Cancelled", "cancellation_reason": data.reason.strip(), "modified_by": user.id},
    )


def on_review_event(db, user, instance, project, action, stage=None):
    if instance.record_type != INSPECTION:
        return
    offer = db.get(QualityOffer, instance.record_id)
    package = db.get(WorkPackage, offer.package_id) if offer else None
    if not offer or not package or package.project_id != project.id:
        return
    kept = package.status
    if action == "advance":
        return
    if action == "return":
        offer.status = "Returned for Correction"
    elif action == "reject":
        offer.status = "Rejected"
    elif instance.state == "Approved":
        offer.status = "Approved"
        for line in _lines(db, offer):
            line.accepted_quantity = line.offered_quantity
            line.accepted_percent = line.offered_percent
        _tell(
            db,
            project,
            _watchers(db, project),
            "Quantity accepted",
            f"{package.code} has an accepted quantity. No billing certificate or commissioning test was created.",
            f"quality.inspection.{offer.id}",
        )
    else:
        return
    if package.status != kept:
        package.status = kept
    offer.version += 1
    offer.modified_by = user.id
    offer.modified_at = now()


def review_guard(db, user, instance, stage, action):
    if instance.record_type != INSPECTION or action != "approve":
        return
    from app.domains.identity_projects.models import Project

    project = db.get(Project, instance.project_id)
    offer = db.get(QualityOffer, instance.record_id)
    package = db.get(WorkPackage, offer.package_id) if offer else None
    if (
        not project
        or not offer
        or not package
        or package.project_id != project.id
        or offer.status != "Pending Review"
    ):
        raise HTTPException(409, "This offer is not awaiting inspection")
    problem = _problem(db, package)
    if problem:
        raise HTTPException(409, problem)


if review_guard not in REVIEW_GUARDS:
    REVIEW_GUARDS.append(review_guard)
