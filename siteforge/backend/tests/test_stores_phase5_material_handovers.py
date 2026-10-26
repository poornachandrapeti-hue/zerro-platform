from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.material_handovers import classify_discrepancy, AcknowledgeIn, DispatchIn

def test_exact_receipt():
    assert classify_discrepancy(Decimal('10'), Decimal('10'), Decimal('0'), '') == 'Acknowledged'

def test_shortage():
    assert classify_discrepancy(10, 8, 0, 'Two missing') == 'Discrepancy'

def test_damage():
    assert classify_discrepancy(10, 10, 2, 'Crushed cartons') == 'Discrepancy'

@pytest.mark.parametrize('sent,received,damaged,note', [(10,11,0,'x'), (10,8,0,''), (10,8,9,'damaged'), (10,0,0,'x'), (0,0,0,'x'), ('NaN',0,0,'x')])
def test_invalid(sent,received,damaged,note):
    with pytest.raises(HTTPException): classify_discrepancy(sent,received,damaged,note)

def test_models():
    with pytest.raises(Exception): AcknowledgeIn(version=1,received_quantity=-1,damaged_quantity=0,evidence='valid')
    assert DispatchIn(posting_line_id=10,handover_reference='H-1',evidence='Signed delivery').posting_line_id == 10

def test_unique_and_nonledger():
    from app.domains.stores_inventory.models import StoresMaterialHandover
    assert StoresMaterialHandover.__tablename__ == 'stores_material_handovers'
    assert not hasattr(StoresMaterialHandover, 'on_hand')
    assert any(c.name == 'uq_stores_handover_issue_line' for c in StoresMaterialHandover.__table__.constraints)
