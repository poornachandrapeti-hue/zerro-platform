"""Incoming material inspection for a posted goods receipt.

Quality records the receipt, the item, and the quantity, then splits that
quantity into pending, accepted, rejected, and quarantined. Those four amounts
stay equal to the quantity received. Later decisions are new lines, so the
earlier result stays on record. Only an approved accepted quantity can be put
on hand. Accepting the material does not accept the installation work.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import update

from app.domains.construction.monitoring import _tell
from app.domains.construction.service import qty
from app.domains.coordination.service import REVIEW_GUARDS, review_payload
from app.domains.engineering_documents.workflow import submit_record
from app.domains.identity_projects.models import Membership, User
from app.domains.identity_projects.security import permitted
from app.domains.supply_chain.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    ProcurementItem,
    PurchaseOrder,
    PurchaseOrderLine,
    QuotationLine,
    RequisitionLine,
    RfqAward,
    RfqLine,
)
from app.domains.supply_chain.service import _authority, _policy, _project_member

from .models import MaterialDisposition, MaterialInspection, now

MATERIAL = "quality.material"
OPEN = {"Draft", "Pending Review", "Returned for Correction"}
EDITABLE = {"Draft", "Returned for Correction"}
REVIEWING = {"Pending Review", "Returned for Correction"}
MOVES = {
    "Pending": {"Accepted", "Rejected", "Quarantined"},
    "Quarantined": {"Accepted", "Rejected"},
}
STATEMENT = (
    "This inspection records how the received quantity is split into pending, accepted, "
    "rejected, and quarantined. Accepting the material does not accept the installation "
    "work, certify billing, or create a commissioning test."
)
NOTE = (
    "A posted goods receipt can be offered for inspection. Quality splits the received "
    "quantity into pending, accepted, rejected, and quarantined. Those four amounts stay "
    "equal to the quantity received. Only the accepted quantity can be put on hand. "
    "Accepting the material does not accept the installation work."
)
WATCH = {"QA/QC", "Stores Officer", "Project Manager", "Discipline Head"}


def quality_accepted(db, receipt_line_id):
    return _totals(db, receipt_line_id)["accepted"]


def _q(value):
    return Decimal(value).quantize(Decimal("0.001"))


def _bump(db, row, version, values):
    changed = db.execute(
        update(MaterialInspection)
        .where(MaterialInspection.id == row.id, MaterialInspection.version == version)
        .values(version=version + 1, modified_at=now(), **values)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This material inspection changed. Reload it and try again")
    db.refresh(row)


def _latest_review(db, project, row):
    from app.domains.coordination.models import ReviewInstance

    return (
        db.query(ReviewInstance)
        .filter_by(project_id=project.id, record_type=MATERIAL, record_id=row.id)
        .order_by(ReviewInstance.id.desc())
        .first()
    )


def _lines(db, row):
    return (
        db.query(MaterialDisposition)
        .filter_by(inspection_id=row.id)
        .order_by(MaterialDisposition.id)
        .all()
    )


def _receipt(db, project, receipt_id):
    row = db.get(GoodsReceipt, receipt_id)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "Goods receipt not found")
    return row


def _posted(receipt):
    if receipt.status != "Posted":
        raise HTTPException(422, "Inspection applies to a posted goods receipt")


def _inspector(db, project, inspector_id):
    person = db.get(User, inspector_id)
    if not _project_member(db, project, person):
        raise HTTPException(422, "Choose an active project member as the inspector")
    return person


def _item(db, line):
    order_line = db.get(PurchaseOrderLine, line.purchase_order_line_id) if line else None
    award = db.get(RfqAward, order_line.award_id) if order_line else None
    quote_line = db.get(QuotationLine, award.quotation_line_id) if award else None
    rfq_line = db.get(RfqLine, quote_line.rfq_line_id) if quote_line else None
    source = db.get(RequisitionLine, rfq_line.requisition_line_id) if rfq_line else None
    item = db.get(ProcurementItem, source.item_id) if source else None
    if not item or not source:
        return "Item", None, ""
    return item.code, item.id, source.unit


def _joined(db, receipt_line_id, statuses, ignore_id=None):
    query = (
        db.query(MaterialDisposition, MaterialInspection)
        .join(MaterialInspection, MaterialInspection.id == MaterialDisposition.inspection_id)
        .filter(
            MaterialDisposition.goods_receipt_line_id == receipt_line_id,
            MaterialInspection.status.in_(tuple(statuses)),
        )
    )
    if ignore_id:
        query = query.filter(MaterialInspection.id != ignore_id)
    return query.all()


def _totals(db, receipt_line_id, ignore_id=None):
    accepted = rejected = quarantined = Decimal("0")
    for disposition, _inspection in _joined(db, receipt_line_id, {"Approved"}, ignore_id):
        amount = _q(disposition.quantity)
        if disposition.from_state == "Quarantined":
            quarantined -= amount
        if disposition.to_state == "Accepted":
            accepted += amount
        elif disposition.to_state == "Rejected":
            rejected += amount
        elif disposition.to_state == "Quarantined":
            quarantined += amount
    return {"accepted": accepted, "rejected": rejected, "quarantined": quarantined}


def _reserved(db, receipt_line_id, ignore_id=None):
    pending = quarantine = Decimal("0")
    for disposition, _inspection in _joined(db, receipt_line_id, REVIEWING, ignore_id):
        amount = _q(disposition.quantity)
        if disposition.from_state == "Quarantined":
            quarantine += amount
        else:
            pending += amount
    return pending, quarantine


def line_balance(db, line, ignore_id=None):
    received = _q(line.quantity)
    totals = _totals(db, line.id, ignore_id)
    pending = received - totals["accepted"] - totals["rejected"] - totals["quarantined"]
    held_pending, held_quarantine = _reserved(db, line.id, ignore_id)
    code, item_id, unit = _item(db, line)
    return {
        "id": line.id,
        "item_id": item_id,
        "item_code": code,
        "unit": unit,
        "received": qty(received),
        "pending": qty(pending),
        "accepted": qty(totals["accepted"]),
        "rejected": qty(totals["rejected"]),
        "quarantined": qty(totals["quarantined"]),
        "available_pending": qty(pending - held_pending),
        "available_quarantined": qty(totals["quarantined"] - held_quarantine),
    }


def _blocking(db, receipt, ignore_id=None):
    query = db.query(MaterialInspection).filter(
        MaterialInspection.goods_receipt_id == receipt.id,
        MaterialInspection.status.in_(tuple(OPEN)),
    )
    if ignore_id:
        query = query.filter(MaterialInspection.id != ignore_id)
    return query.first() is not None


def _check_dates(data):
    if data.inspected_on and data.inspected_on < data.requested_on:
        raise HTTPException(422, "Inspection date cannot be before the request")


def _check_lines(db, receipt, incoming, ignore_id=None):
    _posted(receipt)
    grouped = {}
    prepared = []
    for row in incoming:
        origin = row.from_state.strip()
        destination = row.to_state.strip()
        if origin in {"Accepted", "Rejected"}:
            raise HTTPException(422, "An accepted or rejected quantity stays on record")
        if origin not in MOVES or destination not in MOVES[origin]:
            raise HTTPException(
                422,
                "That quantity can move only from pending or quarantine into accepted, rejected, or quarantine",
            )
        line = db.get(GoodsReceiptLine, row.goods_receipt_line_id)
        if not line or line.goods_receipt_id != receipt.id:
            raise HTTPException(422, "Each line must belong to this goods receipt")
        amount = _q(row.quantity)
        bucket = grouped.setdefault(line.id, {"Pending": Decimal("0"), "Quarantined": Decimal("0"), "line": line})
        bucket[origin] += amount
        prepared.append((line, origin, destination, amount, row))
    for bucket in grouped.values():
        balance = line_balance(db, bucket["line"], ignore_id)
        if bucket["Pending"] > _q(balance["available_pending"]):
            raise HTTPException(422, "Only the quantity still pending inspection can be decided")
        if bucket["Quarantined"] > _q(balance["available_quarantined"]):
            raise HTTPException(422, "Only the quarantined quantity still waiting can be decided")
    return prepared


def _replace_lines(db, row, prepared):
    db.query(MaterialDisposition).filter_by(inspection_id=row.id).delete()
    for line, origin, destination, amount, incoming in prepared:
        db.add(
            MaterialDisposition(
                inspection_id=row.id,
                goods_receipt_line_id=line.id,
                from_state=origin,
                to_state=destination,
                quantity=amount,
                batch_number=incoming.batch_number.strip(),
                heat_number=incoming.heat_number.strip(),
                serial_number=incoming.serial_number.strip(),
            )
        )
    db.flush()


def _snapshot(db, receipt, row):
    return {
        "receipt_number": receipt.number,
        "statement": STATEMENT,
        "lines": [
            {
                "goods_receipt_line_id": line.goods_receipt_line_id,
                "from_state": line.from_state,
                "to_state": line.to_state,
                "quantity": qty(line.quantity),
                "batch_number": line.batch_number,
                "heat_number": line.heat_number,
                "serial_number": line.serial_number,
            }
            for line in _lines(db, row)
        ],
    }


def _policy_for(db, project, receipt):
    order = db.get(PurchaseOrder, receipt.purchase_order_id)
    policy = _policy(db, project, MATERIAL, None, order.discipline_id if order else None)
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


def _members(db, project):
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


def _disposition_view(db, line):
    code, _item_id, unit = _item(db, db.get(GoodsReceiptLine, line.goods_receipt_line_id))
    return {
        "goods_receipt_line_id": line.goods_receipt_line_id,
        "item_code": code,
        "unit": unit,
        "from_state": line.from_state,
        "to_state": line.to_state,
        "quantity": qty(line.quantity),
        "batch_number": line.batch_number,
        "heat_number": line.heat_number,
        "serial_number": line.serial_number,
    }


def inspection_view(db, user, project, row):
    receipt = db.get(GoodsReceipt, row.goods_receipt_id)
    inspector = db.get(User, row.inspector_id)
    instance = _latest_review(db, project, row)
    return {
        "id": row.id,
        "number": row.number,
        "goods_receipt_id": row.goods_receipt_id,
        "receipt_number": receipt.number if receipt else "",
        "receipt_status": receipt.status if receipt else "",
        "status": row.status,
        "inspector_id": row.inspector_id,
        "inspector_name": inspector.name if inspector else "",
        "requested_on": row.requested_on.isoformat(),
        "inspected_on": row.inspected_on.isoformat() if row.inspected_on else None,
        "certificate_reference": row.certificate_reference,
        "findings": row.findings,
        "statement": row.statement,
        "payload": row.payload or {},
        "lines": [_disposition_view(db, line) for line in _lines(db, row)],
        "cancellation_reason": row.cancellation_reason,
        "version": row.version,
        "review": review_payload(db, user, instance) if instance else None,
    }


def _receipt_view(db, receipt):
    lines = (
        db.query(GoodsReceiptLine)
        .filter_by(goods_receipt_id=receipt.id)
        .order_by(GoodsReceiptLine.id)
        .all()
    )
    return {
        "id": receipt.id,
        "number": receipt.number,
        "status": receipt.status,
        "receipt_date": receipt.receipt_date.isoformat(),
        "lines": [line_balance(db, line) for line in lines],
    }


def register(db, user, project):
    receipts = (
        db.query(GoodsReceipt)
        .filter_by(project_id=project.id, status="Posted")
        .order_by(GoodsReceipt.number)
        .all()
    )
    inspections = (
        db.query(MaterialInspection)
        .filter_by(project_id=project.id)
        .filter(MaterialInspection.status != "Cancelled")
        .order_by(MaterialInspection.id.desc())
        .all()
    )
    return {
        "note": NOTE,
        "receipts": [_receipt_view(db, row) for row in receipts],
        "inspections": [inspection_view(db, user, project, row) for row in inspections],
        "members": _members(db, project),
    }


def _fill(row, data, inspector):
    row.inspector_id = inspector.id
    row.requested_on = data.requested_on
    row.inspected_on = data.inspected_on
    row.certificate_reference = data.certificate_reference.strip()
    row.findings = data.findings.strip()


def add_inspection(db, user, project, data):
    receipt = _receipt(db, project, data.goods_receipt_id)
    _posted(receipt)
    if _blocking(db, receipt):
        raise HTTPException(409, "This receipt already has an open material inspection")
    inspector = _inspector(db, project, data.inspector_id)
    _check_dates(data)
    prepared = _check_lines(db, receipt, data.lines)
    key = data.number.strip().casefold()
    if db.query(MaterialInspection).filter_by(project_id=project.id, number_key=key).first():
        raise HTTPException(409, "Inspection number already exists on this project")
    row = MaterialInspection(
        organization_id=project.organization_id,
        project_id=project.id,
        goods_receipt_id=receipt.id,
        number=data.number.strip(),
        number_key=key,
        statement=STATEMENT,
        payload={},
        created_by=user.id,
        modified_by=user.id,
    )
    _fill(row, data, inspector)
    db.add(row)
    db.flush()
    _replace_lines(db, row, prepared)
    return row


def update_inspection(db, user, project, row, data):
    if row.status not in EDITABLE:
        raise HTTPException(409, "An approved material inspection is kept. Record a later decision")
    receipt = _receipt(db, project, row.goods_receipt_id)
    inspector = _inspector(db, project, data.inspector_id)
    _check_dates(data)
    prepared = _check_lines(db, receipt, data.lines, ignore_id=row.id)
    _replace_lines(db, row, prepared)
    _bump(
        db,
        row,
        data.version,
        {
            "inspector_id": inspector.id,
            "requested_on": data.requested_on,
            "inspected_on": data.inspected_on,
            "certificate_reference": data.certificate_reference.strip(),
            "findings": data.findings.strip(),
            "modified_by": user.id,
        },
    )
    return row


def submit_inspection(db, user, project, row, version):
    if row.status == "Returned for Correction":
        raise HTTPException(409, "A returned inspection is resubmitted, not submitted again")
    if row.status != "Draft":
        raise HTTPException(409, "Only a draft inspection can be submitted")
    receipt = _receipt(db, project, row.goods_receipt_id)
    if _blocking(db, receipt, ignore_id=row.id):
        raise HTTPException(409, "This receipt already has an open material inspection")
    _inspector(db, project, row.inspector_id)
    prepared = _check_lines(db, receipt, _lines(db, row), ignore_id=row.id)
    if not prepared:
        raise HTTPException(422, "Record at least one quantity")
    policy = _policy_for(db, project, receipt)
    _bump(db, row, version, {"status": "Pending Review", "modified_by": user.id})
    row.payload = _snapshot(db, receipt, row)
    db.flush()
    return submit_record(db, user, project, MATERIAL, row.id, row.version, policy)


def apply_resubmit(db, user, instance, review_version):
    from app.domains.coordination.service import _close_tasks, _lock, _open_stage, current_stage
    from app.domains.identity_projects.models import Project

    if instance.record_type != MATERIAL:
        return
    if instance.state != "Returned":
        raise HTTPException(409, "Only a returned review can be resubmitted")
    if user.id != instance.submitted_by and not user.organization_admin:
        raise HTTPException(403, "Only the submitter can resubmit")
    project = db.get(Project, instance.project_id)
    row = db.get(MaterialInspection, instance.record_id)
    receipt = db.get(GoodsReceipt, row.goods_receipt_id) if row else None
    if not project or not row or not receipt or receipt.project_id != project.id:
        raise HTTPException(404, "Material inspection not found")
    permitted(db, user, project, "quality.plan")
    if row.status != "Returned for Correction":
        raise HTTPException(409, "Only a returned inspection can be resubmitted")
    if _blocking(db, receipt, ignore_id=row.id):
        raise HTTPException(409, "This receipt already has an open material inspection")
    _inspector(db, project, row.inspector_id)
    prepared = _check_lines(db, receipt, _lines(db, row), ignore_id=row.id)
    if not prepared:
        raise HTTPException(422, "Record at least one quantity")
    policy = _policy_for(db, project, receipt)
    _lock(db, instance, review_version)
    _close_tasks(db, project.id, instance.record_type, instance.id, "Completed", "Corrected and resubmitted")
    instance.attempt += 1
    instance.state = "In Review"
    _bump(db, row, row.version, {"status": "Pending Review", "modified_by": user.id})
    row.payload = _snapshot(db, receipt, row)
    instance.record_version = row.version
    instance.policy_id = policy.id
    _open_stage(db, user, project, instance, current_stage(db, instance))
    return instance


def cancel_inspection(db, user, row, data):
    if row.status == "Pending Review":
        raise HTTPException(409, "This inspection is in review")
    if row.status not in EDITABLE:
        raise HTTPException(409, "Only a draft inspection can be cancelled here")
    _bump(
        db,
        row,
        data.version,
        {"status": "Cancelled", "cancellation_reason": data.reason.strip(), "modified_by": user.id},
    )


def on_review_event(db, user, instance, project, action, stage=None):
    if instance.record_type != MATERIAL:
        return
    row = db.get(MaterialInspection, instance.record_id)
    receipt = db.get(GoodsReceipt, row.goods_receipt_id) if row else None
    if not row or not receipt or receipt.project_id != project.id:
        return
    if action == "advance":
        return
    if action == "return":
        row.status = "Returned for Correction"
    elif action == "reject":
        row.status = "Rejected"
    elif instance.state == "Approved":
        row.status = "Approved"
        accepted = sum(_q(line.quantity) for line in _lines(db, row) if line.to_state == "Accepted")
        title = "Material quantity accepted" if accepted else "Material inspection decided"
        _tell(
            db,
            project,
            _watchers(db, project),
            title,
            (
                f"{receipt.number} has a quality decision. This does not accept the installation "
                "work or certify billing."
            ),
            f"quality.material.{row.id}",
        )
    else:
        return
    row.version += 1
    row.modified_by = user.id
    row.modified_at = now()


def review_guard(db, user, instance, stage, action):
    if instance.record_type != MATERIAL or action != "approve":
        return
    from app.domains.identity_projects.models import Project

    project = db.get(Project, instance.project_id)
    row = db.get(MaterialInspection, instance.record_id)
    receipt = db.get(GoodsReceipt, row.goods_receipt_id) if row else None
    if not project or not row or not receipt or receipt.project_id != project.id or row.status != "Pending Review":
        raise HTTPException(409, "This material inspection is not awaiting review")
    if receipt.status != "Posted":
        raise HTTPException(409, "Inspection applies to a posted goods receipt")
    try:
        _check_lines(db, receipt, _lines(db, row), ignore_id=row.id)
    except HTTPException as exc:
        raise HTTPException(409, "This quantity is no longer waiting for inspection") from exc


if review_guard not in REVIEW_GUARDS:
    REVIEW_GUARDS.append(review_guard)
