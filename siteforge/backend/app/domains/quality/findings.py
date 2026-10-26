"""NCRs, concessions, and quality holds.

Use-as-is is a concession, not a QA disposition. Closure and hold release
become effective only when a saved reviewer approves them. Neither decision
accepts installation work or certifies billing.
"""

from datetime import date

from fastapi import HTTPException
from sqlalchemy import update

from app.domains.construction.models import ConstructionActivity, WorkPackage
from app.domains.construction.monitoring import _tell
from app.domains.coordination.service import REVIEW_GUARDS, review_payload
from app.domains.engineering_documents.workflow import submit_record
from app.domains.identity_projects.models import Company, Membership, ProjectDiscipline, User
from app.domains.identity_projects.security import holds
from app.domains.supply_chain.models import GoodsReceipt, GoodsReceiptLine
from app.domains.supply_chain.service import _authority, _policy, _project_member

from .models import (
    Concession,
    ConstructionRequest,
    MaterialInspection,
    Nonconformance,
    QualityCheckpoint,
    QualityDocument,
    QualityHold,
    QualityOffer,
    now,
)

NCR = "quality.ncr"
NCR_CLOSE = "quality.ncr.close"
CONCESSION = "quality.concession"
HOLD = "quality.hold"
OPEN_NCR = {
    "Draft",
    "Pending Review",
    "Returned for Correction",
    "Approved",
    "Pending Verification",
    "Verification Returned",
}
NCR_EDIT = {"Draft", "Returned for Correction"}
CONCESSION_EDIT = {"Draft", "Returned for Correction"}
HOLD_OPEN = {"Active", "Pending Release", "Release Returned"}
DISPOSITIONS = {"Rework", "Repair", "Reject/Return", "Use-As-Is"}
SEVERITIES = {"Minor", "Major", "Critical"}
SOURCES = {"activity", "request", "material", "offer"}
SCOPES = {"package", "activity", "receipt"}
NCR_NOTE = (
    "An NCR records the defect, the corrective action, and the disposition. "
    "Use-as-is needs an approved concession. Closure needs a saved reviewer. "
    "This does not accept the work or certify billing."
)
HOLD_NOTE = (
    "A quality hold blocks the actions named on it. Release needs evidence and a saved reviewer. "
    "It does not accept the work or certify billing."
)
NCR_STATEMENT = (
    "This NCR records the defect and the corrective action. "
    "Approval of the disposition does not accept the work or certify billing. "
    "Use-as-is is effective only through an approved concession."
)
CONCESSION_STATEMENT = (
    "This concession proposes use-as-is. Approval does not close the NCR, accept the work, or certify billing."
)
HOLD_STATEMENT = (
    "This hold blocks the named actions until a saved reviewer accepts the release evidence. "
    "Release does not accept the work or certify billing."
)
WATCH = {"Site Engineer", "Discipline Head", "QA/QC", "Project Manager"}


def _bump(db, model, row, version, values):
    changed = db.execute(
        update(model).where(model.id == row.id, model.version == version).values(version=version + 1, modified_at=now(), **values)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This record changed. Reload it and try again")
    db.refresh(row)


def _member(db, project, user_id, label):
    person = db.get(User, user_id)
    if not _project_member(db, project, person):
        raise HTTPException(422, f"Choose an active project member as the {label}")
    return person


def _company(db, project, company_id):
    company = db.get(Company, company_id)
    if not company or company.organization_id != project.organization_id:
        raise HTTPException(422, "Choose a company on this project")
    member = db.query(Membership).filter_by(project_id=project.id, company_id=company_id, active=True).first()
    if not member and project.client_company_id != company_id:
        raise HTTPException(422, "Choose a company on this project")
    return company


def _discipline(db, project, discipline_id):
    row = db.query(ProjectDiscipline).filter_by(project_id=project.id, discipline_id=discipline_id, active=True).first()
    if not row:
        raise HTTPException(422, "Discipline is not active on this project")
    return row


def _policy_for(db, project, record_type, company_id, discipline_id):
    policy = _policy(db, project, record_type, company_id, discipline_id)
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


def _source(db, project, kind, source_id):
    if kind not in SOURCES:
        raise HTTPException(422, "Choose the record this NCR refers to")
    activity_id = request_id = material_id = offer_id = None
    label = ""
    if kind == "activity":
        activity = db.get(ConstructionActivity, source_id)
        package = db.get(WorkPackage, activity.package_id) if activity else None
        if not activity or not package or package.project_id != project.id or not activity.active:
            raise HTTPException(422, "Choose an activity on this project")
        activity_id = activity.id
        label = activity.code
    elif kind == "request":
        row = db.get(ConstructionRequest, source_id)
        if not row or row.project_id != project.id:
            raise HTTPException(422, "Choose a construction inspection on this project")
        request_id = row.id
        label = row.number
    elif kind == "material":
        row = db.get(MaterialInspection, source_id)
        if not row or row.project_id != project.id:
            raise HTTPException(422, "Choose a material inspection on this project")
        material_id = row.id
        label = row.number
    else:
        row = db.get(QualityOffer, source_id)
        if not row or row.project_id != project.id:
            raise HTTPException(422, "Choose an inspection offer on this project")
        offer_id = row.id
        label = row.number
    return activity_id, request_id, material_id, offer_id, label


def _open_ncr(db, project, kind, activity_id, request_id, material_id, offer_id, ignore_id=None):
    query = db.query(Nonconformance).filter(
        Nonconformance.project_id == project.id,
        Nonconformance.source_kind == kind,
        Nonconformance.status.in_(tuple(OPEN_NCR)),
    )
    column = {
        "activity": Nonconformance.activity_id,
        "request": Nonconformance.request_id,
        "material": Nonconformance.material_id,
        "offer": Nonconformance.offer_id,
    }[kind]
    value = {"activity": activity_id, "request": request_id, "material": material_id, "offer": offer_id}[kind]
    query = query.filter(column == value)
    if ignore_id:
        query = query.filter(Nonconformance.id != ignore_id)
    return query.first()


def _concession_for(db, ncr):
    return (
        db.query(Concession)
        .filter_by(ncr_id=ncr.id, status="Approved")
        .order_by(Concession.id.desc())
        .first()
    )


def _require_concession(db, row):
    if row.disposition == "Use-As-Is" and not _concession_for(db, row):
        raise HTTPException(422, "Use-as-is needs an approved concession")


def _fields(data):
    if data.severity not in SEVERITIES:
        raise HTTPException(422, "Choose the severity")
    if data.disposition not in DISPOSITIONS:
        raise HTTPException(422, "Choose the disposition")
    if data.target_on < data.raised_on:
        raise HTTPException(422, "The target date cannot be earlier than the raised date")
    return {
        "location": data.location.strip(),
        "description": data.description.strip(),
        "requirement": data.requirement.strip(),
        "severity": data.severity,
        "affected_scope": data.affected_scope.strip(),
        "containment": data.containment.strip(),
        "raised_on": data.raised_on,
        "target_on": data.target_on,
        "root_cause": data.root_cause.strip(),
        "corrective_action": data.corrective_action.strip(),
        "disposition": data.disposition,
    }


def ncr_view(db, user, project, row):
    owner = db.get(User, row.owner_id)
    instance = _latest(db, project, NCR, row.id)
    closure = _latest(db, project, NCR_CLOSE, row.id)
    concessions = (
        db.query(Concession).filter_by(ncr_id=row.id).filter(Concession.status != "Cancelled").order_by(Concession.id.desc()).all()
    )
    return {
        "id": row.id,
        "number": row.number,
        "source_kind": row.source_kind,
        "source_label": _source_label(db, row),
        "activity_id": row.activity_id,
        "request_id": row.request_id,
        "material_id": row.material_id,
        "offer_id": row.offer_id,
        "discipline_id": row.discipline_id,
        "company_id": row.company_id,
        "owner_id": row.owner_id,
        "owner_name": owner.name if owner else "",
        "status": row.status,
        "location": row.location,
        "description": row.description,
        "requirement": row.requirement,
        "severity": row.severity,
        "affected_scope": row.affected_scope,
        "containment": row.containment,
        "raised_on": row.raised_on.isoformat(),
        "target_on": row.target_on.isoformat(),
        "root_cause": row.root_cause,
        "corrective_action": row.corrective_action,
        "disposition": row.disposition,
        "evidence": row.evidence,
        "verification": row.verification,
        "statement": row.statement,
        "version": row.version,
        "review": review_payload(db, user, instance) if instance else None,
        "closure_review": review_payload(db, user, closure) if closure else None,
        "concessions": [concession_view(db, user, project, item) for item in concessions],
    }


def _source_label(db, row):
    if row.activity_id:
        activity = db.get(ConstructionActivity, row.activity_id)
        return activity.code if activity else ""
    if row.request_id:
        found = db.get(ConstructionRequest, row.request_id)
        return found.number if found else ""
    if row.material_id:
        found = db.get(MaterialInspection, row.material_id)
        return found.number if found else ""
    found = db.get(QualityOffer, row.offer_id) if row.offer_id else None
    return found.number if found else ""


def concession_view(db, user, project, row):
    instance = _latest(db, project, CONCESSION, row.id)
    return {
        "id": row.id,
        "ncr_id": row.ncr_id,
        "number": row.number,
        "status": row.status,
        "proposal": row.proposal,
        "technical_note": row.technical_note,
        "statement": row.statement,
        "version": row.version,
        "review": review_payload(db, user, instance) if instance else None,
    }


def ncr_register(db, user, project):
    activities = []
    for package in db.query(WorkPackage).filter_by(project_id=project.id).order_by(WorkPackage.code):
        for activity in db.query(ConstructionActivity).filter_by(package_id=package.id, active=True).order_by(ConstructionActivity.code):
            activities.append({"id": activity.id, "label": f"{package.code} · {activity.code}"})
    requests = [
        {"id": row.id, "label": row.number}
        for row in db.query(ConstructionRequest).filter_by(project_id=project.id).filter(ConstructionRequest.status != "Cancelled")
    ]
    materials = [
        {"id": row.id, "label": row.number}
        for row in db.query(MaterialInspection).filter_by(project_id=project.id).filter(MaterialInspection.status != "Cancelled")
    ]
    offers = [
        {"id": row.id, "label": row.number}
        for row in db.query(QualityOffer).filter_by(project_id=project.id).filter(QualityOffer.status != "Cancelled")
    ]
    people = []
    companies = {}
    seen = set()
    for member in db.query(Membership).filter_by(project_id=project.id, active=True):
        company = db.get(Company, member.company_id)
        if company:
            companies[company.id] = company.name
        if member.user_id in seen:
            continue
        person = db.get(User, member.user_id)
        if person and person.active:
            seen.add(person.id)
            people.append({"id": person.id, "name": person.name})
    if project.client_company_id and project.client_company_id not in companies:
        client = db.get(Company, project.client_company_id)
        if client:
            companies[client.id] = client.name
    from app.domains.identity_projects.models import Discipline

    disciplines = []
    for row in db.query(ProjectDiscipline).filter_by(project_id=project.id, active=True):
        discipline = db.get(Discipline, row.discipline_id)
        if discipline:
            disciplines.append({"id": discipline.id, "name": discipline.name})
    rows = (
        db.query(Nonconformance)
        .filter_by(project_id=project.id)
        .filter(Nonconformance.status != "Cancelled")
        .order_by(Nonconformance.id.desc())
        .all()
    )
    return {
        "note": NCR_NOTE,
        "activities": activities,
        "requests": requests,
        "materials": materials,
        "offers": offers,
        "members": people,
        "companies": [{"id": key, "name": value} for key, value in companies.items()],
        "disciplines": disciplines,
        "ncrs": [ncr_view(db, user, project, row) for row in rows],
    }


def add_ncr(db, user, project, data):
    activity_id, request_id, material_id, offer_id, _label = _source(db, project, data.source_kind, data.source_id)
    if _open_ncr(db, project, data.source_kind, activity_id, request_id, material_id, offer_id):
        raise HTTPException(409, "This record already has an open NCR")
    _discipline(db, project, data.discipline_id)
    _company(db, project, data.company_id)
    owner = _member(db, project, data.owner_id, "owner")
    values = _fields(data)
    key = data.number.strip().casefold()
    if db.query(Nonconformance).filter_by(project_id=project.id, number_key=key).first():
        raise HTTPException(409, "NCR number already exists on this project")
    row = Nonconformance(
        organization_id=project.organization_id,
        project_id=project.id,
        source_kind=data.source_kind,
        activity_id=activity_id,
        request_id=request_id,
        material_id=material_id,
        offer_id=offer_id,
        discipline_id=data.discipline_id,
        company_id=data.company_id,
        owner_id=owner.id,
        number=data.number.strip(),
        number_key=key,
        statement=NCR_STATEMENT,
        payload={},
        created_by=user.id,
        modified_by=user.id,
        **values,
    )
    db.add(row)
    db.flush()
    return row


def update_ncr(db, user, project, row, data):
    if row.status not in NCR_EDIT:
        raise HTTPException(409, "This NCR can no longer be edited")
    activity_id, request_id, material_id, offer_id, _label = _source(db, project, data.source_kind, data.source_id)
    if _open_ncr(db, project, data.source_kind, activity_id, request_id, material_id, offer_id, row.id):
        raise HTTPException(409, "This record already has an open NCR")
    _discipline(db, project, data.discipline_id)
    _company(db, project, data.company_id)
    owner = _member(db, project, data.owner_id, "owner")
    values = _fields(data)
    values.update(
        {
            "source_kind": data.source_kind,
            "activity_id": activity_id,
            "request_id": request_id,
            "material_id": material_id,
            "offer_id": offer_id,
            "discipline_id": data.discipline_id,
            "company_id": data.company_id,
            "owner_id": owner.id,
            "modified_by": user.id,
        }
    )
    _bump(db, Nonconformance, row, data.version, values)


def submit_ncr(db, user, project, row, version):
    if row.status not in NCR_EDIT:
        raise HTTPException(409, "Only a draft NCR can be submitted")
    _require_concession(db, row)
    policy = _policy_for(db, project, NCR, row.company_id, row.discipline_id)
    payload = {
        "disposition": row.disposition,
        "corrective_action": row.corrective_action,
        "root_cause": row.root_cause,
        "containment": row.containment,
    }
    _bump(db, Nonconformance, row, version, {"status": "Pending Review", "payload": payload, "modified_by": user.id})
    return submit_record(db, user, project, NCR, row.id, row.version, policy)


def submit_closure(db, user, project, row, data):
    if row.status == "Verification Returned":
        _require_concession(db, row)
        payload = dict(row.payload or {})
        payload.update({"evidence": data.evidence.strip(), "verification": data.verification.strip()})
        _bump(
            db,
            Nonconformance,
            row,
            data.version,
            {
                "evidence": data.evidence.strip(),
                "verification": data.verification.strip(),
                "payload": payload,
                "modified_by": user.id,
            },
        )
        return _latest(db, project, NCR_CLOSE, row.id)
    if row.status != "Approved":
        raise HTTPException(409, "Close an NCR only after the disposition is approved")
    _require_concession(db, row)
    policy = _policy_for(db, project, NCR_CLOSE, row.company_id, row.discipline_id)
    payload = dict(row.payload or {})
    payload.update({"evidence": data.evidence.strip(), "verification": data.verification.strip()})
    _bump(
        db,
        Nonconformance,
        row,
        data.version,
        {
            "status": "Pending Verification",
            "evidence": data.evidence.strip(),
            "verification": data.verification.strip(),
            "payload": payload,
            "modified_by": user.id,
        },
    )
    return submit_record(db, user, project, NCR_CLOSE, row.id, row.version, policy)


def cancel_ncr(db, user, row, data):
    if row.status == "Pending Review":
        raise HTTPException(409, "This NCR is in review")
    if row.status not in NCR_EDIT:
        raise HTTPException(409, "Only a draft NCR can be cancelled here")
    _bump(
        db,
        Nonconformance,
        row,
        data.version,
        {"status": "Cancelled", "cancellation_reason": data.reason.strip(), "modified_by": user.id},
    )


def add_concession(db, user, project, data):
    ncr = db.get(Nonconformance, data.ncr_id)
    if not ncr or ncr.project_id != project.id or ncr.status == "Cancelled":
        raise HTTPException(404, "NCR not found")
    if ncr.disposition != "Use-As-Is":
        raise HTTPException(422, "A concession applies only to use-as-is")
    if ncr.status not in NCR_EDIT | {"Pending Review", "Approved"}:
        raise HTTPException(409, "This NCR is not open for a concession")
    open_row = (
        db.query(Concession)
        .filter(Concession.ncr_id == ncr.id, Concession.status.in_(("Draft", "Pending Review", "Returned for Correction", "Approved")))
        .first()
    )
    if open_row:
        raise HTTPException(409, "This NCR already has a concession")
    key = data.number.strip().casefold()
    if db.query(Concession).filter_by(project_id=project.id, number_key=key).first():
        raise HTTPException(409, "Concession number already exists on this project")
    row = Concession(
        organization_id=project.organization_id,
        project_id=project.id,
        ncr_id=ncr.id,
        number=data.number.strip(),
        number_key=key,
        proposal=data.proposal.strip(),
        technical_note=data.technical_note.strip(),
        statement=CONCESSION_STATEMENT,
        payload={"proposal": data.proposal.strip()},
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def submit_concession(db, user, project, row, version):
    if row.status not in CONCESSION_EDIT:
        raise HTTPException(409, "Only a draft concession can be submitted")
    ncr = db.get(Nonconformance, row.ncr_id)
    if not ncr or ncr.disposition != "Use-As-Is" or ncr.status in {"Closed", "Cancelled", "Rejected"}:
        raise HTTPException(409, "This NCR is not open for a concession")
    policy = _policy_for(db, project, CONCESSION, ncr.company_id, ncr.discipline_id)
    _bump(db, Concession, row, version, {"status": "Pending Review", "modified_by": user.id})
    return submit_record(db, user, project, CONCESSION, row.id, row.version, policy)


def _open_holds(db):
    return db.query(QualityHold).filter(QualityHold.status.in_(tuple(HOLD_OPEN)))


def hold_for_checkpoint(db, activity, point):
    return (
        _open_holds(db)
        .filter(
            QualityHold.activity_id == activity.id,
            QualityHold.checkpoint_id == point.id,
            QualityHold.scope_kind == "activity",
        )
        .first()
    )


def acceptance_blocked(db, request_row):
    if request_row.outcome not in {"Accepted", "Partially Accepted"} or not request_row.checkpoint_id:
        return False
    point = db.get(QualityCheckpoint, request_row.checkpoint_id)
    if not point or point.point_type != "Hold":
        return False
    return (
        _open_holds(db)
        .filter(
            QualityHold.activity_id == request_row.activity_id,
            QualityHold.checkpoint_id == request_row.checkpoint_id,
        )
        .first()
        is not None
    )


def issue_blocked(db, project_id, item_id):
    from .material import _item

    for hold in _open_holds(db).filter_by(project_id=project_id, scope_kind="receipt", blocks_issue=True):
        line = db.get(GoodsReceiptLine, hold.receipt_line_id)
        _code, found_id, _unit = _item(db, line)
        if found_id == item_id:
            return hold
    return None


def release_blocked(db, package):
    return (
        _open_holds(db)
        .filter_by(package_id=package.id, scope_kind="package", blocks_work=True)
        .first()
    )


def work_blocked(db, package, activity):
    package_hold = (
        _open_holds(db).filter_by(package_id=package.id, scope_kind="package", blocks_work=True).first()
    )
    if package_hold:
        return package_hold
    if not activity:
        return None
    return _open_holds(db).filter_by(activity_id=activity.id, scope_kind="activity", blocks_work=True).first()


def handover_problem(db, package):
    package_hold = (
        _open_holds(db).filter_by(package_id=package.id, scope_kind="package", blocks_handover=True).first()
    )
    if package_hold:
        return "A quality hold blocks handover"
    activity_ids = [row.id for row in db.query(ConstructionActivity).filter_by(package_id=package.id)]
    if not activity_ids:
        return None
    found = (
        _open_holds(db)
        .filter(
            QualityHold.activity_id.in_(activity_ids),
            QualityHold.scope_kind == "activity",
            QualityHold.blocks_handover.is_(True),
        )
        .first()
    )
    if found:
        return "A quality hold blocks handover"
    return None


def _scope(db, project, data):
    if data.scope_kind not in SCOPES:
        raise HTTPException(422, "Choose what this hold covers")
    package_id = activity_id = receipt_line_id = None
    company_id = discipline_id = None
    if data.scope_kind == "package":
        package = db.get(WorkPackage, data.scope_id)
        if not package or package.project_id != project.id:
            raise HTTPException(422, "Choose a work package on this project")
        if not data.blocks_work and not data.blocks_handover:
            raise HTTPException(422, "Choose the action this hold blocks")
        if data.blocks_issue:
            raise HTTPException(422, "A material hold names a receipt line")
        package_id = package.id
        company_id, discipline_id = package.company_id, package.discipline_id
    elif data.scope_kind == "activity":
        activity = db.get(ConstructionActivity, data.scope_id)
        package = db.get(WorkPackage, activity.package_id) if activity else None
        if not activity or not package or package.project_id != project.id or not activity.active:
            raise HTTPException(422, "Choose an activity on this project")
        if not data.blocks_work and not data.blocks_handover:
            raise HTTPException(422, "Choose the action this hold blocks")
        if data.blocks_issue:
            raise HTTPException(422, "A material hold names a receipt line")
        if data.checkpoint_id:
            point = db.get(QualityCheckpoint, data.checkpoint_id)
            document = db.get(QualityDocument, point.document_id) if point else None
            if (
                not point
                or not document
                or document.project_id != project.id
                or document.status != "Approved"
                or point.point_type != "Hold"
            ):
                raise HTTPException(422, "Choose a hold point on an approved ITP")
            if document.discipline_id and document.discipline_id != package.discipline_id:
                raise HTTPException(422, "The hold point is for another discipline")
        activity_id = activity.id
        package_id = package.id
        company_id, discipline_id = package.company_id, package.discipline_id
    else:
        line = db.get(GoodsReceiptLine, data.scope_id)
        receipt = db.get(GoodsReceipt, line.goods_receipt_id) if line else None
        if not line or not receipt or receipt.project_id != project.id or receipt.status != "Posted":
            raise HTTPException(422, "Choose a posted receipt line")
        if not data.blocks_issue:
            raise HTTPException(422, "A receipt hold blocks material issue")
        if data.blocks_work or data.blocks_handover:
            raise HTTPException(422, "Work and handover holds name a package or activity")
        receipt_line_id = line.id
        from app.domains.supply_chain.models import PurchaseOrder

        order = db.get(PurchaseOrder, receipt.purchase_order_id)
        if order:
            company_id, discipline_id = order.company_id, order.discipline_id
    if data.ncr_id:
        ncr = db.get(Nonconformance, data.ncr_id)
        if not ncr or ncr.project_id != project.id or ncr.status == "Cancelled":
            raise HTTPException(422, "Choose an NCR on this project")
    return package_id, activity_id, receipt_line_id, company_id, discipline_id


def hold_view(db, user, project, row):
    owner = db.get(User, row.owner_id)
    instance = _latest(db, project, HOLD, row.id)
    return {
        "id": row.id,
        "number": row.number,
        "scope_kind": row.scope_kind,
        "scope_label": _hold_label(db, row),
        "package_id": row.package_id,
        "activity_id": row.activity_id,
        "receipt_line_id": row.receipt_line_id,
        "checkpoint_id": row.checkpoint_id,
        "ncr_id": row.ncr_id,
        "owner_id": row.owner_id,
        "owner_name": owner.name if owner else "",
        "status": row.status,
        "reason": row.reason,
        "conditions": row.conditions,
        "evidence": row.evidence,
        "blocks_issue": row.blocks_issue,
        "blocks_work": row.blocks_work,
        "blocks_handover": row.blocks_handover,
        "statement": row.statement,
        "released_on": row.released_on.isoformat() if row.released_on else None,
        "version": row.version,
        "review": review_payload(db, user, instance) if instance else None,
    }


def _hold_label(db, row):
    if row.scope_kind == "activity" and row.activity_id:
        activity = db.get(ConstructionActivity, row.activity_id)
        return activity.code if activity else ""
    if row.scope_kind == "package" and row.package_id:
        package = db.get(WorkPackage, row.package_id)
        return package.code if package else ""
    if row.receipt_line_id:
        from .material import _item

        line = db.get(GoodsReceiptLine, row.receipt_line_id)
        code, _item_id, _unit = _item(db, line)
        receipt = db.get(GoodsReceipt, line.goods_receipt_id) if line else None
        return f"{receipt.number} · {code}" if receipt else code
    return ""


def hold_register(db, user, project):
    packages = [
        {"id": row.id, "label": row.code}
        for row in db.query(WorkPackage).filter_by(project_id=project.id).order_by(WorkPackage.code)
    ]
    activities = []
    for package in db.query(WorkPackage).filter_by(project_id=project.id):
        for activity in db.query(ConstructionActivity).filter_by(package_id=package.id, active=True).order_by(ConstructionActivity.code):
            activities.append({"id": activity.id, "label": f"{package.code} · {activity.code}", "discipline_id": package.discipline_id})
    receipts = []
    for receipt in db.query(GoodsReceipt).filter_by(project_id=project.id, status="Posted"):
        for line in db.query(GoodsReceiptLine).filter_by(goods_receipt_id=receipt.id):
            from .material import _item

            code, _item_id, _unit = _item(db, line)
            receipts.append({"id": line.id, "label": f"{receipt.number} · {code}"})
    points = []
    for document in db.query(QualityDocument).filter_by(project_id=project.id, kind="ITP", status="Approved"):
        for point in db.query(QualityCheckpoint).filter_by(document_id=document.id, point_type="Hold"):
            points.append(
                {
                    "id": point.id,
                    "name": point.name,
                    "discipline_id": document.discipline_id,
                    "label": f"{document.number} rev {document.revision_label} · {point.name}",
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
    ncrs = [
        {"id": row.id, "label": row.number}
        for row in db.query(Nonconformance).filter_by(project_id=project.id).filter(Nonconformance.status != "Cancelled")
    ]
    rows = db.query(QualityHold).filter_by(project_id=project.id).order_by(QualityHold.id.desc()).all()
    return {
        "note": HOLD_NOTE,
        "packages": packages,
        "activities": activities,
        "receipts": receipts,
        "checkpoints": points,
        "members": people,
        "ncrs": ncrs,
        "holds": [hold_view(db, user, project, row) for row in rows],
    }


def add_hold(db, user, project, data):
    package_id, activity_id, receipt_line_id, _company_id, _discipline_id = _scope(db, project, data)
    owner = _member(db, project, data.owner_id, "owner")
    query = _open_holds(db).filter_by(project_id=project.id, scope_kind=data.scope_kind)
    if data.scope_kind == "package":
        query = query.filter_by(package_id=package_id)
    elif data.scope_kind == "activity":
        query = query.filter_by(activity_id=activity_id)
    else:
        query = query.filter_by(receipt_line_id=receipt_line_id)
    if query.first():
        raise HTTPException(409, "This scope already has an open quality hold")
    key = data.number.strip().casefold()
    if db.query(QualityHold).filter_by(project_id=project.id, number_key=key).first():
        raise HTTPException(409, "Hold number already exists on this project")
    row = QualityHold(
        organization_id=project.organization_id,
        project_id=project.id,
        scope_kind=data.scope_kind,
        package_id=package_id,
        activity_id=activity_id,
        receipt_line_id=receipt_line_id,
        checkpoint_id=data.checkpoint_id if data.scope_kind == "activity" else None,
        ncr_id=data.ncr_id,
        owner_id=owner.id,
        number=data.number.strip(),
        number_key=key,
        status="Active",
        reason=data.reason.strip(),
        conditions=data.conditions.strip(),
        blocks_issue=data.blocks_issue,
        blocks_work=data.blocks_work,
        blocks_handover=data.blocks_handover,
        statement=HOLD_STATEMENT,
        payload={"conditions": data.conditions.strip()},
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(row)
    db.flush()
    _tell(
        db,
        project,
        _watchers(db, project),
        "Quality hold raised",
        f"{row.number} is active. Release does not accept the work or certify billing.",
        f"quality.hold.{row.id}.raised",
    )
    return row


def submit_release(db, user, project, row, data):
    if row.status not in {"Active", "Release Returned"}:
        raise HTTPException(409, "This hold is not waiting for release")
    _company, discipline = _hold_scope_ids(db, row)
    policy = _policy_for(db, project, HOLD, _company, discipline)
    payload = dict(row.payload or {})
    payload["evidence"] = data.evidence.strip()
    _bump(
        db,
        QualityHold,
        row,
        data.version,
        {"status": "Pending Release", "evidence": data.evidence.strip(), "payload": payload, "modified_by": user.id},
    )
    return submit_record(db, user, project, HOLD, row.id, row.version, policy)


def _hold_scope_ids(db, row):
    if row.package_id:
        package = db.get(WorkPackage, row.package_id)
        if package:
            return package.company_id, package.discipline_id
    if row.receipt_line_id:
        from app.domains.supply_chain.models import PurchaseOrder

        line = db.get(GoodsReceiptLine, row.receipt_line_id)
        receipt = db.get(GoodsReceipt, line.goods_receipt_id) if line else None
        order = db.get(PurchaseOrder, receipt.purchase_order_id) if receipt else None
        if order:
            return order.company_id, order.discipline_id
    return None, None


def apply_resubmit(db, user, instance, review_version):
    from app.domains.coordination.service import _close_tasks, _lock, _open_stage, current_stage
    from app.domains.identity_projects.models import Project

    if instance.record_type not in {NCR, NCR_CLOSE, CONCESSION, HOLD}:
        return
    if instance.state != "Returned":
        raise HTTPException(409, "Only a returned review can be resubmitted")
    if user.id != instance.submitted_by and not user.organization_admin:
        raise HTTPException(403, "Only the submitter can resubmit")
    project = db.get(Project, instance.project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if instance.record_type in {NCR, NCR_CLOSE}:
        if not holds(db, user, project, "quality.plan") and not (
            instance.record_type == NCR_CLOSE and holds(db, user, project, "quality.edit")
        ):
            raise HTTPException(403, "Insufficient project permission")
        row = db.get(Nonconformance, instance.record_id)
        if not row or row.project_id != project.id:
            raise HTTPException(404, "NCR not found")
        if instance.record_type == NCR:
            if row.status != "Returned for Correction":
                raise HTTPException(409, "Only a returned NCR can be resubmitted")
            _require_concession(db, row)
            status = "Pending Review"
            policy = _policy_for(db, project, NCR, row.company_id, row.discipline_id)
        else:
            if row.status != "Verification Returned":
                raise HTTPException(409, "Only a returned closure can be resubmitted")
            if len((row.evidence or "").strip()) < 3 or len((row.verification or "").strip()) < 3:
                raise HTTPException(422, "Record the corrective evidence and the verification")
            _require_concession(db, row)
            status = "Pending Verification"
            policy = _policy_for(db, project, NCR_CLOSE, row.company_id, row.discipline_id)
        model, record = Nonconformance, row
    elif instance.record_type == CONCESSION:
        if not holds(db, user, project, "quality.plan") and not holds(db, user, project, "quality.edit"):
            raise HTTPException(403, "Insufficient project permission")
        row = db.get(Concession, instance.record_id)
        ncr = db.get(Nonconformance, row.ncr_id) if row else None
        if not row or not ncr or ncr.project_id != project.id:
            raise HTTPException(404, "Concession not found")
        if row.status != "Returned for Correction":
            raise HTTPException(409, "Only a returned concession can be resubmitted")
        status = "Pending Review"
        policy = _policy_for(db, project, CONCESSION, ncr.company_id, ncr.discipline_id)
        model, record = Concession, row
    else:
        if not holds(db, user, project, "quality.plan") and not holds(db, user, project, "quality.edit"):
            raise HTTPException(403, "Insufficient project permission")
        row = db.get(QualityHold, instance.record_id)
        if not row or row.project_id != project.id:
            raise HTTPException(404, "Quality hold not found")
        if row.status != "Release Returned":
            raise HTTPException(409, "Only a returned release can be resubmitted")
        if len((row.evidence or "").strip()) < 3:
            raise HTTPException(422, "Record the evidence that the release conditions are met")
        company_id, discipline_id = _hold_scope_ids(db, row)
        status = "Pending Release"
        policy = _policy_for(db, project, HOLD, company_id, discipline_id)
        model, record = QualityHold, row
    _lock(db, instance, review_version)
    _close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    _bump(db, model, record, record.version, {"status": status, "modified_by": user.id})
    instance.record_version = record.version
    instance.policy_id = policy.id
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def on_review_event(db, user, instance, project, action, stage=None):
    if instance.record_type not in {NCR, NCR_CLOSE, CONCESSION, HOLD}:
        return
    if action == "advance":
        return
    if instance.record_type == CONCESSION:
        row = db.get(Concession, instance.record_id)
        if not row or row.project_id != project.id:
            return
        if action == "return":
            row.status = "Returned for Correction"
        elif action == "reject":
            row.status = "Rejected"
        elif instance.state == "Approved":
            row.status = "Approved"
            _tell(
                db,
                project,
                _watchers(db, project),
                "Concession approved",
                f"{row.number} allows use-as-is. It does not close the NCR, accept the work, or certify billing.",
                f"quality.concession.{row.id}",
            )
        else:
            return
        row.version += 1
        row.modified_by = user.id
        row.modified_at = now()
        return
    if instance.record_type == HOLD:
        row = db.get(QualityHold, instance.record_id)
        if not row or row.project_id != project.id:
            return
        if action == "return":
            row.status = "Release Returned"
        elif action == "reject":
            row.status = "Active"
        elif instance.state == "Approved":
            row.status = "Released"
            row.released_by = user.id
            row.released_on = date.today()
            _tell(
                db,
                project,
                _watchers(db, project),
                "Quality hold released",
                f"{row.number} is released. This does not accept the work or certify billing.",
                f"quality.hold.{row.id}.released",
            )
        else:
            return
        row.version += 1
        row.modified_by = user.id
        row.modified_at = now()
        return
    row = db.get(Nonconformance, instance.record_id)
    if not row or row.project_id != project.id:
        return
    if instance.record_type == NCR_CLOSE:
        if action == "return":
            row.status = "Verification Returned"
        elif action == "reject":
            row.status = "Approved"
        elif instance.state == "Approved":
            row.status = "Closed"
            _tell(
                db,
                project,
                _watchers(db, project),
                "NCR closed",
                f"{row.number} is closed. This does not accept the work or certify billing.",
                f"quality.ncr.{row.id}.closed",
            )
        else:
            return
    elif action == "return":
        row.status = "Returned for Correction"
    elif action == "reject":
        row.status = "Rejected"
    elif instance.state == "Approved":
        row.status = "Approved"
        _tell(
            db,
            project,
            _watchers(db, project),
            "NCR disposition approved",
            f"{row.number} has an approved disposition. This does not accept the work or certify billing.",
            f"quality.ncr.{row.id}",
        )
    else:
        return
    row.version += 1
    row.modified_by = user.id
    row.modified_at = now()


def review_guard(db, user, instance, stage, action):
    if action != "approve" or instance.record_type not in {NCR, NCR_CLOSE, CONCESSION, HOLD}:
        return
    from app.domains.identity_projects.models import Project

    project = db.get(Project, instance.project_id)
    if instance.record_type == CONCESSION:
        row = db.get(Concession, instance.record_id)
        ncr = db.get(Nonconformance, row.ncr_id) if row else None
        if not project or not row or not ncr or ncr.project_id != project.id or row.status != "Pending Review":
            raise HTTPException(409, "This concession is not awaiting review")
        if ncr.disposition != "Use-As-Is" or ncr.status in {"Closed", "Cancelled", "Rejected"}:
            raise HTTPException(409, "This NCR is not open for a concession")
        return
    if instance.record_type == HOLD:
        row = db.get(QualityHold, instance.record_id)
        if not project or not row or row.project_id != project.id or row.status != "Pending Release":
            raise HTTPException(409, "This hold is not awaiting release")
        if len((row.evidence or "").strip()) < 3:
            raise HTTPException(409, "The release evidence is missing. Return the hold")
        return
    row = db.get(Nonconformance, instance.record_id)
    if not project or not row or row.project_id != project.id:
        raise HTTPException(409, "This NCR is not awaiting review")
    if instance.record_type == NCR:
        if row.status != "Pending Review":
            raise HTTPException(409, "This NCR is not awaiting review")
        if row.disposition == "Use-As-Is" and not _concession_for(db, row):
            raise HTTPException(409, "Use-as-is needs an approved concession. Return the NCR")
        return
    if row.status != "Pending Verification":
        raise HTTPException(409, "This NCR is not awaiting closure")
    if len((row.evidence or "").strip()) < 3 or len((row.verification or "").strip()) < 3:
        raise HTTPException(409, "The closure evidence changed. Return the NCR")
    if row.disposition == "Use-As-Is" and not _concession_for(db, row):
        raise HTTPException(409, "Use-as-is needs an approved concession. Return the NCR")


if review_guard not in REVIEW_GUARDS:
    REVIEW_GUARDS.append(review_guard)
