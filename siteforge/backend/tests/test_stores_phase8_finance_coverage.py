from app.domains.stores_inventory.phase8_financial_reconciliation import finance_coverage_summary


def test_empty_finance_coverage_not_valued():
    result = finance_coverage_summary(0, 0, 0)
    assert result['finance_cost_codes'] == 0
    assert result['stores_to_finance_link_verified'] is False
    assert result['inventory_cost_valuation_verified'] is False


def test_even_full_project_finance_coverage_does_not_claim_stores_link():
    result = finance_coverage_summary(12, 7, 3)
    assert result['purchase_order_cost_allocations'] == 7
    assert result['supplier_invoice_verifications'] == 3
    assert result['stores_to_finance_link_verified'] is False
    assert result['inventory_cost_valuation_verified'] is False
