"""How an approved requirement is covered: project stock first, then purchase requisitions.

Remaining to purchase = approved quantity - active stock allocations - quantity on open requisitions.
Issued purchase orders are already counted through their requisition lines, so they are shown, not added again.
Nothing here creates or issues a purchase order.
"""

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select

from app.domains.engineering_documents.models import Drawing, DrawingRevision, MaterialTakeoff, TakeoffLine
from app.domains.identity_projects.security import holds, permitted

from .models import (
    FulfilmentAllocation,
    MaterialRequirement,
    ProcurementItem,
    PurchaseRequisition,
    RequirementLine,
    RequisitionLine,
    StockBalance,
    Warehouse,
)
from .service import _amount, _event, _key, _reserved

ZERO = Decimal("0")


def _fmt(value):
    return format(_amount(value).quantize(Decimal("0.001")), "f")


def allocated(db, line_id):
    total = ZERO
    for row in db.query(FulfilmentAllocation).filter_by(requirement_line_id=line_id, status="Active"):
        total += _amount(row.quantity)
    return total


def _held_elsewhere(db, project_id, warehouse_id, item_id):
    total = ZERO
    for row in db.query(FulfilmentAllocation).filter_by(
        project_id=project_id, warehouse_id=warehouse_id, item_id=item_id, status="Active"
    ):
        total += _amount(row.quantity)
    return total


def _eligible_stock(db, project, line):
    """Stock that is on hand, not reserved by stores and not allocated to another requirement."""
    result = []
    for balance in db.query(StockBalance).filter_by(project_id=project.id, item_id=line.item_id):
        warehouse = db.get(Warehouse, balance.warehouse_id)
        if not warehouse or not warehouse.active:
            continue
        free = _amount(balance.on_hand) - _amount(balance.reserved) - _held_elsewhere(
            db, project.id, balance.warehouse_id, line.item_id
        )
        same_unit = not balance.unit or _key(balance.unit) == _key(line.unit)
        result.append(
            {
                "warehouse_id": warehouse.id,
                "warehouse": warehouse.code,
                "unit": balance.unit or line.unit,
                "free": free if same_unit else ZERO,
                "note": "" if same_unit else f"Held in {balance.unit}. Stock in another unit is not counted.",
            }
        )
    return result


def _issued_orders(db, line_id):
    from .orders import issued_for_requisition_line

    total = ZERO
    for pr_line, requisition in (
        db.query(RequisitionLine, PurchaseRequisition)
        .join(PurchaseRequisition, PurchaseRequisition.id == RequisitionLine.requisition_id)
        .filter(RequisitionLine.requirement_line_id == line_id)
        .all()
    ):
        if requisition.status in {"Cancelled", "Rejected"}:
            continue
        total += issued_for_requisition_line(db, pr_line.id)
    return total


def _trace(db, line):
    revision = db.get(DrawingRevision, line.drawing_revision_id) if line.drawing_revision_id else None
    drawing = db.get(Drawing, revision.drawing_id) if revision else None
    source = db.get(TakeoffLine, line.takeoff_line_id) if line.takeoff_line_id else None
    takeoff = db.get(MaterialTakeoff, source.takeoff_id) if source else None
    return {
        "drawing_id": drawing.id if drawing else None,
        "drawing_number": drawing.number if drawing else "",
        "drawing_revision_id": revision.id if revision else None,
        "drawing_revision_code": revision.code if revision else "",
        "takeoff_id": takeoff.id if takeoff else None,
        "takeoff_number": takeoff.number if takeoff else "",
        "takeoff_line_id": source.id if source else None,
        "takeoff_line_position": source.position if source else None,
        "page": source.page if source else None,
    }


def line_status(db, project, line):
    required = _amount(line.quantity)
    stock = allocated(db, line.id)
    on_requisitions, approved = _reserved(db, line.id)
    orders = _issued_orders(db, line.id)
    remaining = required - stock - on_requisitions
    item = db.get(ProcurementItem, line.item_id)
    eligible = _eligible_stock(db, project, line)
    allocations = [
        {
            "id": row.id,
            "warehouse": db.get(Warehouse, row.warehouse_id).code,
            "quantity": _fmt(row.quantity),
            "unit": row.unit,
            "status": row.status,
            "release_reason": row.release_reason,
        }
        for row in db.query(FulfilmentAllocation).filter_by(requirement_line_id=line.id).order_by(FulfilmentAllocation.id)
    ]
    suggest = []
    need = max(remaining, ZERO)
    for option in eligible:
        if need <= 0:
            break
        take = min(option["free"], need)
        if take > 0:
            suggest.append({"warehouse_id": option["warehouse_id"], "quantity": _fmt(take)})
            need -= take
    return {
        "line_id": line.id,
        "position": line.position,
        "item_id": line.item_id,
        "item_code": item.code,
        "description": item.description,
        "specification": line.specification,
        "unit": line.unit,
        "required": _fmt(required),
        "stock_allocated": _fmt(stock),
        "on_requisitions": _fmt(on_requisitions),
        "approved_requisitions": _fmt(approved),
        "issued_orders": _fmt(orders),
        "remaining_to_purchase": _fmt(max(remaining, ZERO)),
        "eligible_stock": [
            {**option, "free": _fmt(max(option["free"], ZERO))} for option in eligible
        ],
        "suggested_allocations": suggest,
        "allocations": allocations,
        **_trace(db, line),
    }


def check(db, user, project, requirement):
    lines = (
        db.query(RequirementLine)
        .filter_by(requirement_id=requirement.id)
        .order_by(RequirementLine.position)
        .all()
    )
    rows = [line_status(db, project, line) for line in lines]
    blocked = ""
    if requirement.status != "Approved":
        blocked = "Stock and purchase checks start after the requirement is approved."
    elif requirement.impact_state == "Review required":
        blocked = "A drawing change is waiting for the requirement reviewer. Allocation and purchasing wait."
    return {
        "requirement_id": requirement.id,
        "number": requirement.number,
        "status": requirement.status,
        "blocked": blocked,
        "lines": rows,
        "remaining_lines": sum(1 for row in rows if _amount(row["remaining_to_purchase"]) > 0),
        "can_allocate": not blocked and _may_allocate(db, user, project, requirement),
        "can_requisition": not blocked
        and holds(db, user, project, "procurement.requisition.edit")
        and any(_amount(row["remaining_to_purchase"]) > 0 for row in rows),
        "note": "Allocations hold project stock for this requirement so it is not counted twice. They do not move or reserve warehouse stock. Stores still reserves or issues it in Stock. Issued orders are counted through their requisitions.",
    }


def _may_allocate(db, user, project, requirement):
    return holds(db, user, project, "procurement.requisition.edit") or holds(
        db, user, project, "procurement.stock.edit"
    )


def _ready(requirement):
    if requirement.status != "Approved":
        raise HTTPException(409, "Stock and purchase checks start after the requirement is approved")
    if requirement.impact_state == "Review required":
        raise HTTPException(409, "Resolve the drawing impact review first")


def allocate(db, user, project, requirement, data):
    if not _may_allocate(db, user, project, requirement):
        raise HTTPException(403, "Allocating stock needs requisition or stores access")
    _ready(requirement)
    made = []
    for entry in data.lines:
        line = db.get(RequirementLine, entry.line_id)
        if not line or line.requirement_id != requirement.id:
            raise HTTPException(422, "Choose a line from this requirement")
        warehouse = db.get(Warehouse, entry.warehouse_id)
        if not warehouse or warehouse.project_id != project.id or not warehouse.active:
            raise HTTPException(422, "Choose an active warehouse on this project")
        balance = db.execute(
            select(StockBalance)
            .where(
                StockBalance.project_id == project.id,
                StockBalance.warehouse_id == warehouse.id,
                StockBalance.item_id == line.item_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if not balance:
            raise HTTPException(422, f"{warehouse.code} holds none of this item")
        if balance.unit and _key(balance.unit) != _key(line.unit):
            raise HTTPException(422, f"{warehouse.code} holds this item in {balance.unit}, not {line.unit}")
        free = _amount(balance.on_hand) - _amount(balance.reserved) - _held_elsewhere(
            db, project.id, warehouse.id, line.item_id
        )
        reserved, _approved = _reserved(db, line.id)
        remaining = _amount(line.quantity) - allocated(db, line.id) - reserved
        quantity = _amount(entry.quantity)
        if quantity > remaining:
            raise HTTPException(422, f"Line {line.position}: only {_fmt(max(remaining, ZERO))} is still uncovered")
        if quantity > free:
            raise HTTPException(422, f"Line {line.position}: only {_fmt(max(free, ZERO))} is free in {warehouse.code}")
        row = FulfilmentAllocation(
            organization_id=project.organization_id,
            project_id=project.id,
            requirement_line_id=line.id,
            item_id=line.item_id,
            warehouse_id=warehouse.id,
            quantity=quantity,
            unit=line.unit,
            created_by=user.id,
        )
        db.add(row)
        db.flush()
        made.append(row)
        _event(
            db, user, project.id, "requirements", requirement.id, "stock-allocated",
            f"Line {line.position}: {_fmt(quantity)} {line.unit} from {warehouse.code}",
        )
    return made


def release(db, user, project, requirement, allocation_id, reason):
    if not _may_allocate(db, user, project, requirement):
        raise HTTPException(403, "Releasing stock needs requisition or stores access")
    row = db.get(FulfilmentAllocation, allocation_id)
    line = db.get(RequirementLine, row.requirement_line_id) if row else None
    if not row or not line or line.requirement_id != requirement.id:
        raise HTTPException(404, "Allocation not found")
    if row.status != "Active":
        raise HTTPException(409, "This allocation is already released")
    row.status = "Released"
    row.release_reason = reason
    row.released_by = user.id
    row.released_at = datetime.now(timezone.utc)
    _event(
        db, user, project.id, "requirements", requirement.id, "stock-released",
        f"Line {line.position}: {_fmt(row.quantity)} {row.unit}. {reason}",
    )


class _PrLine:
    def __init__(self, line_id, quantity):
        self.requirement_line_id = line_id
        self.quantity = quantity
        self.estimated_price = None


class _PrIn:
    def __init__(self, data, lines):
        self.number = data.number
        self.request_date = data.request_date
        self.required_delivery = data.required_delivery
        self.justification = data.justification
        self.currency = ""
        self.lines = lines
        self.version = None


def requisition_for_uncovered(db, user, project, requirement, data):
    from .service import create_requisition

    permitted(db, user, project, "procurement.requisition.edit", requirement.discipline_id)
    _ready(requirement)
    lines = []
    for line in (
        db.query(RequirementLine)
        .filter_by(requirement_id=requirement.id)
        .order_by(RequirementLine.position)
    ):
        reserved, _approved = _reserved(db, line.id)
        remaining = _amount(line.quantity) - allocated(db, line.id) - reserved
        if remaining > 0:
            lines.append(_PrLine(line.id, remaining))
    if not lines:
        raise HTTPException(409, "Nothing is left to purchase on this requirement")
    return create_requisition(db, user, project, _PrIn(data, lines))


def purchase_needs(db, user, project, show_all=False):
    rows = []
    for requirement in (
        db.query(MaterialRequirement)
        .filter_by(project_id=project.id, status="Approved")
        .order_by(MaterialRequirement.required_date, MaterialRequirement.id)
    ):
        lines = [
            line_status(db, project, line)
            for line in db.query(RequirementLine)
            .filter_by(requirement_id=requirement.id)
            .order_by(RequirementLine.position)
        ]
        open_lines = [line for line in lines if _amount(line["remaining_to_purchase"]) > 0]
        if not open_lines and not show_all:
            continue
        takeoff = db.get(MaterialTakeoff, requirement.takeoff_id) if requirement.takeoff_id else None
        drawing = db.get(Drawing, requirement.drawing_id) if requirement.drawing_id else None
        revision = db.get(DrawingRevision, requirement.drawing_revision_id) if requirement.drawing_revision_id else None
        rows.append(
            {
                "requirement_id": requirement.id,
                "number": requirement.number,
                "source": requirement.source,
                "purpose": requirement.purpose,
                "discipline_id": requirement.discipline_id,
                "required_date": requirement.required_date.isoformat(),
                "priority": requirement.priority,
                "impact_state": requirement.impact_state,
                "drawing_number": drawing.number if drawing else "",
                "drawing_revision_code": revision.code if revision else "",
                "takeoff_number": takeoff.number if takeoff else "",
                "lines": lines if show_all else open_lines,
            }
        )
    return {
        "items": rows,
        "can_requisition": holds(db, user, project, "procurement.requisition.edit"),
        "note": "Approved requirements with quantity not yet covered by stock allocations or purchase requisitions. Each row links to the one requirement record in Requirements & Requests.",
    }
