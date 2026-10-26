from decimal import Decimal
from types import SimpleNamespace
from fastapi import HTTPException
import pytest
from app.domains.stores_inventory.transfer_posting_readiness import validate_destination_lot_plan


def case(**changes):
    data = dict(status='Received', discrepancy_status='Resolved',
                destination_custodian_company_id=None, custody_confirmed_by=None, quantity=Decimal('4'))
    data.update(changes)
    return SimpleNamespace(**data)


def source(**changes):
    data = dict(status='Planned', source_posting_id=None, quantity=Decimal('4'))
    data.update(changes)
    return SimpleNamespace(**data)


def test_valid_unposted_plan():
    assert validate_destination_lot_plan(case(), source()) is None

@pytest.mark.parametrize('transfer,lineage', [
    (case(status='Dispatched'), source()),
    (case(discrepancy_status='Escalated'), source()),
    (case(destination_custodian_company_id=10), source()),
    (case(), None),
    (case(), source(source_posting_id=44)),
    (case(), source(quantity=Decimal('3'))),
])
def test_rejects_unsafe_plans(transfer, lineage):
    with pytest.raises(HTTPException) as exc:
        validate_destination_lot_plan(transfer, lineage)
    assert exc.value.status_code == 409


def test_stock_posting_stays_blocked():
    from pathlib import Path
    code = (Path(__file__).resolve().parents[1] / 'app/domains/stores_inventory/transfer_posting_readiness.py').read_text()
    assert 'raise HTTPException(503,' in code
    assert "status='PendingPostingAndQA'" in code
