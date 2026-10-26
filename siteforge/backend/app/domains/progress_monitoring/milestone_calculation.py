"""Conservative preview of source-linked E/P milestones; no approved earning claim.

Milestone weight policy is supplied explicitly, rather than inferred from readiness.
Full earned progress requires storing and approving a versioned source-linked policy.
"""
from decimal import Decimal, InvalidOperation


def dec(value):
    try:
        x = Decimal(str(value))
        return x if x.is_finite() else None
    except (ValueError, TypeError, InvalidOperation):
        return None


def policy_errors(weights, required):
    if not isinstance(weights, dict) or set(weights) != set(required):
        return ['A complete explicit milestone weight policy is required']
    parsed = [dec(weights[k]) for k in required]
    if any(x is None or x < 0 for x in parsed):
        return ['Weights must be finite nonnegative numbers']
    if sum(parsed) != Decimal('100'):
        return ['Milestone weights must total exactly 100%']
    return []


def engineering_preview(drawings, revisions, weights):
    """Distinct active drawing count, no duplicate credit for revisions."""
    errors = policy_errors(weights, ('prepared', 'released'))
    active = [d for d in drawings if d.record_status == 'Active']
    by_id = {d.id: d for d in active}
    if len(by_id) != len(active): errors.append('Duplicate source drawing IDs')
    revisions_by_drawing = {}
    for r in revisions:
        if r.drawing_id in by_id:
            revisions_by_drawing.setdefault(r.drawing_id, []).append(r)
    rows = []
    for drawing in active:
        r = revisions_by_drawing.get(drawing.id, [])
        released = any(v.release_state == 'Released' and v.released_at is not None for v in r)
        prepared = released or drawing.preparation in ('Prepared', 'Completed')
        # Per-drawing milestones are earned once; never once per revision.
        rows.append({'drawing_id':drawing.id,'prepared':prepared,'released':released})
    if not rows: errors.append('No active planned drawing scope')
    percent = None
    if not errors:
        total = Decimal(len(rows))
        earned = sum((dec(weights['prepared']) if x['prepared'] else Decimal(0)) +
                     (dec(weights['released']) if x['released'] else Decimal(0)) for x in rows)
        percent = float((earned / total).quantize(Decimal('0.01')))
    return {'preview_percent':percent,'policy_status':'UNAPPROVED_PREVIEW',
            'earned_percent':None,'errors':errors,'drawings':rows}


def procurement_preview(orders, lines, receipts, receipt_lines, weights):
    """Quantity-aware PO/delivery preview. Acceptance is never inferred from posted GRNs."""
    errors = policy_errors(weights, ('ordered', 'received', 'accepted'))
    by_order = {o.id:o for o in orders}
    if len(by_order) != len(orders): errors.append('Duplicate source order IDs')
    line_map = {line.id:line for line in lines if line.purchase_order_id in by_order}
    if len(line_map) != len([line for line in lines if line.purchase_order_id in by_order]):
        errors.append('Duplicate source PO line IDs')
    posted = {r.id:r for r in receipts if r.purchase_order_id in by_order and r.status == 'Posted'}
    quantities = {lid:Decimal(0) for lid in line_map}
    seen_grn_lines = set()
    for line in receipt_lines:
        if line.goods_receipt_id not in posted:continue
        if line.id in seen_grn_lines: errors.append('Duplicate receipt-line mapping');continue
        seen_grn_lines.add(line.id)
        po_line = line_map.get(line.purchase_order_line_id)
        if po_line is None:
            errors.append('Posted receipt references an inaccessible or unrelated PO line');continue
        if po_line.purchase_order_id != posted[line.goods_receipt_id].purchase_order_id:
            errors.append('Receipt PO does not match PO line');continue
        q=dec(line.quantity)
        if q is None or q < 0:errors.append('Invalid receipt quantity');continue
        quantities[po_line.id]+=q
    rows=[]
    for line in line_map.values():
        approved=dec(line.quantity)
        if approved is None or approved <= 0:
            errors.append('Missing or invalid approved PO-line quantity');continue
        received=quantities[line.id]
        if received>approved: errors.append('Received quantity exceeds ordered scope')
        order=by_order[line.purchase_order_id]
        ordered=order.status not in ('Draft', 'Cancelled', 'Rejected')
        rows.append({'purchase_order_line_id':line.id,'ordered_quantity':str(approved),
                     'received_quantity':str(received),'ordered':ordered})
    if not rows:errors.append('No valid purchase order lines')
    # Do not combine unlike units/line quantities. Each PO line earns a separately weighted item fraction.
    if len(rows)>1:errors.append('PO-line allocation weights and compatible units are not approved')
    percent=None
    if not errors:
        row=rows[0]
        fraction=dec(row['received_quantity'])/dec(row['ordered_quantity'])
        percent = float(((dec(weights['ordered']) if row['ordered'] else Decimal(0)) +
                        dec(weights['received'])*fraction).quantize(Decimal('0.01')))
    return {'preview_percent':percent,'policy_status':'UNAPPROVED_PREVIEW',
            'earned_percent':None,'errors':list(dict.fromkeys(errors)),
            'rows':rows,'acceptance_status':'NOT_AVAILABLE_IN_RECEIPT_RECORDS'}
