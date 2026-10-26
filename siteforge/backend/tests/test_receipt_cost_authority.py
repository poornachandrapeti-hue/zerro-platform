from decimal import Decimal
from types import SimpleNamespace
from fastapi import HTTPException
from app.domains.commercial_financials.receipt_cost_authority import CreateAllocation, serialize, get_locked

def test_create_schema_accepts_decimal_quantity():
    v=CreateAllocation(goods_receipt_line_id=1,vendor_invoice_line_id=2,quantity='2.375',source_reference='FIN-123')
    assert v.quantity==Decimal('2.375')

def test_create_schema_rejects_zero_quantity():
    import pytest
    with pytest.raises(Exception):
        CreateAllocation(goods_receipt_line_id=1,vendor_invoice_line_id=2,quantity='0',source_reference='FIN-123')

def test_serializer_does_not_claim_journal_or_movement_posting():
    obj=SimpleNamespace(id=1,project_id=2,goods_receipt_line_id=3,vendor_invoice_line_id=4,
        quantity=Decimal('4'),currency='INR',unit_cost=Decimal('15.4'),status='Approved',
        source_reference='FIN-234',created_by=1,submitted_by=1,approved_by=2,approved_at=None)
    output=serialize(obj)
    assert output['receipt_cost_evidence_approved'] is True
    assert output['journal_posting_verified'] is False
    assert output['movement_valuation_verified'] is False

def test_missing_receipt_allocation_is_404():
    class Query:
        def filter_by(self,**kw):return self
        def with_for_update(self):return self
        def one_or_none(self):return None
    class DB:
        def query(self,*args):return Query()
    import pytest
    with pytest.raises(HTTPException) as e:get_locked(DB(),2,3,99)
    assert e.value.status_code==404
