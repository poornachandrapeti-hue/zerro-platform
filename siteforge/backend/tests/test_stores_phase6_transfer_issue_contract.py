from decimal import Decimal
from pathlib import Path
from fastapi import HTTPException
import pytest
from app.domains.stores_inventory.transfer_lot_issue import transfer_issue_limits, issue_transfer_lot


def test_valid_transfer_issue_limits():
    assert transfer_issue_limits(accepted='20', previously_issued='4', other_reservations='6',
        requested='3', active_remaining='5', balance_on_hand='17', balance_reserved='8') == Decimal('3')

@pytest.mark.parametrize('changes', [
    {'previously_issued': '21'},
    {'other_reservations': '18'},
    {'requested': '6'},
    {'balance_reserved': '2'},
    {'balance_on_hand': '2'},
    {'accepted': 'NaN'},
])
def test_transfer_issue_rejects_invalid_balances(changes):
    args = dict(accepted='20', previously_issued='4', other_reservations='6',
                requested='3', active_remaining='5', balance_on_hand='17', balance_reserved='8')
    args.update(changes)
    with pytest.raises(HTTPException) as error:
        transfer_issue_limits(**args)
    assert error.value.status_code == 409


def test_transfer_issue_default_off(monkeypatch):
    for name in ('STORES_TRANSFER_LOT_ISSUE_ENABLED', 'STORES_LOT_WRITER_CUTOVER',
                 'STORES_ATOMIC_LOT_ISSUE_ENABLED'):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(HTTPException) as error:
        issue_transfer_lot(1, 1, None, u=None, db=None)
    assert error.value.status_code == 503


def test_existing_ledger_and_provenance_used():
    module = Path(__file__).resolve().parents[1] / 'app/domains/stores_inventory/transfer_lot_issue.py'
    source = module.read_text()
    assert "stock._save(db, u, project, 'Issue'" in source
    assert 'StoresTransferIssueAllocation(' in source
    assert 'require_issue_authorization(' in source
    assert "'QAAcceptedPendingActivation'" in source
