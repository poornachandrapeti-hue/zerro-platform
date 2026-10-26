from types import SimpleNamespace as Obj
from app.domains.stores_inventory.phase8_financial_reconciliation import trace_finance_evidence


def trace(invoices):
    return trace_finance_evidence([Obj(id=5, stock_posting_line_id=20)],
        [Obj(id=20, source_line_id=None, goods_receipt_line_id=30)],
        [Obj(id=30, goods_receipt_id=40, purchase_order_line_id=50)],
        [Obj(id=50, purchase_order_id=60)], [Obj(id=40, purchase_order_id=60)],
        [Obj(id=70, purchase_order_id=60, cost_code_id=80)], invoices, {80})[0]


def inv(id, header, code=80, curr='INR'):
    return Obj(id=id, purchase_order_id=60, vendor_invoice_id=header, cost_code_id=code, currency=curr)


def test_consistent_invoice_evidence_is_traced_without_valuation():
    result = trace([inv(1, 101), inv(2, 102)])
    assert result['procurement_finance_reference_traced'] is True
    assert result['finance_invoice_header_ids'] == [101, 102]
    assert result['invoice_currencies'] == ['INR']
    assert result['financial_value'] is None and not result['journal_verified']


def test_duplicate_invoice_header_blocks_trace():
    result = trace([inv(1, 101), inv(2, 101)])
    assert not result['procurement_finance_reference_traced']
    assert any('same supplier invoice' in s for s in result['blockers'])


def test_invoice_cost_code_mismatch_blocks_trace():
    result = trace([inv(1, 101, code=999)])
    assert not result['procurement_finance_reference_traced']
    assert any('cost code conflicts' in s for s in result['blockers'])


def test_mixed_invoice_currencies_block_trace():
    result = trace([inv(1, 101, curr='INR'), inv(2, 102, curr='USD')])
    assert not result['procurement_finance_reference_traced']
    assert any('inconsistent currencies' in s for s in result['blockers'])
