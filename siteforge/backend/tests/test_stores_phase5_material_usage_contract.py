from decimal import Decimal
from pathlib import Path
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.construction_material_usage import enforce_usage_limit, checked_quantity, UsageIn, VerifyIn


def test_quantity_limit_allows_exact_outstanding():
    enforce_usage_limit('10', '2', '3', '5')

@pytest.mark.parametrize('issued,returned,prior,new', [('10','2','4','5'), ('10','11','0','0'), ('3','0','3','1')])
def test_usage_never_exceeds_posted_outstanding(issued, returned, prior, new):
    with pytest.raises(HTTPException) as error:
        enforce_usage_limit(issued, returned, prior, new)
    assert error.value.status_code == 409

@pytest.mark.parametrize('quantity', ['NaN', 'Infinity', '-0.01'])
def test_bad_source_quantity_rejected(quantity):
    with pytest.raises(HTTPException): checked_quantity(quantity)

def test_usage_requires_evidence_and_positive_quantity():
    with pytest.raises(Exception): UsageIn(handover_id=1, usage_type='Installed', quantity=Decimal('0'), evidence_key='install-01', evidence='Evidence attached')
    valid = UsageIn(handover_id=1, usage_type='Installed', quantity=Decimal('1'), evidence_key='install-01', evidence='Evidence attached')
    assert valid.quantity == Decimal('1')

def test_verification_decisions_restricted():
    with pytest.raises(Exception): VerifyIn(version=1, decision='Approved', note='review complete')

def test_migration_single_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    root = Path(__file__).resolve().parents[1]
    heads = ScriptDirectory.from_config(Config(str(root / 'alembic.ini'))).get_heads()
    assert heads == ['a5f15015c001']
