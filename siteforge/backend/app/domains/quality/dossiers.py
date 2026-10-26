"""Quality dossier index and punch items.

The index freezes the exact quality versions on a work package. Approving it
does not hand the package over and does not certify billing. Commissioning
and Financials are not open.
"""

import json

from fastapi import HTTPException
from sqlalchemy import update

from app.domains.construction.models import ConstructionActivity, ConstructionBlocker, WorkPackage
from app.domains.coordination.service import REVIEW_GUARDS, review_payload
from app.domains.engineering_documents.workflow import submit_record
from app.domains.identity_projects.models import Membership, User
from app.domains.identity_projects.security import holds
from app.domains.supply_chain.service import _authority, _policy, _project_member

from .findings import HOLD_OPEN, OPEN_NCR
from .models import (
    Calibration,
    Concession,
    ConstructionRequest,
    MaterialInspection,
    Nonconformance,
    Qualification,
    QualityDocument,
    QualityDossier,
    QualityForm,
    QualityHold,
    QualityOffer,
    QualityOfferLine,
    QualityPunch,
    now,
)

DOSSIER = "quality.dossier"
PUNCH_CLOSE = "quality.punch.close"
OPEN_DOSSIER = {"Draft", "Pending Review", "Returned for Correction"}
PUNCH_REMAINING = {"Open", "Pending Closure", "Closure Returned"}
PROCEDURES = {"Project Quality Plan", "ITP", "Inspection Procedure", "Test Procedure", "Acceptance Criteria"}
STATEMENT = (
    "This index keeps the exact quality versions for this work package. "
    "A complete index does not authorize handover. Commissioning is not open. "
    "Financials is not open. This does not certify billing."
)
PUNCH_STATEMENT = (
    "This punch item is a quality record. Closing it does not resolve a construction blocker, "
    "accept the work, or certify billing."
)
NOTE = (
    "A dossier lists the approved quality versions for one work package, including remaining punch items. "
    "Commissioning owns handover and Financials owns billing. Neither module is the source of this index."
)


def _bump(db, model, row, version, values):
    changed = db.execute(
        update(model).where(model.id == row.id, model.version == version).values(version=version + 1, modified_at=now(), **values)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This record changed. Reload it and try again")
    db.refresh(row)


def _package(db, project, package_id):
    package = db.get(WorkPackage, package_id)
    if not package or package.project_id != project.id:
        raise HTTPException(422, "Choose a work package on this project")
    return package


def _member(db, project, user_id):
    person = db.get(User, user_id)
    if not _project_member(db, project, person):
        raise HTTPException(422, "Choose an active project member")
    return person


def _people(db, project):
    people = []
    seen = set()
    for member in db.query(Membership).filter_by(project_id=project.id, active=True):
        if member.user_id in seen:
            continue
        person = db.get(User, member.user_id)
        if person and person.active:
            seen.add(person.id)
            people.append({"id": person.id, "name": person.name})
    return people


def _policy_for(db, project, record_type):
    policy = _policy(db, project, record_type, None, None)
    if not policy:
        raise HTTPException(422, "Mandatory reviewer configuration is missing")
    _authority(db, project, policy)
    return policy


def _latest(db, project, record_type, record_id):
    from app.domains.coordination.models import ReviewInstance

    return (
        db.query(ReviewInstance)
        .filter_by(project_id=project.id, record_type=record_type, record_id=record_id)
        .order_by(ReviewInstance.id.desc())
        .first()
    )


def _ref(kind, row, **extra):
    item = {"kind": kind, "id": row.id, "number": row.number, "version": row.version, "status": row.status}
    item.update(extra)
    return item


def _activities(db, package):
    return db.query(ConstructionActivity).filter_by(package_id=package.id).all()


def build_index(db, project, package):
    activities = _activities(db, package)
    activity_ids = {row.id for row in activities}
    procedures = []
    for row in db.query(QualityDocument).filter_by(project_id=project.id, status="Approved"):
        if row.kind not in PROCEDURES:
            continue
        if row.discipline_id not in {None, package.discipline_id}:
            continue
        procedures.append(_ref(row.kind, row, revision=row.revision_label))
    offers = db.query(QualityOffer).filter_by(project_id=project.id, package_id=package.id, status="Approved").all()
    requests = (
        db.query(ConstructionRequest).filter_by(project_id=project.id, package_id=package.id, status="Approved").all()
    )
    inspection_reports = [_ref("Inspection offer", row) for row in offers]
    test_reports = []
    acceptance = []
    for row in offers:
        lines = db.query(QualityOfferLine).filter_by(offer_id=row.id).all()
        if any(line.accepted_quantity is not None or line.accepted_percent is not None for line in lines):
            acceptance.append(_ref("Inspection offer", row))
    for row in requests:
        form = db.get(QualityForm, row.template_id)
        criteria = db.get(QualityDocument, form.criteria_document_id) if form and form.criteria_document_id else None
        revision = (row.payload or {}).get("template_revision", "")
        item = _ref("Construction inspection", row, revision=revision, outcome=row.outcome)
        if criteria and criteria.kind == "Test Procedure":
            test_reports.append(item)
        else:
            inspection_reports.append(item)
        if row.outcome in {"Accepted", "Partially Accepted"}:
            acceptance.append(item)
    certificates = [
        _ref("Material inspection", row, revision=row.certificate_reference)
        for row in db.query(MaterialInspection).filter_by(project_id=project.id, status="Approved")
        if row.certificate_reference.strip()
    ]
    qualifications = [
        _ref("Qualification", row, revision=row.valid_to.isoformat())
        for row in db.query(Qualification).filter_by(project_id=project.id, status="Approved")
    ]
    calibrations = [
        _ref("Calibration", row, revision=row.due_on.isoformat())
        for row in db.query(Calibration).filter_by(project_id=project.id, status="Approved")
    ]
    package_ncrs = []
    request_ids = {row.id for row in requests} | {
        row.id
        for row in db.query(ConstructionRequest).filter_by(project_id=project.id, package_id=package.id)
    }
    offer_ids = {row.id for row in offers} | {
        row.id for row in db.query(QualityOffer).filter_by(project_id=project.id, package_id=package.id)
    }
    for row in db.query(Nonconformance).filter_by(project_id=project.id):
        linked = (
            (row.activity_id and row.activity_id in activity_ids)
            or (row.request_id and row.request_id in request_ids)
            or (row.offer_id and row.offer_id in offer_ids)
        )
        if linked:
            package_ncrs.append(row)
    closed = [_ref("NCR", row) for row in package_ncrs if row.status == "Closed"]
    ncr_ids = {row.id for row in package_ncrs}
    concessions = [
        _ref("Concession", row)
        for row in db.query(Concession).filter_by(project_id=project.id, status="Approved")
        if row.ncr_id in ncr_ids
    ]
    punches = [
        _ref("Punch", row, issue_type=row.issue_type, blocking=row.blocking)
        for row in db.query(QualityPunch).filter(
            QualityPunch.project_id == project.id,
            QualityPunch.package_id == package.id,
            QualityPunch.status.in_(tuple(PUNCH_REMAINING)),
        )
    ]
    holds = []
    for row in db.query(QualityHold).filter(
        QualityHold.project_id == project.id,
        QualityHold.status.in_(tuple(HOLD_OPEN)),
        QualityHold.blocks_handover.is_(True),
        QualityHold.package_id == package.id,
    ):
        holds.append(_ref("Quality hold", row))
    blockers = [
        {"kind": "Construction blocker", "id": row.id, "number": row.kind, "version": row.version, "status": row.status}
        for row in db.query(ConstructionBlocker).filter_by(project_id=project.id, package_id=package.id, status="Open")
    ]
    gaps = []
    if not any(row["kind"] == "ITP" for row in procedures):
        gaps.append("No approved ITP applies to this discipline")
    if any(row["blocking"] for row in punches):
        gaps.append("A blocking punch is still open")
    if holds:
        gaps.append("A quality hold blocks handover")
    if any(row.status in OPEN_NCR for row in package_ncrs):
        gaps.append("An NCR on this package is still open")
    index = {
        "procedures": procedures,
        "inspection_reports": inspection_reports,
        "test_reports": test_reports,
        "material_certificates": certificates,
        "qualifications": qualifications,
        "calibrations": calibrations,
        "closed_ncrs": closed,
        "concessions": concessions,
        "punches": punches,
        "acceptance_records": acceptance,
        "open_holds": holds,
        "construction_blockers": blockers,
        "gaps": gaps,
    }
    for key, rows in index.items():
        if key != "gaps":
            rows.sort(key=lambda item: (item.get("kind", ""), item.get("id", 0), item.get("number", "")))
    return index


def _same(left, right):
    return json.dumps(left, sort_keys=True, default=str) == json.dumps(right, sort_keys=True, default=str)


def dossier_view(db, user, project, row):
    package = db.get(WorkPackage, row.package_id)
    instance = _latest(db, project, DOSSIER, row.id)
    return {
        "id": row.id,
        "number": row.number,
        "package_id": row.package_id,
        "package_code": package.code if package else "",
        "package_status": package.status if package else "",
        "status": row.status,
        "statement": row.statement,
        "payload": row.payload or {},
        "version": row.version,
        "review": review_payload(db, user, instance) if instance else None,
    }


def punch_view(db, user, project, row):
    package = db.get(WorkPackage, row.package_id)
    owner = db.get(User, row.owner_id)
    instance = _latest(db, project, PUNCH_CLOSE, row.id)
    blocker = db.get(ConstructionBlocker, row.blocker_id) if row.blocker_id else None
    return {
        "id": row.id,
        "number": row.number,
        "package_id": row.package_id,
        "package_code": package.code if package else "",
        "issue_type": row.issue_type,
        "status": row.status,
        "description": row.description,
        "owner_name": owner.name if owner else "",
        "severity": row.severity,
        "blocking": row.blocking,
        "due_on": row.due_on.isoformat(),
        "evidence": row.evidence,
        "verification": row.verification,
        "blocker_label": blocker.kind if blocker else "",
        "statement": row.statement,
        "version": row.version,
        "review": review_payload(db, user, instance) if instance else None,
    }


def register(db, user, project):
    packages = [
        {"id": row.id, "code": row.code, "status": row.status}
        for row in db.query(WorkPackage).filter_by(project_id=project.id).order_by(WorkPackage.id)
    ]
    blockers = [
        {"id": row.id, "package_id": row.package_id, "kind": row.kind, "description": row.description}
        for row in db.query(ConstructionBlocker).filter_by(project_id=project.id, status="Open")
    ]
    dossiers = [
        dossier_view(db, user, project, row)
        for row in db.query(QualityDossier)
        .filter_by(project_id=project.id)
        .filter(QualityDossier.status != "Cancelled")
        .order_by(QualityDossier.id.desc())
    ]
    punches = [
        punch_view(db, user, project, row)
        for row in db.query(QualityPunch)
        .filter_by(project_id=project.id)
        .filter(QualityPunch.status != "Cancelled")
        .order_by(QualityPunch.id.desc())
    ]
    return {
        "note": NOTE,
        "packages": packages,
        "members": _people(db, project),
        "blockers": blockers,
        "dossiers": dossiers,
        "punches": punches,
    }


def add_dossier(db, user, project, data):
    package = _package(db, project, data.package_id)
    key = data.number.strip().casefold()
    if db.query(QualityDossier).filter_by(project_id=project.id, number_key=key).first():
        raise HTTPException(409, "Dossier number already exists on this project")
    if (
        db.query(QualityDossier)
        .filter(QualityDossier.package_id == package.id, QualityDossier.status.in_(tuple(OPEN_DOSSIER)))
        .first()
    ):
        raise HTTPException(409, "This work package already has an open quality dossier")
    row = QualityDossier(
        organization_id=project.organization_id,
        project_id=project.id,
        package_id=package.id,
        number=data.number.strip(),
        number_key=key,
        statement=STATEMENT,
        payload={},
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def submit_dossier(db, user, project, row, version):
    if row.status == "Returned for Correction":
        raise HTTPException(409, "A returned dossier is resubmitted, not submitted again")
    if row.status != "Draft":
        raise HTTPException(409, "Only a draft dossier can be submitted")
    package = _package(db, project, row.package_id)
    index = build_index(db, project, package)
    policy = _policy_for(db, project, DOSSIER)
    _bump(
        db,
        QualityDossier,
        row,
        version,
        {"status": "Pending Review", "payload": {"index": index}, "modified_by": user.id},
    )
    return submit_record(db, user, project, DOSSIER, row.id, row.version, policy)


def add_punch(db, user, project, data):
    if data.issue_type not in {"Observation", "Punch"}:
        raise HTTPException(422, "Choose an observation or a punch item")
    if data.severity not in {"Minor", "Major", "Critical"}:
        raise HTTPException(422, "Choose the severity")
    package = _package(db, project, data.package_id)
    owner = _member(db, project, data.owner_id)
    blocker_id = None
    if data.blocker_id:
        blocker = db.get(ConstructionBlocker, data.blocker_id)
        if not blocker or blocker.project_id != project.id or blocker.package_id != package.id or blocker.status != "Open":
            raise HTTPException(422, "Link an open construction blocker on this package")
        clash = (
            db.query(QualityPunch)
            .filter(
                QualityPunch.blocker_id == blocker.id,
                QualityPunch.status.in_(tuple(PUNCH_REMAINING | {"Pending Closure"})),
            )
            .first()
        )
        if clash:
            raise HTTPException(409, "This construction blocker is already classified")
        blocker_id = blocker.id
    if data.activity_id:
        activity = db.get(ConstructionActivity, data.activity_id)
        if not activity or activity.package_id != package.id:
            raise HTTPException(422, "Choose an activity on this work package")
    key = data.number.strip().casefold()
    if db.query(QualityPunch).filter_by(project_id=project.id, number_key=key).first():
        raise HTTPException(409, "Punch number already exists on this project")
    row = QualityPunch(
        organization_id=project.organization_id,
        project_id=project.id,
        package_id=package.id,
        blocker_id=blocker_id,
        activity_id=data.activity_id,
        number=data.number.strip(),
        number_key=key,
        issue_type=data.issue_type,
        description=data.description.strip(),
        company_id=data.company_id,
        owner_id=owner.id,
        severity=data.severity,
        blocking=data.blocking,
        due_on=data.due_on,
        statement=PUNCH_STATEMENT,
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def submit_punch_closure(db, user, project, row, data):
    if row.status == "Closure Returned":
        raise HTTPException(409, "A returned punch closure is resubmitted, not submitted again")
    if row.status != "Open":
        raise HTTPException(409, "Only an open punch item can be submitted for closure")
    policy = _policy_for(db, project, PUNCH_CLOSE)
    _bump(
        db,
        QualityPunch,
        row,
        data.version,
        {
            "status": "Pending Closure",
            "evidence": data.evidence.strip(),
            "verification": data.verification.strip(),
            "modified_by": user.id,
        },
    )
    return submit_record(db, user, project, PUNCH_CLOSE, row.id, row.version, policy)


def cancel_punch(db, user, row, data):
    if row.status != "Open":
        raise HTTPException(409, "Only an open punch item can be cancelled")
    _bump(db, QualityPunch, row, data.version, {"status": "Cancelled", "modified_by": user.id})


def eligibility(db, project, package):
    from app.domains.construction.progress import activity_measures

    index = build_index(db, project, package)
    approved = (
        db.query(QualityDossier)
        .filter_by(project_id=project.id, package_id=package.id, status="Approved")
        .order_by(QualityDossier.id.desc())
        .first()
    )
    activities = []
    for activity in _activities(db, package):
        measured = activity_measures(db, activity)
        activities.append(
            {
                "code": measured["activity_code"],
                "unit": measured["unit"],
                "accepted_quantity": measured["accepted_quantity"],
                "certified_quantity": measured["certified_quantity"],
            }
        )
    return {
        "package_id": package.id,
        "package_code": package.code,
        "package_status": package.status,
        "gaps": index["gaps"],
        "blocking_punches": [row for row in index["punches"] if row["blocking"]],
        "activities": activities,
        "approved_dossier": {"id": approved.id, "number": approved.number, "version": approved.version} if approved else None,
        "handover_note": "A complete index does not authorize handover. Commissioning is not open.",
        "billing_note": "Financials is not open. This list is acceptance evidence. It does not certify billing.",
    }


def apply_resubmit(db, user, instance, review_version):
    from app.domains.coordination.service import _close_tasks, _lock, _open_stage, current_stage
    from app.domains.identity_projects.models import Project

    if instance.record_type not in {DOSSIER, PUNCH_CLOSE}:
        return
    if instance.state != "Returned":
        raise HTTPException(409, "Only a returned review can be resubmitted")
    if user.id != instance.submitted_by and not user.organization_admin:
        raise HTTPException(403, "Only the submitter can resubmit")
    project = db.get(Project, instance.project_id)
    model = QualityDossier if instance.record_type == DOSSIER else QualityPunch
    row = db.get(model, instance.record_id)
    if not project or not row or row.project_id != project.id:
        raise HTTPException(404, "Record not found")
    if instance.record_type == DOSSIER:
        if not holds(db, user, project, "quality.plan"):
            raise HTTPException(403, "Insufficient project permission")
        if row.status != "Returned for Correction":
            raise HTTPException(409, "Only a returned dossier can be resubmitted")
        package = _package(db, project, row.package_id)
        values = {"status": "Pending Review", "payload": {"index": build_index(db, project, package)}, "modified_by": user.id}
    else:
        if not holds(db, user, project, "quality.edit") and not holds(db, user, project, "quality.plan"):
            raise HTTPException(403, "Insufficient project permission")
        if row.status != "Closure Returned":
            raise HTTPException(409, "Only a returned punch closure can be resubmitted")
        values = {"status": "Pending Closure", "modified_by": user.id}
    policy = _policy_for(db, project, instance.record_type)
    _lock(db, instance, review_version)
    _close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    _bump(db, model, row, row.version, values)
    instance.record_version = row.version
    instance.policy_id = policy.id
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def on_review_event(db, user, instance, project, action, stage=None):
    if instance.record_type not in {DOSSIER, PUNCH_CLOSE}:
        return
    model = QualityDossier if instance.record_type == DOSSIER else QualityPunch
    row = db.get(model, instance.record_id)
    if not row or row.project_id != project.id:
        return
    if instance.record_type == PUNCH_CLOSE:
        if action == "return":
            row.status = "Closure Returned"
        elif action == "reject":
            row.status = "Open"
        elif instance.state == "Approved":
            row.status = "Closed"
        else:
            return
    else:
        if action == "return":
            row.status = "Returned for Correction"
        elif action == "reject":
            row.status = "Rejected"
        elif instance.state == "Approved":
            row.status = "Approved"
        else:
            return
    row.version += 1
    row.modified_by = user.id
    row.modified_at = now()


def review_guard(db, user, instance, stage, action):
    if action != "approve" or instance.record_type != DOSSIER:
        return
    from app.domains.identity_projects.models import Project

    project = db.get(Project, instance.project_id)
    row = db.get(QualityDossier, instance.record_id)
    if not project or not row or row.project_id != project.id or row.status != "Pending Review":
        raise HTTPException(409, "This dossier is not awaiting review")
    package = _package(db, project, row.package_id)
    frozen = (row.payload or {}).get("index")
    if not _same(frozen, build_index(db, project, package)):
        raise HTTPException(409, "The quality index changed. Return the dossier")


if review_guard not in REVIEW_GUARDS:
    REVIEW_GUARDS.append(review_guard)
