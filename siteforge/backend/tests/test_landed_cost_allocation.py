from dataclasses import replace
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from app.domains.commercial_financials.landed_cost_allocation import ReceiptCostBasis, ApprovedLandedCharge, preview_landed_cost_allocation

NOW = datetime(2026,10,25,tzinfo=timezone.utc)
R1=ReceiptCostBasis(1,2,3,9,Decimal('10'),Decimal('50'),'INR')
R2=ReceiptCostBasis(2,2,3,9,Decimal('20'),Decimal('75'),'INR')
C=ApprovedLandedCharge('freight-1',2,3,'INR',Decimal('30.01'),'APPROVED','INV-1',44,NOW-timedelta(days=1),'freight')
def run(rs=None,cs=None):
    return preview_landed_cost_allocation(receipts=[R1,R2] if rs is None else rs,charges=[C] if cs is None else cs,organization_id=2,project_id=3,currency='INR',as_of=NOW)
def test_allocation_conserves_amount():
    result=run()
    assert result['status']=='UNPOSTED_FINANCE_PREVIEW'
    assert sum(Decimal(x['allocated_landed_charge']) for x in result['receipt_lines'])==Decimal('30.01')
    assert result['finance_source_verified'] is False
    assert result['journal_posting_verified'] is False

def test_order_independent():
    assert run([R2,R1]) == run([R1,R2])

@pytest.mark.parametrize('receipts,charges',[
    ([],[C]),([R1,R1],[C]),([replace(R1,project_id=4)],[C]),
    ([replace(R1,quantity=Decimal('NaN'))],[C]),
    ([replace(R1,purchase_unit_cost=Decimal('-1'))],[C]),
    ([R1],[]),([R1],[C,C]),([R1],[replace(C,status='DRAFT')]),
    ([R1],[replace(C,currency='USD')]),([R1],[replace(C,approved_at=NOW+timedelta(days=1))]),
    ([R1],[replace(C,amount=Decimal('0'))]),([R1],[replace(C,amount=Decimal('3.001'))]),
    ([R1],[replace(C,source_document='')]),([R1],[replace(C,approved_by=0)]),
])
def test_invalid_evidence_rejected(receipts,charges):
    with pytest.raises(ValueError):run(receipts,charges)
