from types import SimpleNamespace as S
from app.domains.progress_monitoring.procurement_acceptance import procurement_accepted_preview,allocation_errors

def fixtures(status='Approved',accepted=6):
    orders=[S(id=1,status='Issued')];lines=[S(id=11,purchase_order_id=1,quantity=10)]
    receipts=[S(id=21,purchase_order_id=1,status='Posted')]
    rlines=[S(id=31,goods_receipt_id=21,purchase_order_line_id=11,quantity=10)]
    inspections=[S(id=41,goods_receipt_id=21,status=status)]
    dispositions=[S(inspection_id=41,goods_receipt_line_id=31,to_state='Accepted',quantity=accepted),S(inspection_id=41,goods_receipt_line_id=31,to_state='Rejected',quantity=10-accepted)]
    return orders,lines,receipts,rlines,inspections,dispositions

W={'ordered':20,'received':30,'accepted':50}
def test_quality_accepted_earned_fraction():
    result=procurement_accepted_preview(*fixtures(),W,{'11':100})
    assert result['errors']==[]
    assert result['preview_percent']==80.0

def test_pending_quality_never_earns_acceptance():
    result=procurement_accepted_preview(*fixtures(status='Pending Review'),W,{'11':100})
    assert result['preview_percent'] is None
    assert any('complete approved' in e for e in result['errors'])

def test_allocation_must_cover_scope():
    assert allocation_errors({'11':100},[11,12])
    assert allocation_errors({'11':50,'12':40},[11,12])
    assert not allocation_errors({'11':40,'12':60},[11,12])

def test_incomplete_disposition_blocks_earning():
    args=fixtures();args[-1].pop()
    assert procurement_accepted_preview(*args,W,{'11':100})['preview_percent'] is None

def test_over_receipt_blocks_earning():
    args=fixtures();args[3][0].quantity=11
    assert procurement_accepted_preview(*args,W,{'11':100})['preview_percent'] is None
