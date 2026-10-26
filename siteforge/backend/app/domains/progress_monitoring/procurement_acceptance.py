"""Conservative read-only quality disposition reconciliation for posted GRNs."""
from decimal import Decimal
from .milestone_calculation import dec, policy_errors

def allocation_errors(allocations, po_line_ids):
    ids={str(i) for i in po_line_ids}
    if not isinstance(allocations,dict) or set(allocations)!=ids or not ids:
        return ['Approved allocation must contain every eligible PO line exactly once']
    vals=[dec(v) for v in allocations.values()]
    if any(v is None or v<=0 for v in vals) or sum(vals)!=Decimal('100'):
        return ['PO line allocations must be positive finite weights totaling 100%']
    return []

def procurement_accepted_preview(orders, lines, receipts, receipt_lines, inspections, dispositions, weights, allocations):
    errors=policy_errors(weights,('ordered','received','accepted'))
    by_order={o.id:o for o in orders}
    if len(by_order)!=len(orders):errors.append('Duplicate PO IDs')
    by_line={l.id:l for l in lines if l.purchase_order_id in by_order}
    if len(by_line)!=len([l for l in lines if l.purchase_order_id in by_order]):errors.append('Duplicate PO line IDs')
    errors+=allocation_errors(allocations,by_line)
    posted={r.id:r for r in receipts if r.purchase_order_id in by_order and r.status=='Posted'}
    by_receipt_line={}
    received={lid:Decimal(0) for lid in by_line};accepted={lid:Decimal(0) for lid in by_line}
    for rl in receipt_lines:
        if rl.goods_receipt_id not in posted:continue
        if rl.id in by_receipt_line:errors.append('Duplicate receipt lines');continue
        po_line=by_line.get(rl.purchase_order_line_id)
        if po_line is None or po_line.purchase_order_id!=posted[rl.goods_receipt_id].purchase_order_id:
            errors.append('Receipt references unauthorized or unrelated purchase order line');continue
        q=dec(rl.quantity)
        if q is None or q<0:errors.append('Invalid posted receipt quantity');continue
        received[po_line.id]+=q
        by_receipt_line[rl.id]=(rl,po_line,q)
    inspections_by_id={i.id:i for i in inspections if i.goods_receipt_id in posted}
    decisions={rid:[] for rid in by_receipt_line}
    for d in dispositions:
        if d.goods_receipt_line_id not in by_receipt_line:continue
        inspection=inspections_by_id.get(d.inspection_id)
        if inspection is None:
            errors.append('Material disposition has no authorized inspection');continue
        if inspection.goods_receipt_id!=by_receipt_line[d.goods_receipt_line_id][0].goods_receipt_id:
            errors.append('Disposition inspection and GRN mismatch');continue
        if inspection.status!='Approved':
            # Do not count unapproved decisions as acceptance.
            continue
        q=dec(d.quantity)
        if q is None or q<0:errors.append('Invalid inspection disposition quantity');continue
        decisions[d.goods_receipt_line_id].append((d.to_state,q))
    for rid,(rl,po_line,q) in by_receipt_line.items():
        outcomes=decisions[rid]
        # Require one unambiguous final approved disposition partition per GRN line.
        total=sum((n for _,n in outcomes),Decimal(0))
        if total!=q or not outcomes:
            errors.append(f'Receipt line {rid} lacks a complete approved quality disposition');continue
        if any(state not in ('Accepted','Rejected','Quarantined') for state,_ in outcomes):
            errors.append('Unsupported disposition state');continue
        accepted[po_line.id]+=sum((n for state,n in outcomes if state=='Accepted'),Decimal(0))
    result=[]
    for lid,line in by_line.items():
        scope=dec(line.quantity)
        if scope is None or scope<=0:errors.append('PO line quantity missing or invalid');continue
        if received[lid]>scope:errors.append('Receipt quantity exceeds approved PO scope')
        if accepted[lid]>received[lid]:errors.append('Accepted quantity exceeds received quantity')
        order=by_order[line.purchase_order_id]
        if order.status in ('Draft','Cancelled','Rejected') and received[lid]>0:
            errors.append('Receipt posted against ineligible PO')
        result.append({'purchase_order_line_id':lid,'scope':str(scope),'received':str(received[lid]),'accepted':str(accepted[lid]),'ordered':order.status not in ('Draft','Cancelled','Rejected')})
    if not result:errors.append('No eligible PO line scope')
    percent=None
    if not errors:
        score=Decimal(0)
        for r in result:
            fraction_received=dec(r['received'])/dec(r['scope'])
            fraction_accepted=dec(r['accepted'])/dec(r['scope'])
            earned=(dec(weights['ordered']) if r['ordered'] else Decimal(0))+dec(weights['received'])*fraction_received+dec(weights['accepted'])*fraction_accepted
            score+=earned*dec(allocations[str(r['purchase_order_line_id'])])/Decimal('100')
        percent=float(score.quantize(Decimal('0.01')))
    return {'preview_percent':percent,'errors':list(dict.fromkeys(errors)),'rows':result,'measure':'Approved disposition-eligible Procurement milestone progress'}
