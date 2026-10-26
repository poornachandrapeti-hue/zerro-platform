"""Fail-closed Phase 6 transfer posting preflight; no PostgreSQL required."""
from types import SimpleNamespace
from app.domains.stores_inventory.transfer_posting_readiness import checked_balance, evaluate_transfer_posting


def transfer(**changes):
    values = dict(id=1, project_id=1, destination_project_id=1, status='Received',
                  discrepancy_status='Not Required', dispatched_quantity='5',
                  received_quantity='5', damaged_quantity='0',
                  destination_custodian_company_id=None, custody_confirmed_by=None)
    values.update(changes)
    return SimpleNamespace(**values)


def balance(on='20', reserved='2'):
    return SimpleNamespace(on_hand=on, reserved=reserved)


def test_corrupt_aggregate_balances_fail_closed():
    for on, reserved in [('1','2'),('-1','0'),('NaN','0'),('2','Infinity')]:
        available, error = checked_balance(on, reserved)
        assert available is None and error


def test_fully_received_still_blocks_unimplemented_ledger(monkeypatch):
    monkeypatch.setenv('STORES_ATOMIC_TRANSFER_POSTING_ENABLED','true')
    monkeypatch.setenv('STORES_LOT_WRITER_CUTOVER','true')
    result = evaluate_transfer_posting(transfer(),source_balance=balance(), destination_balance=balance())
    assert result['eligible_for_posting'] is False
    assert any('lot attribution' in s for s in result['blockers'])


def test_shortage_and_damage_require_resolution():
    result = evaluate_transfer_posting(transfer(status='Discrepancy', discrepancy_status='Open',
                    received_quantity='4', damaged_quantity='1'), source_balance=balance())
    assert any('fully received' in s for s in result['blockers'])
    assert any('discrepancy' in s.lower() for s in result['blockers'])


def test_cross_project_requires_provenance_migration():
    result=evaluate_transfer_posting(transfer(destination_project_id=3),source_balance=balance())
    assert any('Inter-project' in s for s in result['blockers'])


def test_insufficient_source_balance():
    result=evaluate_transfer_posting(transfer(),source_balance=balance('5','3'))
    assert any('unreserved stock' in s for s in result['blockers'])


def test_custody_confirmation_required_if_declared():
    result=evaluate_transfer_posting(transfer(destination_custodian_company_id=10),source_balance=balance())
    assert any('custody confirmation' in s for s in result['blockers'])
