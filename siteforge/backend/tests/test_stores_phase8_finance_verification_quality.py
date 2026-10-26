"""Finance-owned PO invoice verification evidence never becomes a movement valuation."""
from datetime import datetime, timezone
from types import SimpleNamespace as O
from app.domains.stores_inventory.phase8_financial_reconciliation import trace_finance_evidence


def report(**invoice_overrides):
    invoice = dict(id=81, vendor_invoice_id=91, purchase_order_id=60,
                   cost_code_id=80, currency='INR', amount='1400.00',
                   posted_by=9, posted_at=datetime.now(timezone.utc))
    invoice.update(invoice_overrides)
    return trace_finance_evidence(
        [O(id=5, stock_posting_line_id=20)],
        [O(id=20, source_line_id=None, goods_receipt_line_id=30)],
        [O(id=30, goods_receipt_id=40, purchase_order_line_id=50)],
        [O(id=50, purchase_order_id=60)], [O(id=40, purchase_order_id=60)],
        [O(id=70, purchase_order_id=60, cost_code_id=80)],
        [O(**invoice)], {80})[0]


def test_complete_invoice_quality_remains_po_scope_only():
    row = report()
    assert row['finance_verification_evidence_status'] == 'FINANCE_PO_VERIFICATIONS_COMPLETE'
    assert row['invoice_link_scope'] == 'PURCHASE_ORDER_ONLY'
    assert row['financial_value'] is None
    assert row['journal_verified'] is False and row['movement_cost_verified'] is False


def test_invalid_money_is_not_accepted():
    for value in ('0', '-1', 'NaN', 'Infinity', None, 'abc'):
        row = report(amount=value)
        assert row['finance_verification_evidence_status'] == 'FINANCE_PO_VERIFICATIONS_INCOMPLETE'
        assert any('positive amount' in e for e in row['finance_verification_evidence_issues'])


def test_missing_audit_metadata_is_reported():
    row = report(posted_by=None, posted_at=None)
    assert any('approval audit metadata' in e for e in row['finance_verification_evidence_issues'])


def test_missing_source_invoice_and_currency_reported():
    row = report(vendor_invoice_id=None, currency=None)
    assert any('source invoice header' in e for e in row['finance_verification_evidence_issues'])
    assert any('currency missing' in e for e in row['finance_verification_evidence_issues'])
