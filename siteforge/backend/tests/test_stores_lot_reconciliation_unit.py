"""Pure reconciliation guardrail unit tests; no running DB required."""
from decimal import Decimal
from types import SimpleNamespace
from app.domains.stores_inventory.lot_reconciliation import reconcile_line


def test_missing_qa_and_unregistered_lot_never_releases():
    result = reconcile_line(Decimal('10'), [], None, [])
    assert 'QA_CASE_MISSING' in result['flags']
    assert 'LOT_REGISTRATION_INCOMPLETE' in result['flags']
    assert not result['lot_issue_enabled']


def test_partial_qa_and_multiple_lots_explicitly_flagged():
    lots = [SimpleNamespace(quantity=Decimal('4')), SimpleNamespace(quantity=Decimal('6'))]
    qa = SimpleNamespace(pending_qty=Decimal('2'), accepted_qty=Decimal('5'), rejected_qty=Decimal('3'), quarantined_qty=Decimal('0'))
    result = reconcile_line(Decimal('10'), lots, qa, [SimpleNamespace(quantity=Decimal('5'), unit='EA')])
    assert result['qa']['accepted'] == '5'
    assert 'ACCEPTANCE_NOT_ATTRIBUTED_TO_LOTS' in result['flags']
    assert 'LEGACY_POSTINGS_NOT_LOT_ALLOCATED' in result['flags']
    assert result['legacy_posted_quantity_by_unit']['EA'] == '5'
    assert not result['lot_issue_enabled']
