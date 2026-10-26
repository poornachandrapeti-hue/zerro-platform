"""Phase 6 transfer custody contract checks; no PostgreSQL required."""
import inspect
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory import transfers
from app.domains.stores_inventory.models import StoresTransfer


def test_receipt_full_and_discrepancy():
    assert transfers.classify_receipt('10', '10', '0', '') == 'Received'
    assert transfers.classify_receipt('10', '8', '1', 'Damaged in transit') == 'Discrepancy'

@pytest.mark.parametrize('dispatched,received,damaged,note', [
    ('10','11','0','invalid'), ('10','8','9','invalid'), ('10','8','0',''),
    ('10','NaN','0','bad'), ('10','0','-1','bad'),
])
def test_invalid_receipt_rejected(dispatched,received,damaged,note):
    with pytest.raises(HTTPException):
        transfers.classify_receipt(dispatched,received,damaged,note)

def test_no_inventory_mutations_in_custody_router():
    source = inspect.getsource(transfers)
    assert 'from app.domains.supply_chain.models import StockBalance' not in source
    assert 'StockPosting(' not in source
    assert 'inventory_posted=False' in source
    assert 'with_for_update()' in source


def test_transfer_has_unique_reference_and_versions():
    assert StoresTransfer.__tablename__ == 'stores_transfers'
    assert hasattr(StoresTransfer,'version')
    assert hasattr(StoresTransfer,'approved_by')
    assert hasattr(StoresTransfer,'received_by')


def test_all_custody_routes_exposed():
    paths = {(r.path, tuple(sorted(r.methods))) for r in transfers.router.routes}
    assert any(p.endswith('/material-transfers') and 'POST' in m for p,m in paths)
    for suffix in ('decision','dispatch','receive'):
        assert any(p.endswith('/'+suffix) and 'POST' in m for p,m in paths)
