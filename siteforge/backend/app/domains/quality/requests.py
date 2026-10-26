"""Construction inspection requests against a discipline form.

A request covers one activity at the verified quantity that is not already
accepted. The discipline checklist is copied from an approved template and
frozen on submit. A saved reviewer makes the outcome effective. Approval does
not certify billing, release a hold, or create an NCR.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import update

from app.domains.construction.models import ConstructionActivity, WorkPackage
from app.domains.construction.monitoring import _tell
from app.domains.construction.service import qty
from app.domains.coordination.service import REVIEW_GUARDS, review_payload
from app.domains.engineering_documents.workflow import submit_record
from app.domains.identity_projects.models import Membership, User
from app.domains.identity_projects.security import holds
from app.domains.supply_chain.service import _authority, _policy, _project_member

from .models import (
    ConstructionRequest,
    ConstructionResult,
    QualityCheckpoint,
    QualityDocument,
    QualityForm,
    QualityOffer,
    QualityOfferLine,
    now,
)

CONSTRUCTION = "quality.construction"
OPEN = {"Draft", "Pending Review", "Returned for Correction"}
EDITABLE = {"Draft", "Returned for Correction"}
RESULTS = {"Pass", "Fail", "Not applicable"}
OUTCOMES = {"Accepted", "Partially Accepted", "Rejected"}
STATEMENT = (
    "This request records the discipline checklist for the verified quantity still waiting. "
    "Approval accepts only that quantity. It does not certify billing, release a hold, or create an NCR."
)
NOTE = (
    "A released activity can be requested for inspection on an approved discipline form. "
    "The quantity is the verified quantity still waiting. A saved reviewer makes the outcome effective. "
    "Acceptance does not certify billing."
)
WATCH = {"Site Engineer", "Discipline Head", "QA/QC", "Project Manager"}


class _Acceptance:
    def __init__(self, quantity, percent):
        self.accepted_quantity = quantity
        self.accepted_percent = percent


def _q(value):
    return Decimal(value).quantize(Decimal("0.001"))


def _bump(db, row, version, values):
    changed = db.execute(
        update(ConstructionRequest)
        .where(ConstructionRequest.id == row.id, ConstructionRequest.version == version)
        .values(version=version + 1, modified_at=now(), **values)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This inspection request changed. Reload it and try again")
    db.refresh(row)


def _latest_review(db, project, row):
    from app.domains.coordination.models import ReviewInstance

    return (
        db.query(ReviewInstance)
        .filter_by(project_id=project.id, record_type=CONSTRUCTION, record_id=row.id)
        .order_by(ReviewInstance.id.desc())
        .first()
    )


def _results(db, row):
    return (
        db.query(ConstructionResult)
        .filter_by(request_id=row.id)
        .order_by(ConstructionResult.position)
        .all()
    )


def _approved_requests(db, activity):
    return (
        db.query(ConstructionRequest)
        .filter_by(activity_id=activity.id, status="Approved")
        .order_by(ConstructionRequest.id)
        .all()
    )


def _offer_accepted(db, activity):
    line = (
        db.query(QualityOfferLine)
        .join(QualityOffer, QualityOffer.id == QualityOfferLine.offer_id)
        .filter(QualityOfferLine.activity_id == activity.id, QualityOffer.status == "Approved")
        .order_by(QualityOfferLine.id.desc())
        .first()
    )
    if not line:
        return Decimal("0"), None
    quantity = _q(line.accepted_quantity) if line.accepted_quantity is not None else Decimal("0")
    return quantity, line.accepted_percent


def inspection_accepted(db, activity):
    total = Decimal("0")
    for row in _approved_requests(db, activity):
        if row.outcome in {"Accepted", "Partially Accepted"} and row.accepted_quantity is not None:
            total += _q(row.accepted_quantity)
    return total


def accepted_so_far(db, activity):
    offer_quantity, _percent = _offer_accepted(db, activity)
    return offer_quantity + inspection_accepted(db, activity)


def percent_accepted(db, activity):
    _quantity, offer_percent = _offer_accepted(db, activity)
    if offer_percent is not None and offer_percent >= Decimal("100"):
        return True
    return any(row.accepted_percent is not None and row.accepted_percent >= Decimal("100") for row in _approved_requests(db, activity))


def construction_acceptance(db, activity):
    quantity = Decimal("0")
    percent = None
    for row in _approved_requests(db, activity):
        if row.outcome not in {"Accepted", "Partially Accepted"}:
            continue
        if row.accepted_quantity is not None:
            quantity += _q(row.accepted_quantity)
        if row.accepted_percent is not None:
            percent = row.accepted_percent
    if quantity <= 0 and percent is None:
        return None
    return _Acceptance(quantity if quantity > 0 else None, percent)


def _activity(db, project, activity_id):
    activity = db.get(ConstructionActivity, activity_id)
    package = db.get(WorkPackage, activity.package_id) if activity else None
    if not activity or not activity.active or not package or package.project_id != project.id:
        raise HTTPException(404, "Activity not found")
    return activity, package


def _problem(package):
    if package.release_state != "Released":
        return "Inspection applies to a released work package"
    if package.status == "On Hold":
        return "Resume the work package before inspection"
    if package.status not in {"In Progress", "Physically Complete", "Handed Over"}:
        return "Inspection applies to released work"
    return None


def _waiting(db, activity):
    from app.domains.construction.progress import activity_measures

    measured = activity_measures(db, activity)
    weighted = measured["method"] == "Weighted milestones"
    if weighted:
        if measured["verified_percent"] != "100.00":
            raise HTTPException(422, f"{activity.code} is not fully verified")
        if percent_accepted(db, activity):
            raise HTTPException(422, f"{activity.code} already has this verified quantity accepted")
        return None, Decimal("100.00"), measured
    verified = Decimal(measured["verified_quantity"] or "0")
    if verified <= 0:
        raise HTTPException(422, f"{activity.code} has no verified quantity to offer")
    remaining = verified - accepted_so_far(db, activity)
    if remaining <= 0:
        raise HTTPException(422, f"{activity.code} already has this verified quantity accepted")
    return remaining, None, measured


def _member(db, project, user_id, label):
    person = db.get(User, user_id)
    if not _project_member(db, project, person):
        raise HTTPException(422, f"Choose an active project member as the {label}")
    return person


def _template(db, project, package, template_id):
    form = db.get(QualityForm, template_id)
    if not form or form.project_id != project.id:
        raise HTTPException(404, "Discipline form not found")
    if form.status != "Approved":
        raise HTTPException(422, "Only an approved discipline form can be used")
    if form.discipline_id != package.discipline_id:
        raise HTTPException(422, "The discipline form is for another discipline")
    criteria = db.get(QualityDocument, form.criteria_document_id) if form.criteria_document_id else None
    if not criteria or criteria.status != "Approved" or criteria.project_id != project.id:
        raise HTTPException(422, "Only an approved quality document can be used")
    if not form.items:
        raise HTTPException(422, "The discipline form has no checklist items")
    return form, criteria


def _checkpoint(db, project, package, activity, checkpoint_id, open_hold=True):
    if not checkpoint_id:
        return None
    point = db.get(QualityCheckpoint, checkpoint_id)
    document = db.get(QualityDocument, point.document_id) if point else None
    if not point or not document or document.project_id != project.id:
        raise HTTPException(422, "Choose a checkpoint on an approved ITP")
    if document.kind != "ITP" or document.status != "Approved":
        raise HTTPException(422, "Choose a checkpoint on an approved ITP")
    if document.discipline_id and document.discipline_id != package.discipline_id:
        raise HTTPException(422, "The checkpoint is for another discipline")
    if point.point_type == "Hold" and open_hold:
        from .findings import hold_for_checkpoint

        if not hold_for_checkpoint(db, activity, point):
            raise HTTPException(422, "Raise a quality hold for this hold point before inspection")
    return point


def _blocking(db, activity, ignore_id=None):
    query = db.query(ConstructionRequest).filter(
        ConstructionRequest.activity_id == activity.id,
        ConstructionRequest.status.in_(tuple(OPEN)),
    )
    if ignore_id:
        query = query.filter(ConstructionRequest.id != ignore_id)
    return query.first() is not None


def _link_target(db, activity):
    row = (
        db.query(ConstructionRequest)
        .filter_by(activity_id=activity.id, status="Approved")
        .order_by(ConstructionRequest.id.desc())
        .first()
    )
    rejected = row and (
        row.outcome == "Rejected"
        or (row.rejected_quantity is not None and _q(row.rejected_quantity) > 0)
    )
    if not rejected:
        return None
    followed = (
        db.query(ConstructionRequest)
        .filter(
            ConstructionRequest.follows_id == row.id,
            ConstructionRequest.status != "Cancelled",
        )
        .first()
    )
    if followed:
        return None
    return row


def _apply_link(db, activity, follows_id):
    target = _link_target(db, activity)
    if target and follows_id != target.id:
        raise HTTPException(422, "Reinspection must link the rejected result")
    if follows_id and (not target or follows_id != target.id):
        raise HTTPException(422, "Link the rejected inspection on this activity")
    return target


def _copy_items(db, row, form):
    db.query(ConstructionResult).filter_by(request_id=row.id).delete()
    for position, item in enumerate(form.items, start=1):
        db.add(ConstructionResult(request_id=row.id, position=position, item=str(item), result="", measurement=""))
    db.flush()


def _replace_results(db, row, incoming):
    current = _results(db, row)
    expected = [line.item for line in current]
    received = [item.item.strip() for item in incoming]
    if received != expected:
        raise HTTPException(422, "Record a result for every checklist item")
    for line, item in zip(current, incoming):
        answer = item.result.strip()
        if answer not in RESULTS:
            raise HTTPException(422, "Each checklist item is Pass, Fail, or Not applicable")
        line.result = answer
        line.measurement = item.measurement.strip()
    db.flush()


def _quantities(outcome, offered, proposed, weighted):
    if outcome not in OUTCOMES:
        raise HTTPException(422, "Choose the inspection outcome")
    if weighted:
        if outcome == "Partially Accepted":
            raise HTTPException(422, "Partial acceptance applies to a measured quantity")
        if outcome == "Accepted":
            return None, Decimal("100.00"), None
        return None, None, None
    if outcome == "Accepted":
        return offered, None, Decimal("0")
    if outcome == "Rejected":
        return Decimal("0"), None, offered
    if proposed is None or proposed <= 0 or proposed >= offered:
        raise HTTPException(422, "Partial acceptance must be less than the quantity still waiting")
    return _q(proposed), None, offered - _q(proposed)


def _failed(db, row):
    return any(line.result == "Fail" for line in _results(db, row))


def _snapshot(db, row, form, criteria, point, offered, percent):
    return {
        "template_code": form.code,
        "template_revision": form.revision_label,
        "criteria_revision": criteria.revision_label,
        "criteria_number": criteria.number,
        "units": form.units,
        "checkpoint": point.name if point else "",
        "point_type": point.point_type if point else "",
        "offered_quantity": qty(offered) if offered is not None else None,
        "offered_percent": format(percent, "f") if percent is not None else None,
        "items": [
            {"item": line.item, "result": line.result, "measurement": line.measurement}
            for line in _results(db, row)
        ],
        "statement": STATEMENT,
    }


def _policy_for(db, project, package):
    policy = _policy(db, project, CONSTRUCTION, package.company_id, package.discipline_id)
    if not policy:
        raise HTTPException(422, "Mandatory reviewer configuration is missing")
    _authority(db, project, policy)
    return policy


def _watchers(db, project):
    from app.domains.identity_projects.models import Role

    people = []
    seen = set()
    for member in db.query(Membership).filter_by(project_id=project.id, active=True):
        if member.user_id in seen:
            continue
        person = db.get(User, member.user_id)
        role = db.get(Role, member.role_id)
        if person and person.active and role and role.name in WATCH:
            seen.add(person.id)
            people.append(person)
    return people


def _view_results(db, row):
    return [
        {
            "item": line.item,
            "result": line.result,
            "measurement": line.measurement,
        }
        for line in _results(db, row)
    ]


def request_view(db, user, project, row):
    activity = db.get(ConstructionActivity, row.activity_id)
    package = db.get(WorkPackage, row.package_id)
    form = db.get(QualityForm, row.template_id)
    point = db.get(QualityCheckpoint, row.checkpoint_id) if row.checkpoint_id else None
    inspector = db.get(User, row.inspector_id)
    instance = _latest_review(db, project, row)
    return {
        "id": row.id,
        "number": row.number,
        "package_id": row.package_id,
        "package_code": package.code if package else "",
        "package_status": package.status if package else "",
        "activity_id": row.activity_id,
        "activity_code": activity.code if activity else "",
        "template_id": row.template_id,
        "template_label": f"{form.code} rev {form.revision_label}" if form else "",
        "checkpoint_id": row.checkpoint_id,
        "checkpoint_name": point.name if point else "",
        "point_type": point.point_type if point else "",
        "follows_id": row.follows_id,
        "status": row.status,
        "outcome": row.outcome,
        "location": row.location,
        "requested_on": row.requested_on.isoformat(),
        "inspector_id": row.inspector_id,
        "inspector_name": inspector.name if inspector else "",
        "attendees": row.attendees,
        "findings": row.findings,
        "offered_quantity": qty(row.offered_quantity) if row.offered_quantity is not None else None,
        "accepted_quantity": qty(row.accepted_quantity) if row.accepted_quantity is not None else None,
        "rejected_quantity": qty(row.rejected_quantity) if row.rejected_quantity is not None else None,
        "statement": row.statement,
        "results": _view_results(db, row),
        "payload": row.payload or {},
        "version": row.version,
        "review": review_payload(db, user, instance) if instance else None,
    }


def register(db, user, project):
    from app.domains.construction.progress import activity_measures

    packages = (
        db.query(WorkPackage)
        .filter_by(project_id=project.id, release_state="Released")
        .filter(WorkPackage.status.in_(["In Progress", "Physically Complete", "Handed Over", "On Hold"]))
        .order_by(WorkPackage.code)
        .all()
    )
    activities = []
    for package in packages:
        for activity in (
            db.query(ConstructionActivity).filter_by(package_id=package.id, active=True).order_by(ConstructionActivity.code)
        ):
            measured = activity_measures(db, activity)
            waiting = None
            if measured["method"] != "Weighted milestones" and measured["verified_quantity"]:
                remaining = Decimal(measured["verified_quantity"]) - accepted_so_far(db, activity)
                waiting = qty(remaining) if remaining > 0 else "0.000"
            activities.append(
                {
                    "id": activity.id,
                    "code": activity.code,
                    "package_code": package.code,
                    "package_status": package.status,
                    "discipline_id": package.discipline_id,
                    "method": measured["method"],
                    "unit": measured["unit"],
                    "verified_quantity": measured["verified_quantity"],
                    "verified_percent": measured["verified_percent"],
                    "waiting_quantity": waiting,
                }
            )
    forms = (
        db.query(QualityForm)
        .filter_by(project_id=project.id, status="Approved")
        .order_by(QualityForm.code)
        .all()
    )
    points = []
    documents = (
        db.query(QualityDocument)
        .filter_by(project_id=project.id, kind="ITP", status="Approved")
        .all()
    )
    for document in documents:
        for point in db.query(QualityCheckpoint).filter_by(document_id=document.id).order_by(QualityCheckpoint.sequence):
            points.append(
                {
                    "id": point.id,
                    "name": point.name,
                    "point_type": point.point_type,
                    "discipline_id": document.discipline_id,
                    "document_label": f"{document.number} rev {document.revision_label}",
                }
            )
    people = []
    seen = set()
    for member in db.query(Membership).filter_by(project_id=project.id, active=True):
        if member.user_id in seen:
            continue
        person = db.get(User, member.user_id)
        if person and person.active:
            seen.add(person.id)
            people.append({"id": person.id, "name": person.name})
    requests = (
        db.query(ConstructionRequest)
        .filter_by(project_id=project.id)
        .filter(ConstructionRequest.status != "Cancelled")
        .order_by(ConstructionRequest.id.desc())
        .all()
    )
    return {
        "note": NOTE,
        "activities": activities,
        "forms": [
            {
                "id": form.id,
                "label": f"{form.code} rev {form.revision_label}",
                "discipline_id": form.discipline_id,
                "items": form.items or [],
                "units": form.units,
            }
            for form in forms
        ],
        "checkpoints": points,
        "members": people,
        "requests": [request_view(db, user, project, row) for row in requests],
    }


def add_request(db, user, project, data):
    activity, package = _activity(db, project, data.activity_id)
    problem = _problem(package)
    if problem:
        raise HTTPException(409, problem)
    if _blocking(db, activity):
        raise HTTPException(409, "This activity already has an open inspection request")
    _waiting(db, activity)
    form, _criteria = _template(db, project, package, data.template_id)
    point = _checkpoint(db, project, package, activity, data.checkpoint_id)
    if point and point.point_type == "Witness" and not data.attendees.strip():
        raise HTTPException(422, "Witness attendance is not acceptance. Record who attended")
    _apply_link(db, activity, data.follows_id)
    requester = _member(db, project, data.requester_id, "requester")
    inspector = _member(db, project, data.inspector_id, "inspector")
    key = data.number.strip().casefold()
    if db.query(ConstructionRequest).filter_by(project_id=project.id, number_key=key).first():
        raise HTTPException(409, "Inspection number already exists on this project")
    row = ConstructionRequest(
        organization_id=project.organization_id,
        project_id=project.id,
        package_id=package.id,
        activity_id=activity.id,
        template_id=form.id,
        checkpoint_id=point.id if point else None,
        follows_id=data.follows_id,
        company_id=activity.company_id,
        number=data.number.strip(),
        number_key=key,
        location=data.location.strip(),
        requested_on=data.requested_on,
        requester_id=requester.id,
        inspector_id=inspector.id,
        attendees=data.attendees.strip(),
        findings=data.findings.strip(),
        statement=STATEMENT,
        payload={},
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(row)
    db.flush()
    _copy_items(db, row, form)
    return row


def update_request(db, user, project, row, data):
    if row.status not in EDITABLE:
        raise HTTPException(409, "An approved inspection request is kept. Record a later inspection")
    activity, package = _activity(db, project, row.activity_id)
    problem = _problem(package)
    if problem:
        raise HTTPException(422, problem)
    inspector = _member(db, project, data.inspector_id, "inspector")
    point = db.get(QualityCheckpoint, row.checkpoint_id) if row.checkpoint_id else None
    if point and point.point_type == "Witness" and not data.attendees.strip():
        raise HTTPException(422, "Witness attendance is not acceptance. Record who attended")
    if data.outcome not in OUTCOMES | {"Pending"}:
        raise HTTPException(422, "Choose the inspection outcome")
    _replace_results(db, row, data.results)
    if data.outcome == "Accepted" and _failed(db, row):
        raise HTTPException(422, "A failed checklist item cannot be accepted")
    _bump(
        db,
        row,
        data.version,
        {
            "outcome": data.outcome,
            "location": data.location.strip(),
            "requested_on": data.requested_on,
            "inspector_id": inspector.id,
            "attendees": data.attendees.strip(),
            "findings": data.findings.strip(),
            "accepted_quantity": data.accepted_quantity if data.outcome == "Partially Accepted" else None,
            "modified_by": user.id,
        },
    )
    return row


def _prepare(db, project, row, open_hold=True):
    activity, package = _activity(db, project, row.activity_id)
    problem = _problem(package)
    if problem:
        raise HTTPException(422, problem)
    if _blocking(db, activity, ignore_id=row.id):
        raise HTTPException(409, "This activity already has an open inspection request")
    offered, percent, _measured = _waiting(db, activity)
    form, criteria = _template(db, project, package, row.template_id)
    point = _checkpoint(db, project, package, activity, row.checkpoint_id, open_hold)
    if point and point.point_type == "Witness" and not row.attendees.strip():
        raise HTTPException(422, "Witness attendance is not acceptance. Record who attended")
    lines = _results(db, row)
    if not lines or any(line.result not in RESULTS for line in lines):
        raise HTTPException(422, "Record a result for every checklist item")
    if row.outcome == "Accepted" and _failed(db, row):
        raise HTTPException(422, "A failed checklist item cannot be accepted")
    weighted = percent is not None
    accepted, accepted_percent, rejected = _quantities(row.outcome, offered, row.accepted_quantity, weighted)
    kept = package.status
    payload = _snapshot(db, row, form, criteria, point, offered, percent)
    from .competence import coverage_note

    payload["qualification_note"] = coverage_note(db, project, row.inspector_id, row.requested_on)
    if package.status != kept:
        package.status = kept
    return offered, percent, accepted, accepted_percent, rejected, payload, package


def submit_request(db, user, project, row, version):
    if row.status == "Returned for Correction":
        raise HTTPException(409, "A returned request is resubmitted, not submitted again")
    if row.status != "Draft":
        raise HTTPException(409, "Only a draft request can be submitted")
    from .competence import assert_inspector

    assert_inspector(db, project, row.inspector_id, row.requested_on)
    offered, percent, accepted, accepted_percent, rejected, payload, package = _prepare(db, project, row)
    policy = _policy_for(db, project, package)
    _bump(
        db,
        row,
        version,
        {
            "status": "Pending Review",
            "offered_quantity": offered,
            "offered_percent": percent,
            "accepted_quantity": accepted,
            "accepted_percent": accepted_percent,
            "rejected_quantity": rejected,
            "payload": payload,
            "modified_by": user.id,
        },
    )
    return submit_record(db, user, project, CONSTRUCTION, row.id, row.version, policy)


def apply_resubmit(db, user, instance, review_version):
    from app.domains.coordination.service import _close_tasks, _lock, _open_stage, current_stage
    from app.domains.identity_projects.models import Project

    if instance.record_type != CONSTRUCTION:
        return
    if instance.state != "Returned":
        raise HTTPException(409, "Only a returned review can be resubmitted")
    if user.id != instance.submitted_by and not user.organization_admin:
        raise HTTPException(403, "Only the submitter can resubmit")
    project = db.get(Project, instance.project_id)
    row = db.get(ConstructionRequest, instance.record_id)
    if not project or not row or row.project_id != project.id:
        raise HTTPException(404, "Inspection request not found")
    if not holds(db, user, project, "quality.edit") and not holds(db, user, project, "quality.plan"):
        raise HTTPException(403, "Insufficient project permission")
    if row.status != "Returned for Correction":
        raise HTTPException(409, "Only a returned request can be resubmitted")
    from .competence import assert_inspector

    assert_inspector(db, project, row.inspector_id, row.requested_on)
    _activity_row, package = _activity(db, project, row.activity_id)
    offered, percent, accepted, accepted_percent, rejected, payload, package = _prepare(db, project, row)
    policy = _policy_for(db, project, package)
    _lock(db, instance, review_version)
    _close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    _bump(
        db,
        row,
        row.version,
        {
            "status": "Pending Review",
            "offered_quantity": offered,
            "offered_percent": percent,
            "accepted_quantity": accepted,
            "accepted_percent": accepted_percent,
            "rejected_quantity": rejected,
            "payload": payload,
            "modified_by": user.id,
        },
    )
    instance.record_version = row.version
    instance.policy_id = policy.id
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def cancel_request(db, user, row, data):
    if row.status == "Pending Review":
        raise HTTPException(409, "This request is in review")
    if row.status not in EDITABLE:
        raise HTTPException(409, "Only a draft request can be cancelled here")
    _bump(
        db,
        row,
        data.version,
        {"status": "Cancelled", "cancellation_reason": data.reason.strip(), "modified_by": user.id},
    )


def on_review_event(db, user, instance, project, action, stage=None):
    if instance.record_type != CONSTRUCTION:
        return
    row = db.get(ConstructionRequest, instance.record_id)
    package = db.get(WorkPackage, row.package_id) if row else None
    if not row or not package or package.project_id != project.id:
        return
    kept = package.status
    if action == "advance":
        return
    if action == "return":
        row.status = "Returned for Correction"
    elif action == "reject":
        row.status = "Rejected"
    elif instance.state == "Approved":
        row.status = "Approved"
        title = "Construction quantity accepted" if row.outcome in {"Accepted", "Partially Accepted"} else "Construction inspection decided"
        _tell(
            db,
            project,
            _watchers(db, project),
            title,
            f"{row.number} has a quality decision. This does not certify the work for billing.",
            f"quality.construction.{row.id}",
        )
    else:
        return
    if package.status != kept:
        package.status = kept
    row.version += 1
    row.modified_by = user.id
    row.modified_at = now()


def review_guard(db, user, instance, stage, action):
    if instance.record_type != CONSTRUCTION or action != "approve":
        return
    from app.domains.identity_projects.models import Project

    project = db.get(Project, instance.project_id)
    row = db.get(ConstructionRequest, instance.record_id)
    if not project or not row or row.project_id != project.id or row.status != "Pending Review":
        raise HTTPException(409, "This inspection request is not awaiting review")
    form = db.get(QualityForm, row.template_id)
    criteria = db.get(QualityDocument, form.criteria_document_id) if form and form.criteria_document_id else None
    frozen = (row.payload or {}).get("criteria_revision")
    frozen_form = (row.payload or {}).get("template_revision")
    if not form or form.revision_label != frozen_form:
        raise HTTPException(409, "The discipline form revision changed. Return the inspection")
    if not criteria or criteria.revision_label != frozen:
        raise HTTPException(409, "The acceptance criteria revision changed. Return the inspection")
    try:
        _prepare(db, project, row, open_hold=False)
    except HTTPException as exc:
        raise HTTPException(409, "This quantity is no longer waiting for inspection") from exc
    from .findings import acceptance_blocked

    if acceptance_blocked(db, row):
        raise HTTPException(409, "Release the quality hold before this hold point can be accepted")


if review_guard not in REVIEW_GUARDS:
    REVIEW_GUARDS.append(review_guard)
