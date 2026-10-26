from decimal import Decimal
from types import SimpleNamespace
from app.domains.commercial_financials.procurement_integration import amount_lines, COMMITTED_STATES

def test_invoice_decimal_math():
    rows=[SimpleNamespace(quantity=Decimal('2.125'),billed_unit_price=Decimal('100.50')),SimpleNamespace(quantity=Decimal('1'),billed_unit_price=Decimal('10.00'))]
    assert amount_lines(rows,'quantity','billed_unit_price')==Decimal('223.56250')

def test_draft_orders_not_committed():
    assert 'Draft' not in COMMITTED_STATES
    assert 'Cancelled' not in COMMITTED_STATES
    assert 'Superseded' not in COMMITTED_STATES
    assert 'Issued' in COMMITTED_STATES
