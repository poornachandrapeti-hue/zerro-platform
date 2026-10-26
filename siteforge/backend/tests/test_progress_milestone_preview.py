from types import SimpleNamespace as O
from app.domains.progress_monitoring.milestone_calculation import engineering_preview, procurement_preview

def test_engineering_revisions_are_not_double_counted():
    d=[O(id=7,record_status='Active',preparation='Prepared')]
    r=[O(drawing_id=7,release_state='Released',released_at='2026-01-01') for _ in range(3)]
    v=engineering_preview(d,r,{'prepared':30,'released':70})
    assert v['preview_percent']==100 and v['earned_percent'] is None

def test_engineering_no_release_evidence():
    v=engineering_preview([O(id=1,record_status='Active',preparation='Prepared')],[],{'prepared':30,'released':70})
    assert v['preview_percent']==30

def test_policy_validation_and_no_scope():
    v=engineering_preview([],[],{'prepared':50,'released':40})
    assert v['preview_percent'] is None and v['errors']

def test_receipt_quantities_and_no_acceptance_inference():
    o=[O(id=1,status='Issued')];l=[O(id=4,purchase_order_id=1,quantity='10')]
    r=[O(id=3,purchase_order_id=1,status='Posted')]
    rl=[O(id=5,goods_receipt_id=3,purchase_order_line_id=4,quantity='5')]
    v=procurement_preview(o,l,r,rl,{'ordered':20,'received':60,'accepted':20})
    assert v['preview_percent']==50 and v['earned_percent'] is None
    assert v['acceptance_status']=='NOT_AVAILABLE_IN_RECEIPT_RECORDS'

def test_over_receipt_blocks_preview():
    o=[O(id=1,status='Issued')]; l=[O(id=4,purchase_order_id=1,quantity='10')]
    r=[O(id=3,purchase_order_id=1,status='Posted')]
    rl=[O(id=5,goods_receipt_id=3,purchase_order_line_id=4,quantity='11')]
    v=procurement_preview(o,l,r,rl,{'ordered':20,'received':60,'accepted':20})
    assert v['preview_percent'] is None

def test_mismatched_receipt_po_blocks_preview():
    o=[O(id=1,status='Issued'),O(id=2,status='Issued')]
    l=[O(id=4,purchase_order_id=1,quantity='10')]
    r=[O(id=3,purchase_order_id=2,status='Posted')]
    rl=[O(id=5,goods_receipt_id=3,purchase_order_line_id=4,quantity='2')]
    v=procurement_preview(o,l,r,rl,{'ordered':20,'received':60,'accepted':20})
    assert v['preview_percent'] is None
