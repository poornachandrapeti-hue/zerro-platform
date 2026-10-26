from types import SimpleNamespace as Row
from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.phase5_material_balance import combine_material_balance


def trace(**kwargs):
    base = {'handover_id': 12, 'work_package_id': 4, 'item_id': 10, 'unit': 'EA',
            'issued_quantity': '10', 'ledger_posted_return_quantity': '2',
            'ledger_outstanding_quantity': '8', 'pending_custody_return_quantity': '1'}
    return {**base, **kwargs}


def usage(status='Verified', kind='Consumed', qty='3', **kwargs):
    base = dict(handover_id=12, work_package_id=4, item_id=10, unit='EA',
               status=status, usage_type=kind, quantity=Decimal(qty))
    return Row(**{**base, **kwargs})


def test_verified_and_pending_are_separate():
    data = combine_material_balance([trace()], [usage(), usage(status='Verified', kind='Installed', qty='2'), usage(status='Pending QA', qty='1')])[0]
    assert data['verified_consumed_quantity'] == '3'
    assert data['verified_installed_quantity'] == '2'
    assert data['pending_qa_consumed_quantity'] == '1'
    assert data['unallocated_outstanding_quantity'] == '2'
    assert data['physical_inventory_verified'] is False


def test_rejected_not_consumed():
    data = combine_material_balance([trace()], [usage(status='Rejected', qty='7')])[0]
    assert data['unallocated_outstanding_quantity'] == '8'
    assert data['rejected_evidence_quantity'] == '7'


@pytest.mark.parametrize('source,usages', [
    (trace(), [usage(qty='9')]),
    (trace(ledger_outstanding_quantity='10'), []),
    (trace(), [usage(handover_id=99)]),
    (trace(), [usage(item_id=99)]),
    (trace(), [usage(status='Unknown')]),
    (trace(), [usage(qty='NaN')]),
])
def test_fail_closed(source, usages):
    with pytest.raises(HTTPException) as exc:
        combine_material_balance([source], usages)
    assert exc.value.status_code == 409
