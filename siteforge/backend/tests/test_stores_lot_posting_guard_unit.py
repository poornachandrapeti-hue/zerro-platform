from datetime import date
from decimal import Decimal
import pytest
from app.domains.stores_inventory.lot_posting_guard import LotIssueSnapshot, LotPostingBlocked, verify_issue


def sample(**updates):
    data = dict(lot_id=3, project_id=4, warehouse_id=5, item_id=6, owner_company_id=7,
                stock_unit='PCS', posted_receipt_quantity=Decimal('10'),
                posted_issue_quantity=Decimal('2'), posted_return_quantity=Decimal('1'),
                qa_accepted_quantity=Decimal('10'), reserved_lot_quantity=Decimal('3'),
                expiry_date=None, qa_current=True, condition='Serviceable',
                posting_coverage_complete=True, legacy_balance_reconciled=True)
    data.update(updates)
    return LotIssueSnapshot(**data)


def check(snapshot=None, quantity='2', **kwargs):
    values = dict(project_id=4, warehouse_id=5, item_id=6, owner_company_id=7, stock_unit='PCS', today=date(2026,10,23))
    values.update(kwargs)
    return verify_issue(snapshot or sample(), quantity=quantity, **values)


def test_valid_available_balance():
    result = check()
    assert result['available_before_issue'] == 6
    assert result['available_after_issue'] == 4


@pytest.mark.parametrize('changes', [
    {'qa_current': False}, {'condition':'Damaged'},
    {'posting_coverage_complete': False}, {'legacy_balance_reconciled': False},
    {'expiry_date': date(2026, 10, 22)}, {'qa_accepted_quantity': Decimal('8')},
    {'posted_issue_quantity': Decimal('11')}, {'posted_return_quantity': Decimal('3')},
])
def test_reject_unverified_lots(changes):
    with pytest.raises(LotPostingBlocked): check(sample(**changes))


@pytest.mark.parametrize('quantity', ['7', '0', '-1', 'NaN', '1.2345'])
def test_reject_bad_quantities(quantity):
    with pytest.raises(LotPostingBlocked): check(quantity=quantity)


def test_owner_scope_enforced():
    with pytest.raises(LotPostingBlocked): check(owner_company_id=999)
