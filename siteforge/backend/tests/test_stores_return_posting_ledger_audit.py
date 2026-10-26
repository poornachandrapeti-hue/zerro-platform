from app.domains.stores_inventory.return_posting_ledger_audit import assess


def sample():
    before={'read_only':True,'scope':[1,2,3], 'return_posting_id':None,
            'balance_key':[4,5,'KG'], 'on_hand':'50','reserved':'5',
            'return_requested_quantity':'10','return_received_quantity':'10',
            'source_posting_id':80,'posting_source_id':None,'posting_warehouse_id':None}
    after=dict(before,return_posting_id=22,return_status='Stock Posted',
               posting_status='Posted',posting_kind='Return',posting_line_count=1,
               posting_line_quantity='10',matching_posting_count=1,on_hand='60',
               posting_source_id=80,posting_warehouse_id=4)
    return before,after


def test_valid_delta():
    a,b=sample()
    assert assess(a,b,'10')['result']=='LEDGER_DELTA_PASS'


def test_double_posting_blocked():
    a,b=sample(); b['on_hand']='70'
    assert assess(a,b,'10')['result']=='FAIL_OR_INCONCLUSIVE'


def test_duplicate_source_postings_blocked():
    a,b=sample(); b['matching_posting_count']=2
    assert assess(a,b,'10')['result']=='FAIL_OR_INCONCLUSIVE'


def test_changed_scope_blocked():
    a,b=sample(); b['scope']=[1,99,3]
    assert assess(a,b,'10')['result']=='FAIL_OR_INCONCLUSIVE'


def test_missing_stock_posting_blocked():
    a,b=sample(); b['return_posting_id']=None
    assert assess(a,b,'10')['result']=='FAIL_OR_INCONCLUSIVE'


def test_missing_evidence_blocked():
    a,b=sample(); b['on_hand']=None
    assert assess(a,b,'10')['result']=='FAIL_OR_INCONCLUSIVE'


def test_unexpected_reservation_change_blocked():
    a,b=sample(); b['reserved']='6'
    assert assess(a,b,'10')['result']=='FAIL_OR_INCONCLUSIVE'


def test_wrong_source_posting_blocked():
    a,b=sample(); b['posting_source_id']=81
    assert assess(a,b,'10')['result']=='FAIL_OR_INCONCLUSIVE'

def test_wrong_warehouse_blocked():
    a,b=sample(); b['posting_warehouse_id']=99
    assert assess(a,b,'10')['result']=='FAIL_OR_INCONCLUSIVE'

def test_return_receipt_quantity_mismatch_blocked():
    a,b=sample(); b['return_received_quantity']='8'
    assert assess(a,b,'10')['result']=='FAIL_OR_INCONCLUSIVE'

def test_requested_quantity_changed_blocked():
    a,b=sample(); b['return_requested_quantity']='12'
    assert assess(a,b,'10')['result']=='FAIL_OR_INCONCLUSIVE'
