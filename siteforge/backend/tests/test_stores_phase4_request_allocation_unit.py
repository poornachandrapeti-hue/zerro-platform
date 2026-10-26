"""Non-database checks; live locking/permissions require PostgreSQL integration tests."""
from decimal import Decimal
from app.domains.stores_inventory.request_allocation import remaining_demand


def test_remaining_quantity():
    assert remaining_demand('100', '40.250') == Decimal('59.750')


def test_no_negative_remaining():
    assert remaining_demand('5', '7') == Decimal('0')


def test_decimal_precision():
    assert remaining_demand('0.3', '0.1') == Decimal('0.2')
