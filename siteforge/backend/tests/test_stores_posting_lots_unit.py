from decimal import Decimal
import pytest
from app.domains.stores_inventory.posting_lots import check_allocation

def test_allocation_within_line_and_lot():
    assert check_allocation(Decimal("2.000"), 10, 6, 5, 2)

def test_prevent_overallocation_of_posting_line():
    with pytest.raises(ValueError, match="posting"):
        check_allocation(3, 10, 8, 20, 0)

def test_prevent_overallocation_of_lot():
    with pytest.raises(ValueError, match="lot"):
        check_allocation(3, 10, 0, 5, 3)

def test_reject_zero_and_negative():
    with pytest.raises(ValueError):
        check_allocation(0, 10, 0, 10, 0)
