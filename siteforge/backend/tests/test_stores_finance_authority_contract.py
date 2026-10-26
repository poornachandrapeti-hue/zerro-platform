from app.domains.stores_inventory.phase8_financial_reconciliation import finance_authority_contract


def test_authority_does_not_confuse_invoices_and_journals():
    matrix = finance_authority_contract()
    assert matrix['purchase_order_cost_code']['available'] is True
    assert matrix['supplier_invoice_verification']['scope'] == 'purchase_order'
    assert matrix['movement_valuation']['available'] is False
    assert matrix['accounting_journal']['available'] is False
    assert matrix['movement_cost_verified'] is False
    assert matrix['journal_posting_verified'] is False


def test_future_finance_contract_identifies_necessary_keys():
    matrix = finance_authority_contract()
    assert 'stock_posting_line_id' in matrix['movement_valuation']['required_keys']
    assert 'costing_method' in matrix['movement_valuation']['required_keys']
    assert 'journal_entry_id' in matrix['accounting_journal']['required_keys']
    assert 'project_id' in matrix['accounting_journal']['required_keys']
