import pytest
from app.domains.stores_inventory.outbound_lot_allocations import validate_outbound_allocation

def test_valid_issue():
    validate_outbound_allocation("Issue", 3, 10, 2, 12, 5)

def test_double_allocation_blocked():
    with pytest.raises(ValueError):
        validate_outbound_allocation("Issue", 9, 10, 2, 12, 0)

def test_source_capacity_blocked():
    with pytest.raises(ValueError):
        validate_outbound_allocation("Issue", 4, 10, 0, 12, 10)

def test_unsupported_kind_blocked():
    with pytest.raises(ValueError):
        validate_outbound_allocation("Transfer", 1, 10, 0, 10, 0)
