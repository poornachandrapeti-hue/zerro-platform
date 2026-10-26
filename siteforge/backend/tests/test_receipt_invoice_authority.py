from app.domains.commercial_financials.receipt_invoice_authority import classify_invoice_evidence

def row(i,c='INR',q='3',price='50'):
    return {'invoice_line_id':i,'currency':c,'quantity':q,'unit_price':price}

def test_no_invoice():
    assert classify_invoice_evidence(receipt_qty='5',matches=[])=='NO_FINANCE_VERIFIED_INVOICE_LINE'

def test_invalid_receipt():
    assert classify_invoice_evidence(receipt_qty='NaN',matches=[row(1)])=='INVALID_RECEIPT_QUANTITY'

def test_duplicate():
    assert classify_invoice_evidence(receipt_qty='5',matches=[row(1),row(1)])=='DUPLICATE_INVOICE_LINE'

def test_mixed_currency():
    assert classify_invoice_evidence(receipt_qty='5',matches=[row(1),row(2,'USD')])=='MIXED_INVOICE_CURRENCIES'

def test_invalid_values():
    assert classify_invoice_evidence(receipt_qty='5',matches=[row(1,q='0')])=='INVALID_INVOICE_LINE_VALUES'

def test_verified_po_evidence_not_valued_receipt():
    assert classify_invoice_evidence(receipt_qty='5',matches=[row(1)])=='PO_LINE_INVOICE_VERIFIED_RECEIPT_COST_UNALLOCATED'
