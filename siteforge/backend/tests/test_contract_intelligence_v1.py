from datetime import datetime,timezone,timedelta
from decimal import Decimal
from types import SimpleNamespace as R
from app.domains.contracts.intelligence import build_intelligence

def test_currency_separation_effective_only():
    cs=[R(id=1,lifecycle='Active',currency='INR',original_value=Decimal('100')),
        R(id=2,lifecycle='Executed',currency='USD',original_value=Decimal('50'))]
    amendments=[R(id=5,contract_id=1,status='Executed',effective_version_id=9,currency='INR',delta_value=Decimal('10')),
                R(id=6,contract_id=2,status='Approved',effective_version_id=None,currency='USD',delta_value=Decimal('20'))]
    result=build_intelligence(4,cs,amendments,[],[],[],[])
    assert result['effective_value_by_currency']=={'INR':'110','USD':'50'}
    assert result['agreed_pending_effectiveness_by_currency']=={'USD':'20'}
    assert result['financials_certified_billing']['value'] is None

def test_undated_obligation_and_expired_security():
    now=datetime(2026,10,21,tzinfo=timezone.utc)
    r=build_intelligence(1,[R(id=1,lifecycle='Active',currency='INR',original_value=10)],[],
        [R(contract_id=1,status='Not Started',due_at=None)],[],
        [R(contract_id=1,status='Active',expires_at=now-timedelta(days=1))],[],as_of=now)
    assert r['obligations_missing_due_date']==1
    assert r['overdue_obligations']==0
    assert r['securities_expired']==1
