"""Vendor invoices recorded against a purchase order. Matching and payment stay closed."""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select

from app.domains.identity_projects.models import Discipline, User
from app.domains.identity_projects.security import holds

from .models import (
    ProcurementItem,
    PurchaseOrder,
    PurchaseOrderLine,
    QuotationLine,
    RequisitionLine,
    RfqAward,
    RfqLine,
    Vendor,
    VendorInvoice,
    VendorInvoiceLine,
)
from .receipts import received_qty
from .service import _amount, _bump, _commercial, _event, _key


BILLABLE = {"Issued", "Acknowledged", "Partially Received", "Received", "Closed"}
STEPS = ["Draft", "Recorded"]


def _buyer(db, user, project):
    if not holds(db, user, project, "procurement.invoice.edit"):
        raise HTTPException(403, "Recording a vendor invoice requires procurement access")


def _show_prices(db, user, project):
    return _commercial(db, user, project) or holds(db, user, project, "procurement.invoice.edit")


def _qty(value):
    return format(_amount(value), ".3f")


def _money(value):
    return format(_amount(value), ".2f")


def invoiced_qty(db, line_id):
    total = Decimal("0")
    for line in db.query(VendorInvoiceLine).filter_by(purchase_order_line_id=line_id):
        invoice = db.get(VendorInvoice, line.invoice_id)
        if invoice and invoice.status == "Recorded":
            total += _amount(line.quantity)
    return total


def open_invoice(db, purchase_order_id):
    return (
        db.query(VendorInvoice)
        .filter_by(purchase_order_id=purchase_order_id)
        .filter(VendorInvoice.status.in_(("Draft", "Recorded")))
        .first()
        is not None
    )


def invoice_rows(db, purchase_order_id):
    rows = db.query(VendorInvoice).filter_by(purchase_order_id=purchase_order_id).order_by(VendorInvoice.id)
    return [
        {
            "id": row.id,
            "number": row.number,
            "status": row.status,
            "vendor_reference": row.vendor_reference,
        }
        for row in rows
    ]


def recorded_count(db, project_id):
    return db.query(VendorInvoice).filter_by(project_id=project_id, status="Recorded").count()


def _line_context(db, line):
    award = db.get(RfqAward, line.award_id)
    quote_line = db.get(QuotationLine, award.quotation_line_id)
    rfq_line = db.get(RfqLine, quote_line.rfq_line_id)
    source = db.get(RequisitionLine, rfq_line.requisition_line_id)
    item = db.get(ProcurementItem, source.item_id)
    return item, source


def _checked_lines(db, order, data):
    seen = set()
    chosen = []
    for incoming in data.lines:
        if incoming.purchase_order_line_id in seen:
            raise HTTPException(422, "Enter each purchase order line once on this invoice")
        seen.add(incoming.purchase_order_line_id)
        line = db.get(PurchaseOrderLine, incoming.purchase_order_line_id)
        if not line or line.purchase_order_id != order.id:
            raise HTTPException(422, "Each invoice line must belong to this purchase order")
        quantity = _amount(incoming.quantity)
        remaining = _amount(line.quantity) - invoiced_qty(db, line.id)
        if quantity > remaining:
            raise HTTPException(422, "Invoice quantity cannot exceed the quantity still to bill")
        chosen.append((line, quantity, _amount(incoming.billed_unit_price)))
    return chosen


def _order_for_bill(db, project, purchase_order_id):
    order = db.execute(
        select(PurchaseOrder).where(PurchaseOrder.id == purchase_order_id).with_for_update()
    ).scalar_one_or_none()
    if not order or order.project_id != project.id:
        raise HTTPException(404, "Purchase order not found")
    if order.status not in BILLABLE:
        raise HTTPException(409, "Record an invoice against an issued purchase order")
    return order


def _replace_lines(db, row, chosen):
    db.query(VendorInvoiceLine).filter_by(invoice_id=row.id).delete()
    for line, quantity, price in chosen:
        db.add(
            VendorInvoiceLine(
                invoice_id=row.id,
                purchase_order_line_id=line.id,
                quantity=quantity,
                billed_unit_price=price,
            )
        )
    db.flush()


def sources(db, user, project):
    show = _show_prices(db, user, project)
    chosen = []
    orders = (
        db.query(PurchaseOrder)
        .filter_by(project_id=project.id)
        .filter(PurchaseOrder.status.in_(BILLABLE))
        .order_by(PurchaseOrder.number)
    )
    for order in orders:
        vendor = db.get(Vendor, order.vendor_id)
        lines = []
        for line in db.query(PurchaseOrderLine).filter_by(purchase_order_id=order.id).order_by(PurchaseOrderLine.position):
            remaining = _amount(line.quantity) - invoiced_qty(db, line.id)
            if remaining <= 0:
                continue
            item, source = _line_context(db, line)
            lines.append(
                {
                    "purchase_order_line_id": line.id,
                    "item_code": item.code,
                    "ordered": _qty(line.quantity),
                    "received": _qty(received_qty(db, line.id)),
                    "invoiced": _qty(invoiced_qty(db, line.id)),
                    "remaining": _qty(remaining),
                    "unit": source.unit,
                    "order_unit_price": _money(line.unit_price) if show else None,
                }
            )
        if not lines:
            continue
        chosen.append(
            {
                "purchase_order_id": order.id,
                "number": order.number,
                "status": order.status,
                "vendor": vendor.code,
                "discipline": db.get(Discipline, order.discipline_id).name,
                "lines": lines,
            }
        )
    return chosen


def create_invoice(db, user, project, data):
    _buyer(db, user, project)
    order = _order_for_bill(db, project, data.purchase_order_id)
    if db.query(VendorInvoice).filter_by(project_id=project.id, number_key=_key(data.number)).first():
        raise HTTPException(409, "This invoice number is already used on the project")
    chosen = _checked_lines(db, order, data)
    row = VendorInvoice(
        organization_id=user.organization_id,
        project_id=project.id,
        purchase_order_id=order.id,
        number=data.number.strip(),
        number_key=_key(data.number),
        vendor_reference=data.vendor_reference.strip(),
        invoice_date=data.invoice_date,
        note=data.note.strip(),
        status="Draft",
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(row)
    db.flush()
    _replace_lines(db, row, chosen)
    _event(db, user, project.id, "invoices", row.id, "drafted", order.number)
    return row


def update_invoice(db, user, project, row, data):
    _buyer(db, user, project)
    if row.status != "Draft":
        raise HTTPException(409, "Only a draft invoice can be changed")
    order = _order_for_bill(db, project, row.purchase_order_id)
    if data.purchase_order_id != order.id:
        raise HTTPException(422, "Keep this draft on the same purchase order")
    other = db.query(VendorInvoice).filter_by(project_id=project.id, number_key=_key(data.number)).first()
    if other and other.id != row.id:
        raise HTTPException(409, "This invoice number is already used on the project")
    chosen = _checked_lines(db, order, data)
    _bump(
        db,
        VendorInvoice,
        row.id,
        data.version,
        {
            "number": data.number.strip(),
            "number_key": _key(data.number),
            "vendor_reference": data.vendor_reference.strip(),
            "invoice_date": data.invoice_date,
            "note": data.note.strip(),
            "modified_by": user.id,
        },
    )
    db.refresh(row)
    _replace_lines(db, row, chosen)
    _event(db, user, project.id, "invoices", row.id, "updated", order.number)
    return row


def record_invoice(db, user, project, row, version):
    _buyer(db, user, project)
    if row.status != "Draft":
        raise HTTPException(409, "Only a draft invoice can be recorded")
    order = _order_for_bill(db, project, row.purchase_order_id)
    for line in db.query(VendorInvoiceLine).filter_by(invoice_id=row.id):
        order_line = db.get(PurchaseOrderLine, line.purchase_order_line_id)
        remaining = _amount(order_line.quantity) - invoiced_qty(db, order_line.id)
        if _amount(line.quantity) > remaining:
            raise HTTPException(422, "Invoice quantity cannot exceed the quantity still to bill")
    _bump(db, VendorInvoice, row.id, version, {"status": "Recorded", "modified_by": user.id})
    db.refresh(row)
    if order.created_by != user.id:
        buyer = db.get(User, order.created_by)
        if buyer and buyer.active:
            from app.domains.coordination.jobs import notify

            notify(
                db,
                buyer,
                "Vendor invoice recorded",
                f"Invoice {row.number} was recorded against purchase order {order.number}.",
                f"invoice:{row.id}:buyer",
                project_id=project.id,
                link=f"/projects/{project.id}",
            )
    _event(db, user, project.id, "invoices", row.id, "recorded", order.number)
    return row


def cancel_invoice(db, user, project, row, reason, version):
    _buyer(db, user, project)
    if row.status not in {"Draft", "Recorded"}:
        raise HTTPException(409, "Only a draft or recorded invoice can be cancelled")
    if not reason.strip():
        raise HTTPException(422, "Enter the reason for cancelling this invoice")
    _bump(
        db,
        VendorInvoice,
        row.id,
        version,
        {"status": "Cancelled", "cancellation_reason": reason.strip(), "modified_by": user.id},
    )
    db.refresh(row)
    _event(db, user, project.id, "invoices", row.id, "cancelled", reason.strip())
    return row


def step_states(row):
    if row.status == "Cancelled":
        return [{"name": name, "status": "stopped"} for name in STEPS]
    states = []
    for name in STEPS:
        if row.status == "Recorded" or (row.status == "Draft" and name == "Draft"):
            state = "done" if row.status == "Recorded" else "current"
        else:
            state = "waiting"
        states.append({"name": name, "status": state})
    return states


def payload(db, user, project, row):
    order = db.get(PurchaseOrder, row.purchase_order_id)
    vendor = db.get(Vendor, order.vendor_id)
    show = _show_prices(db, user, project)
    buyer = holds(db, user, project, "procurement.invoice.edit")
    lines = []
    for line in db.query(VendorInvoiceLine).filter_by(invoice_id=row.id):
        order_line = db.get(PurchaseOrderLine, line.purchase_order_line_id)
        item, source = _line_context(db, order_line)
        amount = _amount(line.quantity) * _amount(line.billed_unit_price)
        lines.append(
            {
                "id": line.id,
                "purchase_order_line_id": order_line.id,
                "item_code": item.code,
                "quantity": _qty(line.quantity),
                "ordered": _qty(order_line.quantity),
                "received": _qty(received_qty(db, order_line.id)),
                "invoiced": _qty(invoiced_qty(db, order_line.id)),
                "unit": source.unit,
                "order_unit_price": _money(order_line.unit_price) if show else None,
                "billed_unit_price": _money(line.billed_unit_price) if show else None,
                "amount": _money(amount) if show else None,
            }
        )
    if row.status == "Draft":
        hint = "Check the billed quantity and price, then record the bill. Recording does not match the receipt and does not pay."
    elif row.status == "Recorded":
        hint = "This bill is on record for Financials. Matching and payment stay closed."
    else:
        hint = "This bill is cancelled. The quantity can be billed again."
    return {
        "id": row.id,
        "number": row.number,
        "status": row.status,
        "purchase_order_id": order.id,
        "purchase_order_number": order.number,
        "order_status": order.status,
        "vendor": vendor.code,
        "vendor_reference": row.vendor_reference,
        "discipline": db.get(Discipline, order.discipline_id).name,
        "invoice_date": row.invoice_date.isoformat(),
        "note": row.note,
        "cancellation_reason": row.cancellation_reason,
        "version": row.version,
        "lines": lines,
        "steps": step_states(row),
        "prices_visible": show,
        "can_record": buyer and row.status == "Draft",
        "can_cancel": buyer and row.status in {"Draft", "Recorded"},
        "hint": hint,
    }


def list_invoices(db, user, project, status):
    rows = db.query(VendorInvoice).filter_by(project_id=project.id).order_by(VendorInvoice.number)
    if status:
        rows = rows.filter(VendorInvoice.status == status)
    return [payload(db, user, project, row) for row in rows]
