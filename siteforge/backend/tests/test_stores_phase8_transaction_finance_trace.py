from types import SimpleNamespace as Obj
from app.domains.stores_inventory.phase8_financial_reconciliation import trace_finance_evidence

def test_explicit_po_and_finance_allocation_is_evidence_not_valuation():
    result = trace_finance_evidence([Obj(id=5, stock_posting_line_id=20)],
        [Obj(id=20, source_line_id=10, goods_receipt_line_id=None), Obj(id=10, source_line_id=None, goods_receipt_line_id=30)],
        [Obj(id=30, goods_receipt_id=40, purchase_order_line_id=50)],
        [Obj(id=50, purchase_order_id=60)], [Obj(id=40, purchase_order_id=60)],
        [Obj(id=70, purchase_order_id=60, cost_code_id=80)],
        [Obj(id=90, purchase_order_id=60)])[0]
    assert result['procurement_finance_reference_traced'] is True
    assert result['finance_cost_code_id'] == 80
    assert result['finance_invoice_posting_ids'] == [90]
    assert result['financial_value'] is None
    assert result['movement_cost_verified'] is False

def test_missing_receipt_line_fails_closed():
    result = trace_finance_evidence([Obj(id=5, stock_posting_line_id=20)],
        [Obj(id=20, source_line_id=None, goods_receipt_line_id=None)], [], [], [], [], [])[0]
    assert result['purchase_order_id'] is None
    assert result['procurement_finance_reference_traced'] is False

def test_mismatched_po_rejected():
    result = trace_finance_evidence([Obj(id=5, stock_posting_line_id=20)],
        [Obj(id=20, source_line_id=None, goods_receipt_line_id=30)],
        [Obj(id=30, goods_receipt_id=40, purchase_order_line_id=50)],
        [Obj(id=50, purchase_order_id=60)], [Obj(id=40, purchase_order_id=61)], [], [])[0]
    assert result['purchase_order_id'] is None
    assert not result['procurement_finance_reference_traced']

def test_duplicate_finance_allocation_fails_closed():
    result = trace_finance_evidence([Obj(id=5, stock_posting_line_id=20)],
        [Obj(id=20, source_line_id=None, goods_receipt_line_id=30)],
        [Obj(id=30, goods_receipt_id=40, purchase_order_line_id=50)],
        [Obj(id=50, purchase_order_id=60)], [Obj(id=40, purchase_order_id=60)],
        [Obj(id=70, purchase_order_id=60, cost_code_id=80),Obj(id=71, purchase_order_id=60, cost_code_id=81)], [])[0]
    assert result['finance_cost_code_id'] is None
    assert not result['procurement_finance_reference_traced']

def test_finance_allocation_rejected_when_cost_code_not_in_project():
    result = trace_finance_evidence([Obj(id=5, stock_posting_line_id=20)],
        [Obj(id=20, source_line_id=None, goods_receipt_line_id=30)],
        [Obj(id=30, goods_receipt_id=40, purchase_order_line_id=50)],
        [Obj(id=50, purchase_order_id=60)], [Obj(id=40, purchase_order_id=60)],
        [Obj(id=70, purchase_order_id=60, cost_code_id=80)], [], {81})[0]
    assert result['finance_cost_code_id'] is None
    assert result['procurement_finance_reference_traced'] is False
    assert any('Finance cost code' in reason for reason in result['blockers'])

def test_cyclic_stock_line_chain_is_blocked():
    result = trace_finance_evidence([Obj(id=5, stock_posting_line_id=20)],
        [Obj(id=20, source_line_id=21, goods_receipt_line_id=None),
         Obj(id=21, source_line_id=20, goods_receipt_line_id=None)], [], [], [], [], [])[0]
    assert result['procurement_finance_reference_traced'] is False
    assert any('cycle' in reason for reason in result['blockers'])

def test_missing_stock_ancestor_is_explained():
    result = trace_finance_evidence([Obj(id=5, stock_posting_line_id=20)],
        [Obj(id=20, source_line_id=99, goods_receipt_line_id=None)], [], [], [], [], [])[0]
    assert any('incomplete' in reason for reason in result['blockers'])
