from pathlib import Path
from app.domains.stores_inventory.material_returns import _return_posting_quantity, ensure_return_not_consumed
from app.domains.stores_inventory.models import StoresTransferReturnAllocation
from fastapi import HTTPException
from decimal import Decimal
import pytest

def test_transfer_return_model_references_one_destination_lot():
    assert StoresTransferReturnAllocation.__tablename__ == 'stores_transfer_return_allocations'
    assert hasattr(StoresTransferReturnAllocation, 'transfer_destination_lot_id')
    assert hasattr(StoresTransferReturnAllocation, 'original_issue_line_id')

def test_return_limit_blocks_over_return():
    class R: received_quantity = Decimal('4')
    class L: quantity = Decimal('10')
    with pytest.raises(HTTPException):
        _return_posting_quantity(R(), L(), Decimal('7'))

def test_return_cannot_overlap_construction_usage():
    with pytest.raises(HTTPException):
        ensure_return_not_consumed(10, 2, 4, 5)

def test_transfer_return_posts_through_existing_ledger_and_gate():
    code = (Path(__file__).resolve().parents[1] / 'app/domains/stores_inventory/material_returns.py').read_text()
    assert 'STORES_TRANSFER_LOT_RETURN_ENABLED' in code
    assert "stock._save(db, u, project, 'Return'" in code
    assert 'StoresTransferReturnAllocation(' in code
    assert 'if grn_origin:' in code
