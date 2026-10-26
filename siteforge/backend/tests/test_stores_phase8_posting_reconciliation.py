from types import SimpleNamespace as Obj
from app.domains.stores_inventory.phase8_financial_reconciliation import trace_finance_evidence, finance_trace_summary


def trace(postings):
    return trace_finance_evidence([Obj(id=5, stock_posting_line_id=20)],
        [Obj(id=20, source_line_id=None, goods_receipt_line_id=30)],
        [Obj(id=30, goods_receipt_id=40, purchase_order_line_id=50)],
        [Obj(id=50, purchase_order_id=60)], [Obj(id=40, purchase_order_id=60)],
        [Obj(id=70, purchase_order_id=60, cost_code_id=80)], postings, {80})[0]


def test_missing_invoice_reference_is_blocked():
    row = trace([])
    assert row['reconciliation_status'].startswith('BLOCKED')
    assert row['invoice_link_scope'] == 'NONE'
    assert row['financial_value'] is None


def test_duplicate_invoice_reference_is_blocked():
    row = trace([Obj(id=90, purchase_order_id=60), Obj(id=90, purchase_order_id=60)])
    assert row['procurement_finance_reference_traced'] is False
    assert row['finance_invoice_posting_ids'] == [90]
    assert any('Duplicate' in x for x in row['blockers'])


def test_po_invoice_not_a_verified_journal():
    row = trace([Obj(id=90, purchase_order_id=60)])
    assert row['reconciliation_status'] == 'PO_FINANCE_REFERENCES_TRACED'
    assert row['invoice_link_scope'] == 'PURCHASE_ORDER_ONLY'
    assert row['accounting_posting_status'] == 'UNVERIFIED'
    assert not row['journal_verified']


def test_summary_never_claims_postings_verified():
    rows = [trace([Obj(id=90, purchase_order_id=60)]), trace([])]
    result = finance_trace_summary(rows)
    assert result['po_finance_references_traced'] == 1
    assert result['blocked_handovers'] == 1
    assert result['accounting_journals_verified'] == 0
