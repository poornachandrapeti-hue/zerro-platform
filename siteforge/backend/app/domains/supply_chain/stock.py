"""Warehouse stock from an accepted goods receipt.

A receipt alone does not change stock. Stores can put a receipt quantity on hand
only after quality has accepted that quantity.
"""

from decimal import Decimal
import os

from fastapi import HTTPException
from sqlalchemy import select

from app.domains.identity_projects.security import holds

from .models import (
    GoodsReceipt,
    GoodsReceiptLine,
    ProcurementItem,
    PurchaseOrderLine,
    QuotationLine,
    RequisitionLine,
    RfqAward,
    RfqLine,
    StockBalance,
    StockPosting,
    StockPostingLine,
    Warehouse,
)
from .service import _amount, _bump, _event, _key


def _stores(db, user, project):
    if not holds(db, user, project, "procurement.stock.edit"):
        raise HTTPException(403, "Moving stock requires stores access")


def _warehouse(db, project, warehouse_id):
    row = db.get(Warehouse, warehouse_id)
    if not row or row.project_id != project.id or not row.active:
        raise HTTPException(422, "Choose an active warehouse on this project")
    return row


def _number(db, project, number):
    if db.query(StockPosting).filter_by(project_id=project.id, number_key=_key(number)).first():
        raise HTTPException(409, "This stock number is already used on the project")


def accepted_qty(db, receipt_line_id):
    total = Decimal("0")
    for line in db.query(StockPostingLine).filter_by(goods_receipt_line_id=receipt_line_id):
        posting = db.get(StockPosting, line.posting_id)
        if posting and posting.status == "Posted" and posting.kind == "Accept":
            total += _amount(line.quantity)
    return total


def returned_qty(db, issue_line_id):
    total = Decimal("0")
    for line in db.query(StockPostingLine).filter_by(source_line_id=issue_line_id):
        posting = db.get(StockPosting, line.posting_id)
        if posting and posting.status == "Posted" and posting.kind == "Return":
            total += _amount(line.quantity)
    return total


def _issue_lines(db, reservation_line_id):
    out = []
    for line in db.query(StockPostingLine).filter_by(source_line_id=reservation_line_id):
        posting = db.get(StockPosting, line.posting_id)
        if posting and posting.status == "Posted" and posting.kind == "Issue":
            out.append(line)
    return out


def drawn_qty(db, reservation_line_id):
    return sum((_amount(line.quantity) for line in _issue_lines(db, reservation_line_id)), Decimal("0"))


def package_stock(db, project_id, package_id, item_id):
    """Still reserved for the package, and issued from its reservations net of returns."""
    reserved = Decimal("0")
    issued = Decimal("0")
    lines = (
        db.query(StockPostingLine)
        .join(StockPosting, StockPosting.id == StockPostingLine.posting_id)
        .filter(
            StockPosting.project_id == project_id,
            StockPosting.package_id == package_id,
            StockPosting.kind == "Reservation",
            StockPosting.status == "Posted",
            StockPostingLine.item_id == item_id,
        )
    )
    for line in lines:
        drawn = _issue_lines(db, line.id)
        reserved += _amount(line.quantity) - sum((_amount(row.quantity) for row in drawn), Decimal("0"))
        for row in drawn:
            issued += _amount(row.quantity) - returned_qty(db, row.id)
    return reserved, issued


def _open_package(db, project, package_id):
    if package_id is None:
        return None
    from app.domains.construction.models import WorkPackage

    package = db.get(WorkPackage, package_id)
    if not package or package.project_id != project.id or package.status in {"Cancelled", "Handed Over"}:
        raise HTTPException(422, "Choose an open work package on this project")
    return package


def _receipt_item(db, receipt_line):
    order_line = db.get(PurchaseOrderLine, receipt_line.purchase_order_line_id)
    award = db.get(RfqAward, order_line.award_id)
    quote_line = db.get(QuotationLine, award.quotation_line_id)
    rfq_line = db.get(RfqLine, quote_line.rfq_line_id)
    source = db.get(RequisitionLine, rfq_line.requisition_line_id)
    item = db.get(ProcurementItem, source.item_id)
    return item, source.unit


def _lock_balance(db, user, project, warehouse_id, item_id, unit):
    row = db.execute(
        select(StockBalance)
        .where(
            StockBalance.project_id == project.id,
            StockBalance.warehouse_id == warehouse_id,
            StockBalance.item_id == item_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if not row:
        row = StockBalance(
            organization_id=user.organization_id,
            project_id=project.id,
            warehouse_id=warehouse_id,
            item_id=item_id,
            unit=unit,
            on_hand=Decimal("0"),
            reserved=Decimal("0"),
        )
        db.add(row)
        db.flush()
    if row.unit and unit and row.unit != unit:
        raise HTTPException(422, "This warehouse already holds this item in another unit")
    if unit and not row.unit:
        row.unit = unit
    return row


def _available(row):
    return _amount(row.on_hand) - _amount(row.reserved)


def item_stock(db, project_id, item_id):
    on_hand = Decimal("0")
    reserved = Decimal("0")
    for row in db.query(StockBalance).filter_by(project_id=project_id, item_id=item_id):
        on_hand += _amount(row.on_hand)
        reserved += _amount(row.reserved)
    return on_hand, reserved


def _qty(value):
    return format(_amount(value), ".3f")


def _movement_qty(db, warehouse_id, item_id, kind):
    total = Decimal("0")
    postings = db.query(StockPosting).filter_by(warehouse_id=warehouse_id, kind=kind, status="Posted")
    for posting in postings:
        for line in db.query(StockPostingLine).filter_by(posting_id=posting.id, item_id=item_id):
            total += _amount(line.quantity)
    return total


def balances(db, project):
    rows = []
    for row in (
        db.query(StockBalance).filter_by(project_id=project.id).order_by(StockBalance.warehouse_id, StockBalance.item_id)
    ):
        if _amount(row.on_hand) == 0 and _amount(row.reserved) == 0 and _movement_qty(db, row.warehouse_id, row.item_id, "Issue") == 0:
            continue
        item = db.get(ProcurementItem, row.item_id)
        warehouse = db.get(Warehouse, row.warehouse_id)
        issued = _movement_qty(db, row.warehouse_id, row.item_id, "Issue")
        returned = _movement_qty(db, row.warehouse_id, row.item_id, "Return")
        rows.append(
            {
                "warehouse_id": row.warehouse_id,
                "warehouse": warehouse.code,
                "item_id": row.item_id,
                "item_code": item.code,
                "unit": row.unit,
                "on_hand": _qty(row.on_hand),
                "reserved": _qty(row.reserved),
                "available": _qty(_available(row)),
                "issued": _qty(issued),
                "returned": _qty(returned),
            }
        )
    return rows


def on_hand_count(db, project_id):
    return (
        db.query(StockBalance)
        .filter(StockBalance.project_id == project_id, StockBalance.on_hand > 0)
        .count()
    )


def _lot_writer_cutover_on():
    return os.getenv("STORES_LOT_WRITER_CUTOVER", "false").lower() == "true"


def _accept_line_status(db, line):
    """Physical remaining vs Quality/Stores handoff authorization for Accept."""
    from app.domains.quality.material import quality_accepted

    remaining = _amount(line.quantity) - accepted_qty(db, line.id)
    quality = _amount(quality_accepted(db, line.id))
    stores = _qa_accept_limit(db, line.id)
    allowed = max(Decimal("0"), min(quality, stores) - accepted_qty(db, line.id))
    handoff_done = _qa_case(db, line.id) is not None and stores > 0
    if remaining <= 0:
        blocker = "Already fully accepted into stock."
    elif quality <= 0:
        blocker = "Quality → Material: approve accepted quantity first."
    elif not handoff_done:
        blocker = "Quality → Material: click Handoff to Stores on this line."
    elif allowed <= 0:
        blocker = "All QA-authorized quantity is already on hand."
    else:
        blocker = None
    return {
        "remaining": remaining,
        "quality_accepted": quality,
        "stores_accepted": stores,
        "accept_allowed": allowed,
        "handoff_done": handoff_done,
        "blocker": blocker,
    }


def _lot_accept_sources(db, project):
    """Lots with remaining QA-accepted quantity available for atomic acceptance."""
    from sqlalchemy import func
    from app.domains.stores_inventory.models import (
        StoresReceiptLot,
        StoresInspectionCase,
        StoresLotQAAttribution,
        StoresPostingLotAllocation,
    )

    rows = []
    lots = (
        db.query(StoresReceiptLot)
        .filter_by(project_id=project.id, organization_id=project.organization_id)
        .order_by(StoresReceiptLot.id.desc())
        .limit(500)
        .all()
    )
    for lot in lots:
        case = db.query(StoresInspectionCase).filter_by(goods_receipt_line_id=lot.goods_receipt_line_id).first()
        if case is None or case.status not in ("Pending Inspection", "Disposition Recorded"):
            continue
        qa_approved = _amount(
            db.query(func.coalesce(func.sum(StoresLotQAAttribution.quantity), 0))
            .filter_by(
                receipt_lot_id=lot.id,
                inspection_case_id=case.id,
                disposition="Accepted",
                case_version_at_entry=case.version,
            )
            .scalar()
        )
        already = _amount(
            db.query(func.coalesce(func.sum(StoresPostingLotAllocation.quantity), 0))
            .join(StockPostingLine, StoresPostingLotAllocation.stock_posting_line_id == StockPostingLine.id)
            .join(StockPosting, StockPostingLine.posting_id == StockPosting.id)
            .filter(
                StoresPostingLotAllocation.receipt_lot_id == lot.id,
                StockPosting.kind == "Accept",
                StockPosting.status == "Posted",
            )
            .scalar()
        )
        available = min(_amount(lot.quantity), qa_approved) - already
        if available <= 0:
            continue
        line = db.get(GoodsReceiptLine, lot.goods_receipt_line_id)
        item, unit = _receipt_item(db, line) if line else (None, "")
        if item is None:
            continue
        rows.append(
            {
                "lot_id": lot.id,
                "lot_code": lot.lot_code,
                "goods_receipt_line_id": lot.goods_receipt_line_id,
                "warehouse_id": lot.warehouse_id,
                "item_id": item.id,
                "item_code": item.code,
                "unit": unit,
                "accept_allowed": format(available, "f"),
                "batch_number": lot.batch_number,
                "heat_number": lot.heat_number,
            }
        )
    return rows


def accept_sources(db, project):
    from app.domains.quality.material import quality_accepted  # noqa: F401 — kept for clarity/tests

    chosen = []
    waiting_on_quality = 0
    waiting_on_handoff = 0
    ready_to_accept = 0
    receipts = db.query(GoodsReceipt).filter_by(project_id=project.id, status="Posted").order_by(GoodsReceipt.number)
    for receipt in receipts:
        lines = []
        for line in db.query(GoodsReceiptLine).filter_by(goods_receipt_id=receipt.id):
            status = _accept_line_status(db, line)
            if status["remaining"] <= 0:
                continue
            item, unit = _receipt_item(db, line)
            if status["blocker"] and "Quality → Material: approve" in (status["blocker"] or ""):
                waiting_on_quality += 1
            elif status["blocker"] and "Handoff to Stores" in (status["blocker"] or ""):
                waiting_on_handoff += 1
            elif status["accept_allowed"] > 0:
                ready_to_accept += 1
            lines.append(
                {
                    "goods_receipt_line_id": line.id,
                    "item_id": item.id,
                    "item_code": item.code,
                    "quantity": format(_amount(line.quantity), "f"),
                    "remaining": format(status["remaining"], "f"),
                    "quality_accepted": format(status["quality_accepted"], "f"),
                    "stores_accepted": format(status["stores_accepted"], "f"),
                    "accept_allowed": format(status["accept_allowed"], "f"),
                    "handoff_done": status["handoff_done"],
                    "blocker": status["blocker"],
                    "unit": unit,
                }
            )
        if lines:
            chosen.append(
                {
                    "goods_receipt_id": receipt.id,
                    "number": receipt.number,
                    "warehouse_id": receipt.warehouse_id,
                    "lines": lines,
                }
            )
    return {
        "lot_writer_cutover": _lot_writer_cutover_on(),
        "waiting_on_quality": waiting_on_quality,
        "waiting_on_handoff": waiting_on_handoff,
        "ready_to_accept": ready_to_accept,
        "sources": chosen,
        "lot_sources": _lot_accept_sources(db, project),
        "note": (
            "Lot writers are active; use Lot accept."
            if _lot_writer_cutover_on()
            else "Legacy Accept is active. Lot accept stays standby until STORES_LOT_WRITER_CUTOVER=true."
        ),
    }


def issue_sources(db, project):
    chosen = []
    for posting in (
        db.query(StockPosting).filter_by(project_id=project.id, kind="Issue", status="Posted").order_by(StockPosting.number)
    ):
        warehouse = db.get(Warehouse, posting.warehouse_id)
        lines = []
        for line in db.query(StockPostingLine).filter_by(posting_id=posting.id):
            remaining = _amount(line.quantity) - returned_qty(db, line.id)
            if remaining <= 0:
                continue
            item = db.get(ProcurementItem, line.item_id)
            lines.append(
                {
                    "source_line_id": line.id,
                    "item_id": item.id,
                    "item_code": item.code,
                    "quantity": format(_amount(line.quantity), "f"),
                    "remaining": format(remaining, "f"),
                    "unit": line.unit,
                }
            )
        if lines:
            chosen.append(
                {
                    "issue_id": posting.id,
                    "number": posting.number,
                    "warehouse_id": posting.warehouse_id,
                    "warehouse": warehouse.code,
                    "recipient": posting.recipient,
                    "lines": lines,
                }
            )
    return chosen


def _save(db, user, project, kind, number, warehouse_id, reason, recipient, goods_receipt_id, source_posting_id):
    _number(db, project, number)
    row = StockPosting(
        organization_id=user.organization_id,
        project_id=project.id,
        warehouse_id=warehouse_id,
        goods_receipt_id=goods_receipt_id,
        source_posting_id=source_posting_id,
        number=number.strip(),
        number_key=_key(number),
        kind=kind,
        status="Posted",
        reason=reason.strip(),
        recipient=recipient.strip(),
        created_by=user.id,
        modified_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def _qa_case(db, receipt_line_id):
    from app.domains.stores_inventory.models import StoresInspectionCase
    return db.query(StoresInspectionCase).filter_by(goods_receipt_line_id=receipt_line_id).first()


def _qa_accept_limit(db, receipt_line_id):
    """Approved QA quantity, net of revocations; legacy acceptance is never proof."""
    case = _qa_case(db, receipt_line_id)
    return _amount(case.accepted_qty) if case is not None else Decimal("0")


def _require_qa_clear_item(db, project, warehouse_id, item_id):
    """Conservative item-level interlock until physical balances become lot-scoped.

    Legacy balances merge receipt lots. If any source lot is unknown, held,
    revoked, or partly inspected, there is no safe way to pick the approved lot.
    Consequently stop issue/reservation rather than guess which stock is eligible.
    """
    accepted_lines = (
        db.query(StockPostingLine)
        .join(StockPosting, StockPosting.id == StockPostingLine.posting_id)
        .filter(StockPosting.project_id == project.id,
                StockPosting.warehouse_id == warehouse_id,
                StockPosting.status == "Posted", StockPosting.kind == "Accept",
                StockPostingLine.item_id == item_id)
        .all()
    )
    if not accepted_lines:
        raise HTTPException(409, "QA-certified stock source is unavailable for this item")
    for line in accepted_lines:
        case = _qa_case(db, line.goods_receipt_line_id) if line.goods_receipt_line_id else None
        if case is None:
            raise HTTPException(409, "Legacy stock needs QA reconciliation before allocation or issue")
        if (_amount(case.pending_qty) > 0 or _amount(case.rejected_qty) > 0
                or _amount(case.quarantined_qty) > 0 or case.status == "Quality Revoked"):
            raise HTTPException(409, "QA hold or partial inspection blocks this unsegregated item balance")
        if accepted_qty(db, line.goods_receipt_line_id) > _amount(case.accepted_qty):
            raise HTTPException(409, "Stock acceptance exceeds current QA-authorized quantity")


def _require_legacy_writer_enabled():
    """Prevent mixed item-level and lot-level writers after explicit cutover."""
    if os.getenv("STORES_LOT_WRITER_CUTOVER", "false").lower() == "true":
        raise HTTPException(503, "Legacy stock posting is disabled during lot-writer cutover")


def accept_receipt(db, user, project, data):
    _require_legacy_writer_enabled()
    _stores(db, user, project)
    _warehouse(db, project, data.warehouse_id)
    receipt = db.get(GoodsReceipt, data.goods_receipt_id)
    if not receipt or receipt.project_id != project.id or receipt.status != "Posted":
        raise HTTPException(409, "Accept a posted goods receipt")
    seen = set()
    chosen = []
    for incoming in data.lines:
        if incoming.goods_receipt_line_id in seen:
            raise HTTPException(422, "Enter each receipt line once")
        seen.add(incoming.goods_receipt_line_id)
        line = db.get(GoodsReceiptLine, incoming.goods_receipt_line_id)
        if not line or line.goods_receipt_id != receipt.id:
            raise HTTPException(422, "Each line must belong to this goods receipt")
        remaining = _amount(line.quantity) - accepted_qty(db, line.id)
        quantity = _amount(incoming.quantity)
        if quantity > remaining:
            raise HTTPException(422, "Accepted quantity cannot exceed the receipt quantity still waiting")
        from app.domains.quality.material import quality_accepted

        quality = _amount(quality_accepted(db, line.id))
        stores = _qa_accept_limit(db, line.id)
        allowed = min(quality, stores) - accepted_qty(db, line.id)
        if quantity > allowed:
            if quality <= 0:
                raise HTTPException(
                    422,
                    "Quality has not accepted this quantity yet. Complete Quality → Material approve, then Handoff to Stores.",
                )
            if stores <= 0:
                raise HTTPException(
                    422,
                    "Handoff to Stores is required before stock accept (Quality → Material → Handoff to Stores).",
                )
            raise HTTPException(422, "Stores can put on hand only the quantity quality has accepted")
        item, unit = _receipt_item(db, line)
        chosen.append((line, item, unit, quantity))
    posting = _save(db, user, project, "Accept", data.number, data.warehouse_id, f"Accepted from receipt {receipt.number}", "", receipt.id, None)
    for line, item, unit, quantity in sorted(chosen, key=lambda item: item[1].id):
        balance = _lock_balance(db, user, project, data.warehouse_id, item.id, unit)
        balance.on_hand = _amount(balance.on_hand) + quantity
        balance.version += 1
        db.add(
            StockPostingLine(
                posting_id=posting.id,
                item_id=item.id,
                goods_receipt_line_id=line.id,
                quantity=quantity,
                unit=unit,
            )
        )
    _event(db, user, project.id, "stock", posting.id, "accepted", receipt.number)
    return posting


def reserve_stock(db, user, project, data):
    _require_legacy_writer_enabled()
    _stores(db, user, project)
    _warehouse(db, project, data.warehouse_id)
    package = _open_package(db, project, data.package_id)
    seen = set()
    chosen = []
    for incoming in data.lines:
        if incoming.item_id in seen:
            raise HTTPException(422, "Enter each item once")
        seen.add(incoming.item_id)
        item = db.get(ProcurementItem, incoming.item_id)
        if not item or item.organization_id != user.organization_id:
            raise HTTPException(422, "Choose an item on this stock balance")
        chosen.append((item, _amount(incoming.quantity)))
    posting = _save(db, user, project, "Reservation", data.number, data.warehouse_id, data.reason, "", None, None)
    posting.package_id = package.id if package else None
    for item, quantity in sorted(chosen, key=lambda item: item[0].id):
        balance = _lock_balance(db, user, project, data.warehouse_id, item.id, "")
        _require_qa_clear_item(db, project, data.warehouse_id, item.id)
        if quantity > _available(balance):
            raise HTTPException(422, "Reserved quantity cannot exceed the available quantity")
        balance.reserved = _amount(balance.reserved) + quantity
        balance.version += 1
        db.add(StockPostingLine(posting_id=posting.id, item_id=item.id, quantity=quantity, unit=balance.unit))
    _event(db, user, project.id, "stock", posting.id, "reserved", data.reason.strip())
    return posting


def issue_stock(db, user, project, data):
    _require_legacy_writer_enabled()
    _stores(db, user, project)
    _warehouse(db, project, data.warehouse_id)
    reservation = None
    if data.reservation_id is not None:
        reservation = db.get(StockPosting, data.reservation_id)
        if (
            not reservation
            or reservation.project_id != project.id
            or reservation.kind != "Reservation"
            or reservation.status != "Posted"
            or reservation.warehouse_id != data.warehouse_id
        ):
            raise HTTPException(422, "Choose a posted reservation in this warehouse")
    if data.package_id is not None and (not reservation or reservation.package_id != data.package_id):
        raise HTTPException(422, "An issue for a work package draws from that package's reservation")
    seen = set()
    chosen = []
    for incoming in data.lines:
        if incoming.item_id in seen:
            raise HTTPException(422, "Enter each item once")
        seen.add(incoming.item_id)
        item = db.get(ProcurementItem, incoming.item_id)
        if not item or item.organization_id != user.organization_id:
            raise HTTPException(422, "Choose an item on this stock balance")
        from app.domains.quality.findings import issue_blocked

        if issue_blocked(db, project.id, item.id):
            raise HTTPException(409, "A quality hold blocks issue of this item.")
        chosen.append((item, _amount(incoming.quantity)))
    posting = _save(
        db,
        user,
        project,
        "Issue",
        data.number,
        data.warehouse_id,
        data.reason,
        data.recipient,
        None,
        reservation.id if reservation else None,
    )
    posting.package_id = reservation.package_id if reservation else None
    for item, quantity in sorted(chosen, key=lambda item: item[0].id):
        balance = _lock_balance(db, user, project, data.warehouse_id, item.id, "")
        _require_qa_clear_item(db, project, data.warehouse_id, item.id)
        source = None
        if reservation:
            source = db.query(StockPostingLine).filter_by(posting_id=reservation.id, item_id=item.id).first()
            if not source:
                raise HTTPException(422, f"{item.code} is not on reservation {reservation.number}")
            if quantity > _amount(source.quantity) - drawn_qty(db, source.id):
                raise HTTPException(422, "Issued quantity cannot exceed what is still reserved")
            balance.reserved = _amount(balance.reserved) - quantity
        elif quantity > _available(balance):
            raise HTTPException(422, "Issued quantity cannot exceed the available quantity")
        balance.on_hand = _amount(balance.on_hand) - quantity
        balance.version += 1
        db.add(
            StockPostingLine(
                posting_id=posting.id,
                item_id=item.id,
                source_line_id=source.id if source else None,
                quantity=quantity,
                unit=balance.unit,
            )
        )
    _event(db, user, project.id, "stock", posting.id, "issued", data.recipient.strip())
    return posting


def return_stock(db, user, project, data):
    _require_legacy_writer_enabled()
    _stores(db, user, project)
    issue = db.get(StockPosting, data.issue_id)
    if not issue or issue.project_id != project.id or issue.kind != "Issue" or issue.status != "Posted":
        raise HTTPException(409, "Return stock against a posted issue")
    seen = set()
    chosen = []
    for incoming in data.lines:
        if incoming.source_line_id in seen:
            raise HTTPException(422, "Enter each issued line once")
        seen.add(incoming.source_line_id)
        line = db.get(StockPostingLine, incoming.source_line_id)
        if not line or line.posting_id != issue.id:
            raise HTTPException(422, "Each return line must belong to this issue")
        remaining = _amount(line.quantity) - returned_qty(db, line.id)
        quantity = _amount(incoming.quantity)
        if quantity > remaining:
            raise HTTPException(422, "Returned quantity cannot exceed the quantity still out")
        chosen.append((line, quantity))
    posting = _save(db, user, project, "Return", data.number, issue.warehouse_id, data.reason, issue.recipient, None, issue.id)
    for line, quantity in sorted(chosen, key=lambda item: item[0].item_id):
        balance = _lock_balance(db, user, project, issue.warehouse_id, line.item_id, line.unit)
        balance.on_hand = _amount(balance.on_hand) + quantity
        balance.version += 1
        db.add(
            StockPostingLine(
                posting_id=posting.id,
                item_id=line.item_id,
                source_line_id=line.id,
                quantity=quantity,
                unit=line.unit,
            )
        )
    _event(db, user, project.id, "stock", posting.id, "returned", data.reason.strip())
    return posting


def cancel_posting(db, user, project, row, reason, version):
    _require_legacy_writer_enabled()
    _stores(db, user, project)
    if row.status != "Posted":
        raise HTTPException(409, "Only a posted stock movement can be cancelled")
    if not reason.strip():
        raise HTTPException(422, "Enter the reason for cancelling this stock movement")
    lines = db.query(StockPostingLine).filter_by(posting_id=row.id).all()
    if row.kind == "Issue" and any(returned_qty(db, line.id) > 0 for line in lines):
        raise HTTPException(409, "Cancel the return before cancelling this issue")
    if row.kind == "Reservation" and any(drawn_qty(db, line.id) > 0 for line in lines):
        raise HTTPException(409, "Cancel the issues drawn from this reservation first")
    for line in sorted(lines, key=lambda item: item.item_id):
        balance = _lock_balance(db, user, project, row.warehouse_id, line.item_id, line.unit)
        quantity = _amount(line.quantity)
        if row.kind == "Accept":
            if quantity > _available(balance):
                raise HTTPException(409, "This quantity is reserved or issued. Release it before cancelling the acceptance")
            balance.on_hand = _amount(balance.on_hand) - quantity
        elif row.kind == "Reservation":
            balance.reserved = _amount(balance.reserved) - quantity
        elif row.kind == "Issue":
            balance.on_hand = _amount(balance.on_hand) + quantity
            if line.source_line_id:
                balance.reserved = _amount(balance.reserved) + quantity
        elif row.kind == "Return":
            if quantity > _available(balance):
                raise HTTPException(409, "This returned quantity is no longer available to reverse")
            balance.on_hand = _amount(balance.on_hand) - quantity
        if _amount(balance.on_hand) < 0 or _amount(balance.reserved) < 0 or _amount(balance.reserved) > _amount(balance.on_hand):
            raise HTTPException(409, "This cancellation would make the stock balance invalid")
        balance.version += 1
    _bump(
        db,
        StockPosting,
        row.id,
        version,
        {"status": "Cancelled", "cancellation_reason": reason.strip(), "modified_by": user.id},
    )
    db.refresh(row)
    _event(db, user, project.id, "stock", row.id, "cancelled", reason.strip())
    return row


def payload(db, project, row):
    warehouse = db.get(Warehouse, row.warehouse_id)
    lines = []
    for line in db.query(StockPostingLine).filter_by(posting_id=row.id):
        item = db.get(ProcurementItem, line.item_id)
        lines.append(
            {
                "id": line.id,
                "item_id": line.item_id,
                "item_code": item.code,
                "quantity": format(_amount(line.quantity), "f"),
                "unit": line.unit,
                "goods_receipt_line_id": line.goods_receipt_line_id,
                "source_line_id": line.source_line_id,
                "remaining": format(_amount(line.quantity) - drawn_qty(db, line.id), "f")
                if row.kind == "Reservation"
                else None,
            }
        )
    from app.domains.construction.models import WorkPackage

    source = db.get(StockPosting, row.source_posting_id) if row.source_posting_id else None
    receipt = db.get(GoodsReceipt, row.goods_receipt_id) if row.goods_receipt_id else None
    package = db.get(WorkPackage, row.package_id) if row.package_id else None
    return {
        "id": row.id,
        "number": row.number,
        "kind": row.kind,
        "status": row.status,
        "warehouse_id": row.warehouse_id,
        "warehouse": warehouse.code,
        "package_id": row.package_id,
        "package_code": package.code if package else "",
        "reason": row.reason,
        "recipient": row.recipient,
        "goods_receipt_number": receipt.number if receipt else "",
        "source_number": source.number if source else "",
        "cancellation_reason": row.cancellation_reason,
        "version": row.version,
        "lines": lines,
        "can_cancel": row.status == "Posted",
    }


def list_postings(db, project, kind):
    rows = db.query(StockPosting).filter_by(project_id=project.id).order_by(StockPosting.id.desc())
    if kind:
        rows = rows.filter(StockPosting.kind == kind)
    return [payload(db, project, row) for row in rows]
