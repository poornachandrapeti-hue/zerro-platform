"""Catalogue decision permission is separate from master editing."""
import pytest
from app.domains.supply_chain.catalogue_authorization import can_approve_catalogue


@pytest.mark.parametrize("admin,permissions,expected", [
    (True, [], True),
    (False, ["procurement.catalogue.approve"], True),
    (False, ["procurement.master.edit"], False),
    (False, ["procurement.requisition.review"], False),
    (False, [], False),
    (False, None, False),
    (False, ["procurement.catalogue.approve", "procurement.master.edit"], True),
])
def test_catalogue_approval_permission(admin, permissions, expected):
    assert can_approve_catalogue(admin, permissions) is expected
