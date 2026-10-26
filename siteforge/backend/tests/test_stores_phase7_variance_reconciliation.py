from decimal import Decimal
from types import SimpleNamespace
from app.domains.stores_inventory.cycle_counts import reconcile_snapshot


def test_count_reconciliation_remains_blocked_with_perfect_historical_match():
    count = SimpleNamespace(id=7, warehouse_id=3, status='Verified')
    lines = [SimpleNamespace(receipt_lot_id=10, observed_quantity=Decimal('8'), recorded_lot_quantity=Decimal('8'))]
    balance = [SimpleNamespace(item_id=20, unit='EA', on_hand=Decimal('8'), reserved=Decimal('1'), version=2)]
    result = reconcile_snapshot(count, lines, balance)
    assert result['reconciliation_status'] == 'Blocked'
    assert result['independently_verified_count'] is True
    assert result['authorized_stock_adjustment'] is False
    assert result['observations'][0]['historical_difference'] == '0'
    assert result['observations'][0]['variance_verified'] is False
    assert result['warehouse_ledger_balances'][0]['on_hand'] == '8'


def test_partial_count_cannot_be_called_a_verified_variance():
    result = reconcile_snapshot(SimpleNamespace(id=1, warehouse_id=2, status='Submitted'), [], [])
    assert result['reconciliation_status'] == 'Blocked'
    assert len(result['blockers']) >= 3
    assert result['stock_adjustment_posted'] is False
