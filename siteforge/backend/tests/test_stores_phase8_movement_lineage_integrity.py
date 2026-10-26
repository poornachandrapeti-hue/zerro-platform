"""Stock ancestry must remain consistent before Finance references can be traced."""
from types import SimpleNamespace as O
from app.domains.stores_inventory.phase8_financial_reconciliation import trace_finance_evidence


def trace(child_item=10, parent_item=10, child_unit='KG', parent_unit='KG'):
    return trace_finance_evidence(
        [O(id=5, stock_posting_line_id=20)],
        [O(id=20, source_line_id=10, goods_receipt_line_id=None, item_id=child_item, unit=child_unit),
         O(id=10, source_line_id=None, goods_receipt_line_id=30, item_id=parent_item, unit=parent_unit)],
        [O(id=30, goods_receipt_id=40, purchase_order_line_id=50)],
        [O(id=50, purchase_order_id=60)], [O(id=40, purchase_order_id=60)],
        [O(id=70, purchase_order_id=60, cost_code_id=80)], [O(id=90, purchase_order_id=60, cost_code_id=80)], {80})[0]


def test_matching_chain_traces_po_reference_only():
    row = trace()
    assert row['procurement_finance_reference_traced'] is True
    assert row['movement_cost_verified'] is False
    assert row['journal_verified'] is False


def test_mismatched_material_is_blocked():
    row = trace(parent_item=11)
    assert row['procurement_finance_reference_traced'] is False
    assert any('changes material item' in issue for issue in row['blockers'])


def test_mismatched_unit_is_blocked():
    row = trace(parent_unit='TON')
    assert row['procurement_finance_reference_traced'] is False
    assert any('changes unit' in issue for issue in row['blockers'])


def test_both_mismatches_are_reported():
    row = trace(parent_item=11, parent_unit='TON')
    assert not row['procurement_finance_reference_traced']
    assert len([x for x in row['blockers'] if 'ancestry changes' in x]) == 2
