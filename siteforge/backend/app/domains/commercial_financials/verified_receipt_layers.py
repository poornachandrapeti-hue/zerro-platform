"""Read-only consolidation of Finance approved receipt invoice allocations and landed charges.

Not an accounting posting, nor a stock available-layer calculation.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation


def _positive(value, label):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f'Invalid {label}') from exc
    if not result.is_finite() or result <= 0:
        raise ValueError(f'Invalid {label}')
    return result


def consolidate_receipt_layers(*, receipts, invoice_allocations, landed_allocations):
    """Inputs are scoped and pre-authorized by the caller; fail closed on gaps.

    receipts: {id,quantity,currency}; invoices: {receipt_line_id,quantity,unit_cost,
    currency,allocation_id,independently_approved}; landed: {receipt_line_id,
    amount,currency,batch_id,independently_approved}.
    """
    lines = {}
    for r in receipts:
        rid = int(r['id'])
        if rid in lines:
            raise ValueError('Duplicate receipt line')
        currency = r['currency']
        if not isinstance(currency,str) or len(currency)!=3 or not currency.isalpha() or currency!=currency.upper():
            raise ValueError('Invalid receipt currency')
        lines[rid] = {'receipt_line_id':rid,'quantity':_positive(r['quantity'],'receipt quantity'),
                      'currency':currency,'invoice_quantity':Decimal(0),'invoice_value':Decimal(0),
                      'landed_value':Decimal(0),'invoice_allocation_ids':[], 'landed_batch_ids':[]}
    if not lines:
        raise ValueError('No receipts provided')
    seen_invoice=set()
    for a in invoice_allocations:
        rid=int(a['receipt_line_id']); lid=int(a['allocation_id'])
        if rid not in lines or (rid,lid) in seen_invoice:
            raise ValueError('Unknown receipt or duplicate invoice allocation')
        seen_invoice.add((rid,lid)); item=lines[rid]
        if a.get('independently_approved') is not True or a['currency']!=item['currency']:
            raise ValueError('Unapproved or mismatched invoice allocation')
        q=_positive(a['quantity'],'invoice allocation quantity'); u=_positive(a['unit_cost'],'invoice unit cost')
        item['invoice_quantity']+=q; item['invoice_value']+=q*u; item['invoice_allocation_ids'].append(lid)
    seen_landed=set()
    for a in landed_allocations:
        rid=int(a['receipt_line_id']); bid=int(a['batch_id'])
        if rid not in lines or (rid,bid) in seen_landed:
            raise ValueError('Unknown receipt or duplicate landed allocation')
        seen_landed.add((rid,bid)); item=lines[rid]
        if a.get('independently_approved') is not True or a['currency']!=item['currency']:
            raise ValueError('Unapproved or mismatched landed charge')
        try: amount=Decimal(str(a['amount']))
        except (InvalidOperation,ValueError,TypeError) as exc:raise ValueError('Invalid landed charge') from exc
        if not amount.is_finite() or amount<0:raise ValueError('Invalid landed charge')
        item['landed_value']+=amount; item['landed_batch_ids'].append(bid)
    out=[]
    for item in lines.values():
        if item['invoice_quantity'] > item['quantity']:
            raise ValueError('Invoice allocation exceeds receipt quantity')
        complete = item['invoice_quantity']==item['quantity'] and bool(item['invoice_allocation_ids'])
        total=item['invoice_value']+item['landed_value'] if complete else None
        out.append({'receipt_line_id':item['receipt_line_id'],'currency':item['currency'],
                    'received_quantity':str(item['quantity']),
                    'approved_invoice_quantity':str(item['invoice_quantity']),
                    'invoice_value':str(item['invoice_value']),
                    'approved_landed_value':str(item['landed_value']),
                    'combined_receipt_cost_preview':str(total) if total is not None else None,
                    'unit_cost_preview':str(total/item['quantity']) if total is not None else None,
                    'invoice_allocation_ids':item['invoice_allocation_ids'],
                    'landed_batch_ids':item['landed_batch_ids'],
                    'status':'COMPLETE_UNPOSTED_PREVIEW' if complete else 'INCOMPLETE_INVOICE_ALLOCATION',
                    'movement_valuation_verified':False,'journal_posting_verified':False})
    return out
