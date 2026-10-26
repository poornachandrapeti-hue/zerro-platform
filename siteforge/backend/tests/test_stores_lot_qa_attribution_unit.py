from decimal import Decimal
import pytest
from app.domains.stores_inventory.lot_qa_attribution import available_to_attribute


def test_accepted_partials_allow_remaining():
    available_to_attribute({"Accepted": Decimal("6.000")}, {"unallocated": Decimal("4.000")}, "Accepted", Decimal("4.000"))


def test_cannot_exceed_qa_approved_quantity():
    with pytest.raises(ValueError, match="QA-approved"):
        available_to_attribute({"Accepted": Decimal("1.000")}, {"unallocated": Decimal("10.000")}, "Accepted", Decimal("2.000"))


def test_cannot_exceed_lot_quantity():
    with pytest.raises(ValueError, match="receipt-lot"):
        available_to_attribute({"Rejected": Decimal("8.000")}, {"unallocated": Decimal("2.000")}, "Rejected", Decimal("3.000"))


def test_cannot_post_unknown_disposition():
    with pytest.raises(ValueError, match="Invalid disposition"):
        available_to_attribute({}, {"unallocated": Decimal("4")}, "Revoked", Decimal("1"))
