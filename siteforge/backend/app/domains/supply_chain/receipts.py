"""Goods receipts against an issued purchase order. A receipt does not post stock or record a bill."""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select

from app.domains.identity_projects.models import Discipline, User
from app.domains.identity_projects.security import holds

from .models import (
    GoodsReceipt,
    GoodsReceiptLine,
    ProcurementItem,
    PurchaseOrder,
    PurchaseOrderLine,
    RequisitionLine,
    RfqLine,
    QuotationLine,
    RfqAward,
    Vendor,
    Warehouse,
)
from .service import _amount, _bump, _event, _key, _stamp


OPEN = {"Issued", "Acknowledged", "Partially Received"}


def _receiver(db, user, project):
    if not holds(db, user, project, "procurement.receipt.edit"):
        raise HTTPException(403, "Recording a goods receipt requires stores access")


def received_qty(db, line_id):
    total = Decimal("0")
    for line in db.query(GoodsReceiptLine).filter_by(purchase_order_line_id=line_id):
        receipt = db.get(GoodsReceipt, line.goods_receipt_id)
        if receipt and receipt.status == "Posted":
            total += _amount(line.quantity)
    return total


def posted_receipt(db, purchase_order_id):
    return (
        db.query(GoodsReceipt).filter_by(purchase_order_id=purchase_order_id, status="Posted").first()
        is not None
    )


def receipt_rows(db, purchase_order_id):
    rows = db.query(GoodsReceipt).filter_by(purchase_order_id=purchase_order_id).order_by(GoodsReceipt.id)
    return [
        {
            "id": row.id,
            "number": row.number,
            "status": row.status,
            "receipt_date": row.receipt_date.isoformat(),
        }
        for row in rows
    ]


def sources(db, project):
    chosen = []
    orders = (
        db.query(PurchaseOrder)
        .filter_by(project_id=project.id)
        .filter(PurchaseOrder.status.in_(OPEN))
        .order_by(PurchaseOrder.number)
    )
    for order in orders:
        vendor = db.get(Vendor, order.vendor_id)
        lines = []
        for line in db.query(PurchaseOrderLine).filter_by(purchase_order_id=order.id).order_by(PurchaseOrderLine.position):
            remaining = _amount(line.quantity) - received_qty(db, line.id)
            if remaining <= 0:
                continue
            award = db.get(RfqAward, line.award_id)
            quote_line = db.get(QuotationLine, award.quotation_line_id)
            rfq_line = db.get(RfqLine, quote_line.rfq_line_id)
            source = db.get(RequisitionLine, rfq_line.requisition_line_id)
            item = db.get(ProcurementItem, source.item_id)
            lines.append(
                {
                    "purchase_order_line_id": line.id,
                    "item_code": item.code,
                    "ordered": format(_amount(line.quantity), "f"),
                    "remaining": format(remaining, "f"),
                    "unit": source.unit,
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


def _checked_lines(db, order, data):
    seen = set()
    chosen = []
    for incoming in data.lines:
        if incoming.purchase_order_line_id in seen:
            raise HTTPException(422, "Enter each purchase order line once on this receipt")
        seen.add(incoming.purchase_order_line_id)
        line = db.get(PurchaseOrderLine, incoming.purchase_order_line_id)
        if not line or line.purchase_order_id != order.id:
            raise HTTPException(422, "Each receipt line must belong to this purchase order")
        remaining = _amount(line.quantity) - received_qty(db, line.id)
        quantity = _amount(incoming.quantity)
        if quantity > remaining:
            raise HTTPException(422, "Receipt quantity cannot exceed the quantity still to receive")
        chosen.append((line, quantity))
    return chosen


def create_receipt(db, user, project, data):
    _receiver(db, user, project)
    order = db.execute(
        select(PurchaseOrder).where(PurchaseOrder.id == data.purchase_order_id).with_for_update()
    ).scalar_one_or_none()
    if not order or order.project_id != project.id:
        raise HTTPException(404, "Purchase order not found")
    if order.status not in OPEN:
        raise HTTPException(409, "Record a receipt against an issued, acknowledged, or partially received order")
    if db.query(GoodsReceipt).filter_by(project_id=project.id, number_key=_key(data.number)).first():
        raise HTTPException(409, "This receipt number is already used on the project")
    warehouse_id = data.warehouse_id or None
    if warehouse_id:
        warehouse = db.get(Warehouse, warehouse_id)
        if not warehouse or warehouse.project_id != project.id or not warehouse.active:
            raise HTTPException(422, "Choose an active warehouse on this project")
    chosen = _checked_lines(db, order, data)
    row = GoodsReceipt(
        organization_id=user.organization_id,
        project_id=project.id,
        purchase_order_id=order.id,
        warehouse_id=warehouse_id,
        number=data.number.strip(),
        number_key=_key(data.number),
        receipt_date=data.receipt_date,
        delivery_note=data.delivery_note.strip(),
        status="Posted",
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(row)
    db.flush()
    for line, quantity in chosen:
        db.add(
            GoodsReceiptLine(
                goods_receipt_id=row.id,
                purchase_order_line_id=line.id,
                quantity=quantity,
            )
        )
    db.flush()
    from .orders import apply_receipt_status

    apply_receipt_status(db, user, order)
    if order.created_by != user.id:
        buyer = db.get(User, order.created_by)
        if buyer and buyer.active:
            from app.domains.coordination.jobs import notify

            notify(
                db,
                buyer,
                "Goods received",
                f"Receipt {row.number} was posted against purchase order {order.number}.",
                f"receipt:{row.id}:buyer",
                project_id=project.id,
                link=f"/projects/{project.id}",
            )
    _event(db, user, project.id, "receipts", row.id, "posted", order.number)
    return row


def cancel_receipt(db, user, project, row, reason, version):
    _receiver(db, user, project)
    if row.status != "Posted":
        raise HTTPException(409, "Only a posted receipt can be cancelled")
    order = db.execute(
        select(PurchaseOrder).where(PurchaseOrder.id == row.purchase_order_id).with_for_update()
    ).scalar_one()
    if order.status == "Closed":
        raise HTTPException(409, "This order is closed. The receipt stays on record.")
    from .stock import accepted_qty

    if any(accepted_qty(db, line.id) > 0 for line in db.query(GoodsReceiptLine).filter_by(goods_receipt_id=row.id)):
        raise HTTPException(409, "Cancel the warehouse acceptance before cancelling this receipt")
    if not reason.strip():
        raise HTTPException(422, "Enter the reason for cancelling this receipt")
    _bump(
        db,
        GoodsReceipt,
        row.id,
        version,
        {"status": "Cancelled", "cancellation_reason": reason.strip(), "modified_by": user.id},
    )
    db.refresh(row)
    from .orders import apply_receipt_status

    apply_receipt_status(db, user, order)
    _event(db, user, project.id, "receipts", row.id, "cancelled", reason.strip())
    return row


def payload(db, user, project, row):
    order = db.get(PurchaseOrder, row.purchase_order_id)
    vendor = db.get(Vendor, order.vendor_id)
    warehouse = db.get(Warehouse, row.warehouse_id) if row.warehouse_id else None
    from .orders import step_states

    lines = []
    for line in db.query(GoodsReceiptLine).filter_by(goods_receipt_id=row.id):
        order_line = db.get(PurchaseOrderLine, line.purchase_order_line_id)
        award = db.get(RfqAward, order_line.award_id)
        quote_line = db.get(QuotationLine, award.quotation_line_id)
        rfq_line = db.get(RfqLine, quote_line.rfq_line_id)
        source = db.get(RequisitionLine, rfq_line.requisition_line_id)
        item = db.get(ProcurementItem, source.item_id)
        from .stock import accepted_qty

        accepted = accepted_qty(db, line.id)
        lines.append(
            {
                "id": line.id,
                "purchase_order_line_id": order_line.id,
                "item_code": item.code,
                "quantity": format(_amount(line.quantity), "f"),
                "accepted": format(accepted, "f"),
                "unit": source.unit,
            }
        )
    receiver = holds(db, user, project, "procurement.receipt.edit")
    return {
        "id": row.id,
        "number": row.number,
        "status": row.status,
        "purchase_order_id": order.id,
        "purchase_order_number": order.number,
        "order_status": order.status,
        "vendor": vendor.code,
        "discipline": db.get(Discipline, order.discipline_id).name,
        "receipt_date": row.receipt_date.isoformat(),
        "delivery_note": row.delivery_note,
        "warehouse": warehouse.code if warehouse else "",
        "cancellation_reason": row.cancellation_reason,
        "version": row.version,
        "lines": lines,
        "order_steps": step_states(order),
        "can_cancel": receiver and row.status == "Posted" and order.status != "Closed" and all(line["accepted"] == "0.000" for line in lines),
        "hint": (
            "This receipt records the delivery. Quality accepts the quantity before stores can put it on hand. The receipt itself does not change stock."
            if row.status == "Posted"
            else "This receipt is cancelled. The quantity can be received again."
        ),
    }


def list_receipts(db, user, project, status):
    rows = db.query(GoodsReceipt).filter_by(project_id=project.id).order_by(GoodsReceipt.number)
    if status:
        rows = rows.filter(GoodsReceipt.status == status)
    return [payload(db, user, project, row) for row in rows]
