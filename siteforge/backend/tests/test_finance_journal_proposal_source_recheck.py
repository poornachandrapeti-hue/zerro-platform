from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.domains.commercial_financials.movement_journal_proposals import verify_proposal_authority

class FakeQuery:
    def __init__(self, records, model):
        self.records, self.model = records, model
        self.filters = {}
    def filter_by(self, **filters):
        self.filters.update(filters)
        return self
    def order_by(self, *args): return self
    def limit(self, n): return self
    def all(self):
        return [r for r in self.records.get(self.model, []) if all(getattr(r,k,None)==v for k,v in self.filters.items())]
    def first(self):
        return next((r for r in self.records[self.model] if all(getattr(r,k,None)==v for k,v in self.filters.items())),None)
class FakeDB:
    def __init__(self, rows):self.rows=rows
    def query(self, model):return FakeQuery(self.rows,model)

def scenario(quantity='3',posted='Posted',kind='Issue',org=7,code_project=20):
    from app.domains.supply_chain.models import StockPostingLine, StockPosting
    from app.domains.commercial_financials.models import FinanceCostCode, FinanceInventoryCostingPolicy
    rows={StockPostingLine:[SimpleNamespace(id=5,posting_id=8,quantity=quantity)],
          StockPosting:[SimpleNamespace(id=8,project_id=20,organization_id=org,status=posted,kind=kind)],
          FinanceCostCode.id:[SimpleNamespace(id=4,project_id=code_project,organization_id=7)],
          FinanceInventoryCostingPolicy:[SimpleNamespace(project_id=20,organization_id=7,revision=1,status='Approved',approved_by=2,approved_at='now',costing_method='FIFO',currency='INR')]}
    proposal=SimpleNamespace(currency='INR',source_movement_line_id=5,lines=[{'cost_code_id':4,'debit':'15','credit':'0'}, {'cost_code_id':4,'debit':'0','credit':'15'}])
    return FakeDB(rows),proposal

def test_current_valid_references():
    db,p=scenario()
    assert verify_proposal_authority(db,20,7,p)

@pytest.mark.parametrize('kwargs',[
    {'quantity':'0'}, {'quantity':'NaN'}, {'posted':'Canceled'},
    {'kind':'Receipt'}, {'org':8}, {'code_project':99}
])
def test_stale_finance_or_inventory_references_block(kwargs):
    db,p=scenario(**kwargs)
    with pytest.raises(HTTPException) as exc:
        verify_proposal_authority(db,20,7,p)
    assert exc.value.status_code==409

@pytest.mark.parametrize('policy_changes',[{'status':'Draft'}, {'currency':'USD'}, {'approved_by':None}, {'costing_method':'UNKNOWN'}])
def test_finance_policy_must_be_current_and_approved(policy_changes):
    from app.domains.commercial_financials.models import FinanceInventoryCostingPolicy
    db,p=scenario()
    for k,v in policy_changes.items():
        setattr(db.rows[FinanceInventoryCostingPolicy][0],k,v)
    with pytest.raises(HTTPException) as exc:
        verify_proposal_authority(db,20,7,p)
    assert exc.value.status_code == 409
