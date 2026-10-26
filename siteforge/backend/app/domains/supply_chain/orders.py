"""Purchase orders from an RFQ award. Goods receipts update delivery. Invoices record the supplier bill."""

from datetime import date
from decimal import Decimal

from fastapi import HTTPException

from app.domains.coordination.models import PolicyReviewer, PolicyStage
from app.domains.identity_projects.models import Discipline, User
from app.domains.identity_projects.security import holds

from .models import (
    ProcurementItem,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequisition,
    QuotationLine,
    RequestForQuotation,
    RequisitionLine,
    RfqAward,
    RfqLine,
    Vendor,
    VendorQuotation,
)
from .service import (
    _amount,
    _bump,
    _commercial,
    _event,
    _key,
    _name,
    _policy,
    _review,
    _stamp,
)

ORDER = "procurement.purchase_order"
STEPS = [
    "Draft",
    "Pending Approval",
    "Approved",
    "Issued",
    "Acknowledged",
    "Partially Received",
    "Received",
    "Closed",
]
COMMITTED = {"Issued", "Acknowledged", "Partially Received", "Received", "Closed"}
ACTIVE = {
    "Draft",
    "Pending Approval",
    "Returned for Correction",
    "Approved",
    *COMMITTED,
}
ISSUED = COMMITTED
EDITABLE = {"Draft", "Returned for Correction"}


def _buyer(db, user, project):
    if not holds(db, user, project, "procurement.po.edit"):
        raise HTTPException(403, "Creating and issuing a purchase order requires buying access")


def _approvers(db, project, row):
    policy = _policy(db, project, ORDER, row.company_id, row.discipline_id)
    people = []
    if not policy:
        return people
    for stage in db.query(PolicyStage).filter_by(policy_id=policy.id):
        for reviewer in db.query(PolicyReviewer).filter_by(stage_id=stage.id):
            person = db.get(User, reviewer.user_id)
            if person and person.id not in {item["id"] for item in people}:
                people.append({"id": person.id, "name": person.name})
    return people


def _has_successor(db, po_id):
    return (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.supersedes_id == po_id, PurchaseOrder.status.in_(ACTIVE))
        .first()
        is not None
    )


def held_qty(db, award_id, skip_po_id=None):
    total = Decimal("0")
    for line in db.query(PurchaseOrderLine).filter_by(award_id=award_id):
        row = db.get(PurchaseOrder, line.purchase_order_id)
        if not row or row.status not in ACTIVE or row.id == skip_po_id:
            continue
        if _has_successor(db, row.id):
            continue
        total += _amount(line.quantity)
    return total


def issued_for_requisition_line(db, requisition_line_id):
    total = Decimal("0")
    for rfq_line in db.query(RfqLine).filter_by(requisition_line_id=requisition_line_id):
        for quote_line in db.query(QuotationLine).filter_by(rfq_line_id=rfq_line.id):
            for award in db.query(RfqAward).filter_by(quotation_line_id=quote_line.id):
                for line in db.query(PurchaseOrderLine).filter_by(award_id=award.id):
                    row = db.get(PurchaseOrder, line.purchase_order_id)
                    if row and row.status in ISSUED:
                        total += _amount(line.quantity)
    return total


def ordering_summary(db, requisition):
    lines = db.query(RequisitionLine).filter_by(requisition_id=requisition.id).all()
    total = sum((_amount(line.quantity) for line in lines), Decimal("0"))
    ordered = sum((issued_for_requisition_line(db, line.id) for line in lines), Decimal("0"))
    if ordered <= 0:
        state = "Not Ordered"
    elif ordered < total:
        state = "Partially Ordered"
    else:
        state = "Fully Ordered"
    note = (
        "Calculated from issued purchase orders. A draft or an approval does not count as ordered. "
        "A goods receipt does not change the ordered quantity. Stock is not posted."
    )
    return state, note


def unordered_line_count(db, project_id):
    count = 0
    rows = (
        db.query(RequisitionLine, PurchaseRequisition)
        .join(PurchaseRequisition, PurchaseRequisition.id == RequisitionLine.requisition_id)
        .filter(PurchaseRequisition.project_id == project_id, PurchaseRequisition.status == "Approved")
        .all()
    )
    for line, _requisition in rows:
        if issued_for_requisition_line(db, line.id) < _amount(line.quantity):
            count += 1
    return count


def _award_context(db, project, award_id):
    award = db.get(RfqAward, award_id)
    if not award:
        raise HTTPException(422, "Choose a line from an awarded quotation")
    rfq = db.get(RequestForQuotation, award.rfq_id)
    if not rfq or rfq.project_id != project.id or rfq.status != "Awarded":
        raise HTTPException(422, "A purchase order uses an awarded quotation on this project")
    quote_line = db.get(QuotationLine, award.quotation_line_id)
    quote = db.get(VendorQuotation, quote_line.quotation_id)
    vendor = db.get(Vendor, quote.vendor_id)
    rfq_line = db.get(RfqLine, quote_line.rfq_line_id)
    source = db.get(RequisitionLine, rfq_line.requisition_line_id)
    item = db.get(ProcurementItem, source.item_id)
    return award, rfq, quote, quote_line, vendor, source, item


def _checked_lines(db, project, incoming, skip_po_id=None):
    chosen = []
    rfq_id = None
    vendor_id = None
    seen = set()
    for item in incoming:
        if item.award_id in seen:
            raise HTTPException(422, "Each awarded line is included once")
        seen.add(item.award_id)
        award, rfq, quote, quote_line, vendor, source, item_row = _award_context(db, project, item.award_id)
        if not vendor.active or vendor.approval_status != "Approved":
            raise HTTPException(422, "The awarded vendor must stay active and approved")
        if rfq_id is None:
            rfq_id = rfq.id
            vendor_id = vendor.id
        elif rfq.id != rfq_id or vendor.id != vendor_id:
            raise HTTPException(422, "One purchase order uses one awarded vendor")
        remaining = _amount(award.quantity) - held_qty(db, award.id, skip_po_id)
        if _amount(item.quantity) > remaining:
            raise HTTPException(422, "Order quantity cannot exceed the awarded quantity still available")
        chosen.append((award, rfq, quote, quote_line, vendor, source, item_row, item.quantity))
    return chosen


def _store_lines(db, row, chosen):
    for index, (award, _rfq, _quote, quote_line, _vendor, _source, _item, quantity) in enumerate(chosen, start=1):
        db.add(
            PurchaseOrderLine(
                purchase_order_id=row.id,
                award_id=award.id,
                position=index,
                quantity=quantity,
                unit_price=quote_line.unit_price,
            )
        )


def sources(db, project):
    groups = {}
    for award in db.query(RfqAward).order_by(RfqAward.id):
        rfq = db.get(RequestForQuotation, award.rfq_id)
        if not rfq or rfq.project_id != project.id or rfq.status != "Awarded":
            continue
        quote_line = db.get(QuotationLine, award.quotation_line_id)
        quote = db.get(VendorQuotation, quote_line.quotation_id)
        vendor = db.get(Vendor, quote.vendor_id)
        remaining = _amount(award.quantity) - held_qty(db, award.id)
        if remaining <= 0:
            continue
        rfq_line = db.get(RfqLine, quote_line.rfq_line_id)
        source = db.get(RequisitionLine, rfq_line.requisition_line_id)
        item = db.get(ProcurementItem, source.item_id)
        from app.domains.identity_projects.models import Company

        key = (rfq.id, vendor.id)
        group = groups.setdefault(
            key,
            {
                "rfq_id": rfq.id,
                "rfq_number": rfq.number,
                "vendor_id": vendor.id,
                "vendor": vendor.code,
                "company": db.get(Company, vendor.company_id).name,
                "requisition_number": db.get(PurchaseRequisition, rfq.requisition_id).number,
                "discipline": db.get(Discipline, rfq.discipline_id).name,
                "currency": quote.currency,
                "lines": [],
            },
        )
        group["lines"].append(
            {
                "award_id": award.id,
                "item_code": item.code,
                "quantity": format(_amount(award.quantity), "f"),
                "remaining": format(remaining, "f"),
                "unit": source.unit,
                "unit_price": format(_amount(quote_line.unit_price), "f"),
            }
        )
    return list(groups.values())


def create_order(db, user, project, data, supersedes=None, reason=""):
    _buyer(db, user, project)
    if db.query(PurchaseOrder).filter_by(project_id=project.id, number_key=_key(data.number)).first():
        raise HTTPException(409, "Purchase order number already exists on this project")
    skip = supersedes.id if supersedes else None
    chosen = _checked_lines(db, project, data.lines, skip)
    _award, rfq, quote, _quote_line, vendor, _source, _item, _quantity = chosen[0]
    row = PurchaseOrder(
        organization_id=user.organization_id,
        project_id=project.id,
        rfq_id=rfq.id,
        vendor_id=vendor.id,
        supersedes_id=supersedes.id if supersedes else None,
        number=data.number.strip(),
        number_key=_key(data.number),
        company_id=rfq.company_id,
        discipline_id=rfq.discipline_id,
        currency=quote.currency,
        terms=data.terms.strip(),
        delivery_location=data.delivery_location.strip(),
        promised_date=data.promised_date,
        amendment_reason=reason.strip(),
        status="Draft",
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    _store_lines(db, row, chosen)
    _stamp(row, user)
    _event(db, user, project.id, "orders", row.id, "created", reason.strip())
    return row


def update_order(db, user, project, row, data):
    _buyer(db, user, project)
    if row.status not in EDITABLE:
        raise HTTPException(409, "An issued purchase order is kept. Change it with an amendment.")
    chosen = _checked_lines(db, project, data.lines, row.id)
    award, rfq, quote, _quote_line, vendor, _source, _item, _quantity = chosen[0]
    if rfq.id != row.rfq_id or vendor.id != row.vendor_id:
        raise HTTPException(422, "Keep this order on the same awarded vendor")
    _bump(
        db,
        PurchaseOrder,
        row.id,
        data.version,
        {
            "terms": data.terms.strip(),
            "delivery_location": data.delivery_location.strip(),
            "promised_date": data.promised_date,
            "currency": quote.currency,
            "modified_by": user.id,
        },
    )
    db.refresh(row)
    for line in db.query(PurchaseOrderLine).filter_by(purchase_order_id=row.id):
        db.delete(line)
    db.flush()
    _store_lines(db, row, chosen)
    _event(db, user, project.id, "orders", row.id, "updated")
    return row


def submit_order(db, user, project, row, version):
    _buyer(db, user, project)
    if row.status != "Draft":
        raise HTTPException(409, "Only a draft can be submitted. A returned order is resubmitted.")
    if not db.query(PurchaseOrderLine).filter_by(purchase_order_id=row.id).first():
        raise HTTPException(422, "Add at least one awarded line")
    policy = _policy(db, project, ORDER, row.company_id, row.discipline_id)
    if not policy:
        raise HTTPException(422, "Save a purchase order reviewer before submitting")
    from .service import _authority

    _authority(db, project, policy)
    _bump(db, PurchaseOrder, row.id, version, {"status": "Pending Approval", "modified_by": user.id})
    db.refresh(row)
    from app.domains.engineering_documents.workflow import submit_record

    submit_record(db, user, project, ORDER, row.id, row.version, policy)
    _event(db, user, project.id, "orders", row.id, "submitted")
    return row


def resubmit_order(db, user, project, row, data):
    _buyer(db, user, project)
    if row.status != "Returned for Correction":
        raise HTTPException(409, "Only a returned purchase order can be resubmitted")
    from app.domains.coordination.models import ReviewInstance

    from .service import _resubmit

    instance = (
        db.query(ReviewInstance)
        .filter_by(project_id=project.id, record_type=ORDER, record_id=row.id, state="Returned")
        .order_by(ReviewInstance.id.desc())
        .first()
    )
    if not instance:
        raise HTTPException(409, "The returned review was not found")
    _resubmit(db, user, project, instance, data.review_version)
    _bump(db, PurchaseOrder, row.id, data.version, {"status": "Pending Approval", "modified_by": user.id})
    db.refresh(row)
    instance.record_version = row.version
    _event(db, user, project.id, "orders", row.id, "resubmitted")
    return row


def issue_order(db, user, project, row, version):
    _buyer(db, user, project)
    if row.status != "Approved":
        raise HTTPException(409, "Issue a purchase order only after it is approved")
    parent = db.get(PurchaseOrder, row.supersedes_id) if row.supersedes_id else None
    if parent and parent.status not in ISSUED:
        raise HTTPException(409, "The original purchase order is no longer the issued revision")
    _bump(
        db,
        PurchaseOrder,
        row.id,
        version,
        {"status": "Issued", "issue_date": date.today(), "modified_by": user.id},
    )
    db.refresh(row)
    if parent:
        parent.status = "Superseded"
        parent.version += 1
        _stamp(parent, user)
        _event(db, user, project.id, "orders", parent.id, "superseded", row.number)
    _event(db, user, project.id, "orders", row.id, "issued")
    return row


def acknowledge_order(db, user, project, row, note, version):
    _buyer(db, user, project)
    if row.status != "Issued":
        raise HTTPException(409, "Record the supplier acknowledgement after the order is issued")
    if not note.strip():
        raise HTTPException(422, "Enter the supplier acknowledgement")
    _bump(
        db,
        PurchaseOrder,
        row.id,
        version,
        {"status": "Acknowledged", "acknowledgment_note": note.strip(), "modified_by": user.id},
    )
    db.refresh(row)
    _event(db, user, project.id, "orders", row.id, "acknowledged", note.strip())
    return row


def cancel_order(db, user, project, row, reason, version):
    _buyer(db, user, project)
    if row.status == "Pending Approval":
        raise HTTPException(409, "This order is in review. The reviewer returns or rejects it first.")
    if row.status not in {"Draft", "Returned for Correction", "Approved", "Issued", "Acknowledged"}:
        raise HTTPException(409, "This purchase order cannot be cancelled")
    from .invoices import open_invoice
    from .receipts import posted_receipt

    if posted_receipt(db, row.id):
        raise HTTPException(409, "Cancel the posted goods receipts before cancelling this order")
    if open_invoice(db, row.id):
        raise HTTPException(409, "Cancel the vendor invoice before cancelling this order")
    if _has_successor(db, row.id):
        raise HTTPException(409, "Finish or cancel the open amendment before cancelling this order")
    if not reason.strip():
        raise HTTPException(422, "Enter the reason for cancelling this purchase order")
    from .service import _stop_review

    _bump(
        db,
        PurchaseOrder,
        row.id,
        version,
        {"status": "Cancelled", "cancellation_reason": reason.strip(), "modified_by": user.id},
    )
    db.refresh(row)
    _stop_review(db, project, ORDER, row.id)
    _event(db, user, project.id, "orders", row.id, "cancelled", reason.strip())
    return row


def amend_order(db, user, project, row, data):
    _buyer(db, user, project)
    if row.status not in {"Issued", "Acknowledged"}:
        raise HTTPException(409, "Amend an issued purchase order before it is received. The issued revision stays on record.")
    from .invoices import open_invoice
    from .receipts import posted_receipt

    if posted_receipt(db, row.id):
        raise HTTPException(409, "Cancel the posted goods receipts before amending this order")
    if open_invoice(db, row.id):
        raise HTTPException(409, "Cancel the vendor invoice before amending this order")
    if _has_successor(db, row.id):
        raise HTTPException(409, "An amendment is already open for this purchase order")
    return create_order(db, user, project, data, supersedes=row, reason=data.reason)


def apply_receipt_status(db, user, row):
    from .receipts import received_qty

    if row.status not in {"Issued", "Acknowledged", "Partially Received", "Received"}:
        return row
    lines = db.query(PurchaseOrderLine).filter_by(purchase_order_id=row.id).all()
    totals = [received_qty(db, line.id) for line in lines]
    if not lines or all(total <= 0 for total in totals):
        status = "Acknowledged" if (row.acknowledgment_note or "").strip() else "Issued"
    elif all(total >= _amount(line.quantity) for line, total in zip(lines, totals)):
        status = "Received"
    else:
        status = "Partially Received"
    if status != row.status:
        row.status = status
        row.version += 1
        _stamp(row, user)
    return row


def close_order(db, user, project, row, reason, version):
    if not holds(db, user, project, "procurement.po.edit") and not holds(db, user, project, "procurement.receipt.edit"):
        raise HTTPException(403, "Closing a purchase order requires buying or stores access")
    if row.status not in {"Partially Received", "Received"}:
        raise HTTPException(409, "Close an order after a goods receipt has been posted")
    if _has_successor(db, row.id):
        raise HTTPException(409, "Finish or cancel the open amendment before closing this order")
    if not reason.strip():
        raise HTTPException(422, "Enter the reason for closing this purchase order")
    _bump(
        db,
        PurchaseOrder,
        row.id,
        version,
        {"status": "Closed", "closure_reason": reason.strip(), "modified_by": user.id},
    )
    db.refresh(row)
    _event(db, user, project.id, "orders", row.id, "closed", reason.strip())
    return row


def step_states(row):
    index = STEPS.index(row.status) if row.status in STEPS else -1
    if row.status == "Returned for Correction":
        index = 0
    acknowledged = STEPS.index("Acknowledged")
    received = STEPS.index("Received")
    steps = []
    for position, name in enumerate(STEPS):
        if row.status in {"Cancelled", "Rejected"}:
            state = "stopped"
        elif row.status in {"Superseded", "Closed"}:
            state = "done"
        elif row.status == "Acknowledged" and position <= acknowledged:
            state = "done"
        elif row.status == "Acknowledged":
            state = "waiting"
        elif row.status == "Received" and position <= received:
            state = "done"
        elif row.status == "Received":
            state = "waiting"
        elif position < index:
            state = "done"
        elif position == index:
            state = "current"
        else:
            state = "waiting"
        steps.append({"name": name, "status": state})
    return steps


def guard_limit(db, user, stage, row):
    reviewer = db.query(PolicyReviewer).filter_by(stage_id=stage.id, user_id=user.id).first()
    if not reviewer or reviewer.approval_limit is None:
        return
    total = Decimal("0")
    for line in db.query(PurchaseOrderLine).filter_by(purchase_order_id=row.id):
        total += _amount(line.quantity) * _amount(line.unit_price)
    if total > Decimal(reviewer.approval_limit):
        raise HTTPException(403, "This purchase order total is above your approval limit in the order currency")


def payload(db, user, project, row):
    show = _commercial(db, user, project)
    vendor = db.get(Vendor, row.vendor_id)
    from app.domains.identity_projects.models import Company

    from .invoices import invoice_rows, open_invoice
    from .receipts import posted_receipt, receipt_rows, received_qty

    lines = []
    for line in (
        db.query(PurchaseOrderLine).filter_by(purchase_order_id=row.id).order_by(PurchaseOrderLine.position)
    ):
        award = db.get(RfqAward, line.award_id)
        quote_line = db.get(QuotationLine, award.quotation_line_id)
        rfq_line = db.get(RfqLine, quote_line.rfq_line_id)
        source = db.get(RequisitionLine, rfq_line.requisition_line_id)
        item = db.get(ProcurementItem, source.item_id)
        received = received_qty(db, line.id)
        remaining = _amount(line.quantity) - received
        if remaining < 0:
            remaining = Decimal("0")
        lines.append(
            {
                "id": line.id,
                "award_id": line.award_id,
                "item_code": item.code,
                "quantity": format(_amount(line.quantity), "f"),
                "received": format(received, "f"),
                "remaining": format(remaining, "f"),
                "unit": source.unit,
                "unit_price": format(_amount(line.unit_price), "f") if show else None,
            }
        )
    parent = db.get(PurchaseOrder, row.supersedes_id) if row.supersedes_id else None
    child = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.supersedes_id == row.id, PurchaseOrder.status.in_(ACTIVE | {"Superseded"}))
        .order_by(PurchaseOrder.id.desc())
        .first()
    )
    steps = step_states(row)
    approvers = _approvers(db, project, row)
    names = ", ".join(person["name"] for person in approvers) or "Not set"
    if row.status == "Draft":
        hint = f"Submit this draft to {names}. The buyer cannot approve their own order."
    elif row.status == "Pending Approval":
        hint = f"Approval is with {names}. Issue is available only after approval."
    elif row.status == "Returned for Correction":
        hint = "Correct the draft and resubmit it. The issued history is not changed."
    elif row.status == "Approved":
        hint = "The buyer can issue this order. Issue makes this revision the commitment."
    elif row.status == "Issued":
        hint = "Record the supplier acknowledgement, then open Goods receipts for the delivery. Stock is not posted."
    elif row.status == "Acknowledged":
        hint = "The supplier has acknowledged this order. Open Goods receipts to record what arrived. Stock is not posted."
    elif row.status == "Partially Received":
        hint = "Some quantity has arrived. Record another receipt for the rest, or close the order if the rest will not arrive. Stock is not posted."
    elif row.status == "Received":
        hint = "The ordered quantity has arrived. Close the order when delivery is finished. Open Invoices to record the supplier bill. Payment stays closed."
    elif row.status == "Closed":
        hint = "This order is closed. Open Invoices to record the supplier bill. Payment stays closed."
    elif row.status == "Superseded":
        hint = f"This revision is kept. The current order is {child.number}." if child else "This revision was superseded."
    elif row.status == "Rejected":
        hint = "This order was rejected. Create another draft from the award if it should be bought."
    else:
        hint = "This order is cancelled. The awarded quantity can be used on another order."
    buyer = holds(db, user, project, "procurement.po.edit")
    return {
        "id": row.id,
        "number": row.number,
        "status": row.status,
        "rfq_id": row.rfq_id,
        "rfq_number": db.get(RequestForQuotation, row.rfq_id).number,
        "vendor": vendor.code,
        "company": db.get(Company, vendor.company_id).name,
        "discipline": db.get(Discipline, row.discipline_id).name,
        "currency": row.currency if show else "",
        "prices_visible": show,
        "terms": row.terms,
        "delivery_location": row.delivery_location,
        "promised_date": row.promised_date.isoformat(),
        "issue_date": row.issue_date.isoformat() if row.issue_date else "",
        "acknowledgment_note": row.acknowledgment_note,
        "amendment_reason": row.amendment_reason,
        "cancellation_reason": row.cancellation_reason,
        "closure_reason": row.closure_reason,
        "supersedes_number": parent.number if parent else "",
        "successor_number": child.number if child and child.id != row.id else "",
        "version": row.version,
        "approvers": approvers,
        "steps": steps,
        "hint": hint,
        "lines": lines,
        "review": _review(db, user, project.id, ORDER, row.id),
        "ordering_note": "A goods receipt records delivery against this order. It does not post stock. A vendor invoice records the supplier bill and does not match or pay it.",
        "receipts": receipt_rows(db, row.id),
        "invoices": invoice_rows(db, row.id),
        "can_edit": buyer and row.status in EDITABLE,
        "can_submit": buyer and row.status == "Draft",
        "can_resubmit": buyer and row.status == "Returned for Correction",
        "can_issue": buyer and row.status == "Approved",
        "can_acknowledge": buyer and row.status == "Issued",
        "can_cancel": buyer and row.status in {"Draft", "Returned for Correction", "Approved", "Issued", "Acknowledged"} and not _has_successor(db, row.id) and not posted_receipt(db, row.id) and not open_invoice(db, row.id),
        "can_amend": buyer and row.status in {"Issued", "Acknowledged"} and not _has_successor(db, row.id) and not posted_receipt(db, row.id) and not open_invoice(db, row.id),
        "can_close": (buyer or holds(db, user, project, "procurement.receipt.edit")) and row.status in {"Partially Received", "Received"} and not _has_successor(db, row.id),
    }


def list_orders(db, user, project, status):
    rows = db.query(PurchaseOrder).filter_by(project_id=project.id).order_by(PurchaseOrder.number)
    if status:
        rows = rows.filter(PurchaseOrder.status == status)
    return [payload(db, user, project, row) for row in rows]
