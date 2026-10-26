from types import SimpleNamespace as O
from app.domains.stores_inventory.phase8_financial_reconciliation import trace_finance_evidence


def record(grn_item=10, stock_item=10):
    return trace_finance_evidence(
        [O(id=1, stock_posting_line_id=2)],
        [O(id=2, source_line_id=None, goods_receipt_line_id=3, item_id=stock_item, unit='KG')],
        [O(id=3, goods_receipt_id=4, purchase_order_line_id=5)],
        [O(id=5, purchase_order_id=6)],
        [O(id=4, purchase_order_id=6, item_id=grn_item)],
        [O(id=7, purchase_order_id=6, cost_code_id=8)],
        [O(id=9, purchase_order_id=6, cost_code_id=8, vendor_invoice_id=10,
           amount=100, currency='INR', posted_by=4, posted_at='2026-10-24')], {8})[0]


def test_matched_receipt_can_trace_but_not_establish_movement_cost():
    r = record()
    assert r['procurement_finance_reference_traced']
    assert r['movement_valuation_authority'] == 'NOT_ESTABLISHED'
    assert r['journal_authority'] == 'NOT_ESTABLISHED'
    assert r['financial_value'] is None


def test_receipt_item_mismatch_blocks_finance_trace():
    r = record(grn_item=77)
    assert not r['procurement_finance_reference_traced']
    assert any('Goods receipt material differs' in b for b in r['blockers'])


def test_missing_parent_line_blocks_finance_trace():
    r = trace_finance_evidence([O(id=1, stock_posting_line_id=999)], [], [], [], [], [], []) [0]
    assert not r['procurement_finance_reference_traced']
    assert r['journal_verified'] is False
