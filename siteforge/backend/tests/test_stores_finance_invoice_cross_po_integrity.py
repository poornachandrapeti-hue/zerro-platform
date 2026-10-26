from types import SimpleNamespace as O
from app.domains.stores_inventory.phase8_financial_reconciliation import trace_finance_evidence


def _run(postings):
    return trace_finance_evidence(
        [O(id=1, stock_posting_line_id=2)],
        [O(id=2, item_id=1, unit='KG', source_line_id=None, goods_receipt_line_id=3)],
        [O(id=3, goods_receipt_id=4, purchase_order_line_id=5)],
        [O(id=5, purchase_order_id=6)], [O(id=4, purchase_order_id=6, item_id=1)],
        [O(id=7, purchase_order_id=6, cost_code_id=8)], postings)[0]


def invoice(i, po=6, header=100, code=8, currency='INR'):
    return O(id=i, purchase_order_id=po, vendor_invoice_id=header, cost_code_id=code,
             currency=currency, amount='120.00', posted_by=9, posted_at='2026-10-25')


def test_complete_unambiguous_invoice_evidence():
    row = _run([invoice(11)])
    assert row['finance_verification_evidence_status'] == 'FINANCE_PO_VERIFICATIONS_COMPLETE'
    assert row['journal_verified'] is False
    assert row['financial_value'] is None


def test_conflicting_cost_code_not_complete():
    row = _run([invoice(11, code=99)])
    assert row['finance_verification_evidence_status'] == 'FINANCE_PO_VERIFICATIONS_INCOMPLETE'
    assert any('cost code conflicts' in x for x in row['finance_verification_evidence_issues'])


def test_mixed_currency_not_complete():
    row = _run([invoice(11), invoice(12, header=101, currency='USD')])
    assert row['finance_verification_evidence_status'] == 'FINANCE_PO_VERIFICATIONS_INCOMPLETE'


def test_cross_po_invoice_header_reuse_not_complete():
    row = _run([invoice(11), invoice(12, po=999, header=100)])
    assert row['finance_verification_evidence_status'] == 'FINANCE_PO_VERIFICATIONS_INCOMPLETE'
    assert any('multiple purchase orders' in x for x in row['blockers'])


def test_same_po_duplicate_header_not_complete():
    row = _run([invoice(11), invoice(12)])
    assert row['finance_verification_evidence_status'] == 'FINANCE_PO_VERIFICATIONS_INCOMPLETE'
