"""Phase 6 company custody contract checks without requiring a live database."""
from pathlib import Path
from fastapi import HTTPException
from app.domains.stores_inventory.transfers import TransferIn, CustodyConfirmationIn, payload
from app.domains.stores_inventory.models import StoresTransfer


def test_transfer_company_declarations():
    data = TransferIn(reference='TR-1', source_warehouse_id=1, destination_warehouse_id=2,
                      item_id=9, quantity='10', purpose='Send materials',
                      declared_owner_company_id=10, source_custodian_company_id=11,
                      destination_custodian_company_id=12)
    assert data.declared_owner_company_id == 10
    assert data.destination_custodian_company_id == 12


def test_custody_confirmation_requires_evidence_and_version():
    try:
        CustodyConfirmationIn(version=0, evidence='ok')
        assert False
    except ValueError:
        pass
    assert CustodyConfirmationIn(version=2, evidence='Signed receipt').version == 2


def test_transfer_model_uses_same_ledger():
    assert StoresTransfer.__tablename__ == 'stores_transfers'
    assert 'declared_owner_company_id' in StoresTransfer.__table__.columns
    assert 'custody_confirmed_by' in StoresTransfer.__table__.columns


def test_confirmation_not_claimed_as_title_or_stock():
    r = StoresTransfer(id=1, project_id=1, destination_project_id=2,
                       reference='T', source_warehouse_id=1, destination_warehouse_id=2,
                       item_id=2, quantity=1, status='Received', version=2,
                       purpose='Moving', created_by=1)
    result = payload(r)
    assert result['ownership_verified'] is False
    assert result['ownership_transferred'] is False
    assert result['inventory_posted'] is False


def test_confirmation_route_enforces_destination_company_and_independence():
    from app.domains.stores_inventory import transfers
    import inspect
    source = inspect.getsource(transfers.confirm_transfer_custody)
    assert 'u.company_id != row.destination_custodian_company_id' in source
    assert 'row.received_by' in source
    assert 'with_for_update()' in source
