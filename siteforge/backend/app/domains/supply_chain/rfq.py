"""RFQ, vendor quotations, and manual award. Purchase orders stay closed."""

from datetime import date
from decimal import Decimal

from fastapi import HTTPException

from app.domains.coordination.models import PolicyReviewer, PolicyStage
from app.domains.identity_projects.models import Company, Discipline, User
from app.domains.identity_projects.security import holds

from .models import (
    ProcurementItem,
    PurchaseRequisition,
    QuotationLine,
    RequestForQuotation,
    RequisitionLine,
    RfqAward,
    RfqInvite,
    RfqLine,
    Vendor,
    VendorQuotation,
)
from .service import (
    REQUIREMENT,
    _amount,
    _bump,
    _commercial,
    _event,
    _key,
    _name,
    _policy,
    _stamp,
)

STEPS = [
    "Draft",
    "Awaiting quotations",
    "Technical review",
    "Commercial comparison",
    "Awarded",
]
OPEN = set(STEPS[:4])
TECHNICAL = {"Compliant", "Deviation accepted", "Not compliant"}
SELECTABLE = {"Compliant", "Deviation accepted"}


def _buyer(db, user, project):
    if not holds(db, user, project, "procurement.rfq.edit"):
        raise HTTPException(403, "Creating and issuing an RFQ requires procurement buying access")


def _technical_people(db, project, row):
    policy = _policy(db, project, REQUIREMENT, row.company_id, row.discipline_id)
    people = []
    if not policy:
        return people
    for stage in db.query(PolicyStage).filter_by(policy_id=policy.id):
        for reviewer in db.query(PolicyReviewer).filter_by(stage_id=stage.id):
            person = db.get(User, reviewer.user_id)
            if person and person.id not in {item["id"] for item in people}:
                people.append({"id": person.id, "name": person.name})
    return people


def _is_technical(db, user, project, row):
    return user.id in {person["id"] for person in _technical_people(db, project, row)}


def _held(db, requisition_line_id, skip_rfq_id=None):
    total = Decimal("0")
    for line in db.query(RfqLine).filter_by(requisition_line_id=requisition_line_id):
        rfq = db.get(RequestForQuotation, line.rfq_id)
        if not rfq or rfq.status == "Cancelled" or rfq.id == skip_rfq_id:
            continue
        if rfq.status == "Awarded":
            awarded = Decimal("0")
            for quote_line in db.query(QuotationLine).filter_by(rfq_line_id=line.id):
                for award in db.query(RfqAward).filter_by(quotation_line_id=quote_line.id):
                    awarded += _amount(award.quantity)
            total += awarded
        elif rfq.status in OPEN:
            total += _amount(line.quantity)
    return total


def sources(db, project):
    rows = []
    requisitions = (
        db.query(PurchaseRequisition)
        .filter_by(project_id=project.id, status="Approved")
        .order_by(PurchaseRequisition.number)
        .all()
    )
    for requisition in requisitions:
        lines = []
        for line in (
            db.query(RequisitionLine)
            .filter_by(requisition_id=requisition.id)
            .order_by(RequisitionLine.position)
        ):
            remaining = _amount(line.quantity) - _held(db, line.id)
            if remaining <= 0:
                continue
            item = db.get(ProcurementItem, line.item_id)
            lines.append(
                {
                    "id": line.id,
                    "item_code": item.code,
                    "specification": line.specification,
                    "quantity": format(_amount(line.quantity), "f"),
                    "remaining": format(remaining, "f"),
                    "unit": line.unit,
                }
            )
        if lines:
            rows.append(
                {
                    "id": requisition.id,
                    "number": requisition.number,
                    "company_id": requisition.company_id,
                    "discipline_id": requisition.discipline_id,
                    "discipline": db.get(Discipline, requisition.discipline_id).name,
                    "lines": lines,
                }
            )
    return rows


def create_rfq(db, user, project, data):
    _buyer(db, user, project)
    requisition = db.get(PurchaseRequisition, data.requisition_id)
    if not requisition or requisition.project_id != project.id or requisition.status != "Approved":
        raise HTTPException(422, "Choose an approved purchase requisition")
    if db.query(RequestForQuotation).filter_by(project_id=project.id, number_key=_key(data.number)).first():
        raise HTTPException(409, "RFQ number already exists on this project")
    vendors = []
    for vendor_id in dict.fromkeys(data.vendor_ids):
        vendor = db.get(Vendor, vendor_id)
        if (
            not vendor
            or vendor.organization_id != project.organization_id
            or not vendor.active
            or vendor.approval_status != "Approved"
        ):
            raise HTTPException(422, "Invite only an active approved vendor")
        vendors.append(vendor)
    seen = set()
    chosen = []
    for item in data.lines:
        if item.requisition_line_id in seen:
            raise HTTPException(422, "Each requisition line is included once")
        seen.add(item.requisition_line_id)
        line = db.get(RequisitionLine, item.requisition_line_id)
        if not line or line.requisition_id != requisition.id:
            raise HTTPException(422, "Choose lines from the selected requisition")
        remaining = _amount(line.quantity) - _held(db, line.id)
        if _amount(item.quantity) > remaining:
            raise HTTPException(422, "RFQ quantity cannot exceed the approved requisition quantity still available")
        chosen.append((line, item.quantity))
    row = RequestForQuotation(
        organization_id=user.organization_id,
        project_id=project.id,
        requisition_id=requisition.id,
        number=data.number.strip(),
        number_key=_key(data.number),
        company_id=requisition.company_id,
        discipline_id=requisition.discipline_id,
        due_date=data.due_date,
        delivery_location=data.delivery_location.strip(),
        technical_requirements=data.technical_requirements.strip(),
        commercial_requirements=data.commercial_requirements.strip(),
        status="Draft",
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    for index, (line, quantity) in enumerate(chosen, start=1):
        db.add(
            RfqLine(
                rfq_id=row.id,
                requisition_line_id=line.id,
                position=index,
                quantity=quantity,
            )
        )
    for vendor in vendors:
        db.add(RfqInvite(rfq_id=row.id, vendor_id=vendor.id))
    _stamp(row, user)
    _event(db, user, project.id, "rfqs", row.id, "created")
    return row


def issue_rfq(db, user, project, row, version):
    _buyer(db, user, project)
    if row.status != "Draft":
        raise HTTPException(409, "Only a draft RFQ can be issued")
    if not db.query(RfqLine).filter_by(rfq_id=row.id).first():
        raise HTTPException(422, "Add at least one requisition line")
    if not db.query(RfqInvite).filter_by(rfq_id=row.id).first():
        raise HTTPException(422, "Invite at least one approved vendor")
    _bump(db, RequestForQuotation, row.id, version, {"status": "Awaiting quotations", "modified_by": user.id})
    db.refresh(row)
    row.issue_date = date.today()
    _event(db, user, project.id, "rfqs", row.id, "issued")
    return row


def cancel_rfq(db, user, project, row, reason, version):
    _buyer(db, user, project)
    if row.status in {"Awarded", "Cancelled"}:
        raise HTTPException(409, "An awarded RFQ stays recorded. Cancel is available before the award.")
    if not reason.strip():
        raise HTTPException(422, "Enter the reason for cancelling this RFQ")
    _bump(
        db,
        RequestForQuotation,
        row.id,
        version,
        {"status": "Cancelled", "cancellation_reason": reason.strip(), "modified_by": user.id},
    )
    db.refresh(row)
    _event(db, user, project.id, "rfqs", row.id, "cancelled", reason.strip())


def add_quotation(db, user, project, row, data):
    if not _commercial(db, user, project):
        raise HTTPException(403, "Quotation prices require commercial access")
    if row.status != "Awaiting quotations":
        raise HTTPException(409, "Record quotations while the RFQ is awaiting quotations")
    invite = db.query(RfqInvite).filter_by(rfq_id=row.id, vendor_id=data.vendor_id).first()
    if not invite:
        raise HTTPException(422, "This vendor was not invited on the RFQ")
    if db.query(VendorQuotation).filter_by(rfq_id=row.id, vendor_id=data.vendor_id).first():
        raise HTTPException(409, "This vendor already has a quotation on the RFQ")
    if data.validity_date < data.quotation_date:
        raise HTTPException(422, "Validity date cannot be before the quotation date")
    quote = VendorQuotation(
        rfq_id=row.id,
        vendor_id=data.vendor_id,
        reference=data.reference.strip(),
        quotation_date=data.quotation_date,
        validity_date=data.validity_date,
        currency=data.currency.strip().upper(),
        freight=data.freight,
        payment_terms=data.payment_terms.strip(),
        technical_deviations=data.technical_deviations.strip(),
        created_by=user.id,
    )
    db.add(quote)
    db.flush()
    seen = set()
    for item in data.lines:
        if item.rfq_line_id in seen:
            raise HTTPException(422, "Each RFQ line is quoted once on this quotation")
        seen.add(item.rfq_line_id)
        line = db.get(RfqLine, item.rfq_line_id)
        if not line or line.rfq_id != row.id:
            raise HTTPException(422, "Choose a line from this RFQ")
        if _amount(item.quantity) > _amount(line.quantity):
            raise HTTPException(422, "Quoted quantity cannot exceed the RFQ line quantity")
        db.add(
            QuotationLine(
                quotation_id=quote.id,
                rfq_line_id=line.id,
                specification=item.specification.strip(),
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount=item.discount,
                tax=item.tax,
                lead_time_days=item.lead_time_days,
            )
        )
    _bump(db, RequestForQuotation, row.id, data.version, {"modified_by": user.id})
    _event(db, user, project.id, "rfqs", row.id, "quoted", data.reference.strip())
    return quote


def notify_technical(db, project, row):
    from app.domains.coordination.jobs import notify

    for person in _technical_people(db, project, row):
        reviewer = db.get(User, person["id"])
        if not reviewer or not reviewer.active:
            continue
        notify(
            db,
            reviewer,
            "Your technical review is required",
            f"RFQ {row.number} has a quotation waiting for your technical decision.",
            f"rfq:{row.id}:technical:{reviewer.id}",
            project_id=project.id,
            link=f"/projects/{project.id}",
        )


def start_technical(db, user, project, row, version):
    _buyer(db, user, project)
    if row.status != "Awaiting quotations":
        raise HTTPException(409, "Technical review starts from an issued RFQ that is awaiting quotations")
    if not db.query(VendorQuotation).filter_by(rfq_id=row.id).first():
        raise HTTPException(422, "Record at least one quotation before technical review")
    if not _technical_people(db, project, row):
        raise HTTPException(422, "Save a requirement reviewer before technical review of quotations")
    _bump(db, RequestForQuotation, row.id, version, {"status": "Technical review", "modified_by": user.id})
    db.refresh(row)
    _event(db, user, project.id, "rfqs", row.id, "technical")
    notify_technical(db, project, row)


def decide_technical(db, user, project, row, data):
    if row.status != "Technical review":
        raise HTTPException(409, "Technical decisions are recorded during technical review")
    if not _is_technical(db, user, project, row):
        names = ", ".join(person["name"] for person in _technical_people(db, project, row)) or "the saved requirement reviewer"
        raise HTTPException(403, f"Technical review is with {names}")
    if data.decision not in TECHNICAL:
        raise HTTPException(422, "Technical decision must be Compliant, Deviation accepted, or Not compliant")
    if data.decision != "Compliant" and not data.reason.strip():
        raise HTTPException(422, "Enter the reason for a deviation or a non-compliant quotation")
    quote = db.get(VendorQuotation, data.quotation_id)
    if not quote or quote.rfq_id != row.id:
        raise HTTPException(404, "Quotation not found")
    _bump(db, RequestForQuotation, row.id, data.version, {"modified_by": user.id})
    db.refresh(row)
    quote.technical_decision = data.decision
    quote.technical_reason = data.reason.strip()
    quote.technical_by = user.id
    db.flush()
    pending = (
        db.query(VendorQuotation)
        .filter_by(rfq_id=row.id)
        .filter(VendorQuotation.technical_decision == "")
        .count()
    )
    if pending == 0:
        row.status = "Commercial comparison"
        _event(db, user, project.id, "rfqs", row.id, "commercial")
    _event(db, user, project.id, "rfqs", row.id, "technical-decision", data.decision)


def save_commercial(db, user, project, row, data):
    if not _commercial(db, user, project):
        raise HTTPException(403, "Commercial comparison requires commercial access")
    if row.status != "Commercial comparison":
        raise HTTPException(409, "Commercial comparison opens after every quotation has a technical decision")
    _bump(
        db,
        RequestForQuotation,
        row.id,
        data.version,
        {
            "comparison_currency": data.comparison_currency.strip().upper(),
            "rate_date": data.rate_date,
            "modified_by": user.id,
        },
    )
    db.refresh(row)
    for note in data.notes:
        quote = db.get(VendorQuotation, note.quotation_id)
        if not quote or quote.rfq_id != row.id:
            raise HTTPException(422, "Choose a quotation on this RFQ")
        if quote.technical_decision == "Not compliant":
            continue
        if quote.currency != row.comparison_currency and note.conversion_rate is None:
            raise HTTPException(422, "Enter a conversion rate when the quotation currency differs")
        quote.commercial_note = note.commercial_note.strip()
        quote.conversion_rate = note.conversion_rate
        quote.commercial_by = user.id
    _event(db, user, project.id, "rfqs", row.id, "compared")


def award(db, user, project, row, data):
    if not _commercial(db, user, project):
        raise HTTPException(403, "The award requires commercial access. The lowest quotation is not selected automatically.")
    if row.status != "Commercial comparison":
        raise HTTPException(409, "Record the award during commercial comparison")
    if not row.comparison_currency or not row.rate_date:
        raise HTTPException(422, "Record the commercial comparison before the award")
    _bump(
        db,
        RequestForQuotation,
        row.id,
        data.version,
        {"status": "Awarded", "award_reason": data.reason.strip(), "modified_by": user.id},
    )
    db.refresh(row)
    totals = {}
    for item in data.lines:
        quote_line = db.get(QuotationLine, item.quotation_line_id)
        quote = db.get(VendorQuotation, quote_line.quotation_id) if quote_line else None
        rfq_line = db.get(RfqLine, quote_line.rfq_line_id) if quote_line else None
        if not quote or quote.rfq_id != row.id or not rfq_line or rfq_line.rfq_id != row.id:
            raise HTTPException(422, "Award lines from this RFQ")
        if quote.technical_decision not in SELECTABLE:
            raise HTTPException(422, "A non-compliant quotation cannot be awarded")
        if not quote.commercial_note.strip():
            raise HTTPException(422, "Record a commercial note on every quotation that can be awarded")
        if quote.currency != row.comparison_currency and quote.conversion_rate is None:
            raise HTTPException(422, "Enter a conversion rate when the quotation currency differs")
        totals[rfq_line.id] = totals.get(rfq_line.id, Decimal("0")) + _amount(item.quantity)
        db.add(
            RfqAward(
                rfq_id=row.id,
                quotation_line_id=quote_line.id,
                quantity=item.quantity,
                awarded_by=user.id,
            )
        )
    for line_id, quantity in totals.items():
        line = db.get(RfqLine, line_id)
        if quantity > _amount(line.quantity):
            raise HTTPException(422, "Awarded quantity cannot exceed the RFQ line quantity")
    _event(db, user, project.id, "rfqs", row.id, "awarded", data.reason.strip())


def _money(show, value):
    if not show or value is None:
        return None
    return format(_amount(value), "f")


def _line_total(line):
    return _amount(line.quantity) * _amount(line.unit_price) - _amount(line.discount) + _amount(line.tax)


def payload(db, user, project, row):
    show = _commercial(db, user, project)
    technical = _technical_people(db, project, row)
    lines = []
    for line in db.query(RfqLine).filter_by(rfq_id=row.id).order_by(RfqLine.position):
        source = db.get(RequisitionLine, line.requisition_line_id)
        item = db.get(ProcurementItem, source.item_id)
        lines.append(
            {
                "id": line.id,
                "requisition_line_id": line.requisition_line_id,
                "item_code": item.code,
                "specification": source.specification,
                "quantity": format(_amount(line.quantity), "f"),
                "unit": source.unit,
            }
        )
    invites = []
    for invite in db.query(RfqInvite).filter_by(rfq_id=row.id):
        vendor = db.get(Vendor, invite.vendor_id)
        invites.append(
            {
                "vendor_id": vendor.id,
                "code": vendor.code,
                "company": db.get(Company, vendor.company_id).name,
            }
        )
    quotes = []
    comparable = []
    for quote in db.query(VendorQuotation).filter_by(rfq_id=row.id).order_by(VendorQuotation.id):
        vendor = db.get(Vendor, quote.vendor_id)
        quote_lines = []
        original = _amount(quote.freight)
        for line in db.query(QuotationLine).filter_by(quotation_id=quote.id):
            original += _line_total(line)
            source = db.get(RfqLine, line.rfq_line_id)
            item_line = db.get(RequisitionLine, source.requisition_line_id)
            quote_lines.append(
                {
                    "id": line.id,
                    "rfq_line_id": line.rfq_line_id,
                    "item_code": db.get(ProcurementItem, item_line.item_id).code,
                    "specification": line.specification,
                    "quantity": format(_amount(line.quantity), "f"),
                    "unit_price": _money(show, line.unit_price),
                    "discount": _money(show, line.discount),
                    "tax": _money(show, line.tax),
                    "lead_time_days": line.lead_time_days,
                }
            )
        rate = _amount(quote.conversion_rate) if quote.conversion_rate is not None else None
        compared = original * rate if rate is not None else original
        comparable.append(compared)
        quotes.append(
            {
                "id": quote.id,
                "vendor_id": quote.vendor_id,
                "vendor": vendor.code,
                "company": db.get(Company, vendor.company_id).name,
                "reference": quote.reference,
                "quotation_date": quote.quotation_date.isoformat(),
                "validity_date": quote.validity_date.isoformat(),
                "currency": quote.currency if show else "",
                "freight": _money(show, quote.freight),
                "payment_terms": quote.payment_terms if show else "",
                "technical_deviations": quote.technical_deviations,
                "conversion_rate": format(rate, "f") if show and rate is not None else None,
                "original_total": _money(show, original),
                "compared_total": _money(show, compared) if show else None,
                "technical_decision": quote.technical_decision,
                "technical_reason": quote.technical_reason,
                "technical_by_name": _name(db, quote.technical_by),
                "commercial_note": quote.commercial_note if show else "",
                "commercial_by_name": _name(db, quote.commercial_by) if show else "",
                "lines": quote_lines,
            }
        )
    if show and comparable:
        lowest = min(comparable)
        for quote, amount in zip(quotes, comparable):
            quote["lowest_quoted"] = amount == lowest and row.comparison_currency != ""
    else:
        for quote in quotes:
            quote["lowest_quoted"] = False
    awards = []
    for award_row in db.query(RfqAward).filter_by(rfq_id=row.id):
        quote_line = db.get(QuotationLine, award_row.quotation_line_id)
        quote = db.get(VendorQuotation, quote_line.quotation_id)
        vendor = db.get(Vendor, quote.vendor_id)
        awards.append(
            {
                "quotation_line_id": quote_line.id,
                "vendor": vendor.code,
                "quantity": format(_amount(award_row.quantity), "f"),
                "awarded_by_name": _name(db, award_row.awarded_by),
            }
        )
    index = STEPS.index(row.status) if row.status in STEPS else -1
    steps = []
    for position, name in enumerate(STEPS):
        if row.status == "Cancelled":
            state = "stopped"
        elif row.status == "Awarded" or position < index:
            state = "done"
        elif position == index:
            state = "current"
        else:
            state = "waiting"
        steps.append({"name": name, "status": state})
    names = ", ".join(person["name"] for person in technical) or "Not set"
    if row.status == "Draft":
        hint = "Issue the RFQ after the approved lines and approved vendors are saved."
    elif row.status == "Awaiting quotations":
        hint = "Record each invited vendor's quotation, then start technical review. Prices need commercial access."
    elif row.status == "Technical review":
        hint = f"Technical review is with {names}. Mark each quotation Compliant, Deviation accepted, or Not compliant."
    elif row.status == "Commercial comparison":
        hint = "Compare the quotations and record the award yourself. The lowest price is not selected automatically."
    elif row.status == "Awarded":
        hint = "The award is saved. Create a purchase order from it. The award itself does not issue an order."
    else:
        hint = "This RFQ is cancelled. Its quantity can be used on another RFQ."
    return {
        "id": row.id,
        "number": row.number,
        "requisition_id": row.requisition_id,
        "requisition_number": db.get(PurchaseRequisition, row.requisition_id).number,
        "discipline_id": row.discipline_id,
        "discipline": db.get(Discipline, row.discipline_id).name,
        "issue_date": row.issue_date.isoformat() if row.issue_date else "",
        "due_date": row.due_date.isoformat(),
        "delivery_location": row.delivery_location,
        "technical_requirements": row.technical_requirements,
        "commercial_requirements": row.commercial_requirements if show else "",
        "status": row.status,
        "comparison_currency": row.comparison_currency if show else "",
        "rate_date": row.rate_date.isoformat() if show and row.rate_date else "",
        "award_reason": row.award_reason,
        "cancellation_reason": row.cancellation_reason,
        "version": row.version,
        "prices_visible": show,
        "technical_reviewers": technical,
        "steps": steps,
        "hint": hint,
        "lines": lines,
        "vendors": invites,
        "quotations": quotes,
        "awards": awards,
        "ordering_note": "An award does not create an order. Open Purchase orders and create one from this award.",
        "can_issue": holds(db, user, project, "procurement.rfq.edit") and row.status == "Draft",
        "can_quote": show and row.status == "Awaiting quotations",
        "can_start_technical": holds(db, user, project, "procurement.rfq.edit") and row.status == "Awaiting quotations",
        "can_technical": _is_technical(db, user, project, row) and row.status == "Technical review",
        "can_commercial": show and row.status == "Commercial comparison",
        "can_award": show and row.status == "Commercial comparison",
        "can_cancel": holds(db, user, project, "procurement.rfq.edit") and row.status not in {"Awarded", "Cancelled"},
    }


def list_rfqs(db, user, project, status):
    query = db.query(RequestForQuotation).filter_by(project_id=project.id)
    if status:
        query = query.filter(RequestForQuotation.status == status)
    return [payload(db, user, project, row) for row in query.order_by(RequestForQuotation.id.desc()).all()]
