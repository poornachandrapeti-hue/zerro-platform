from datetime import date, timedelta
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.preservation import require_preservation_clear

class Result:
    def __init__(self, plan): self.plan = plan
    def scalar_one_or_none(self): return self.plan
class DB:
    def __init__(self,plan): self.plan = plan
    def execute(self, statement): return Result(self.plan)

def plan(condition='Good', offset=1):
    return SimpleNamespace(condition=condition, next_due_date=date.today()+timedelta(days=offset))

@pytest.mark.parametrize('condition,offset', [('Quarantined',1),('Attention',1),('Good',-1),('Unknown',1)])
def test_preservation_hold_rejects(condition, offset):
    with pytest.raises(HTTPException) as exc:
        require_preservation_clear(DB(plan(condition,offset)), lot_id=7,project_id=3,organization_id=2)
    assert exc.value.status_code == 409

def test_preservation_good_current_plan():
    require_preservation_clear(DB(plan()),lot_id=7,project_id=3,organization_id=2)

def test_unenrolled_lot_does_not_claim_verified_status():
    require_preservation_clear(DB(None),lot_id=7,project_id=3,organization_id=2)

def test_both_grn_writers_check_preservation():
    from pathlib import Path
    base=Path(__file__).resolve().parents[1]/'app/domains/stores_inventory'
    for name in ('lot_reservations.py','atomic_lot_issue.py'):
        source=(base/name).read_text()
        assert 'require_preservation_clear(db, lot_id=lot.id' in source
