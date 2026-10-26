from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.domains.contracts.router import obligation_due, obligation_datetime, obligation_view

def test_undated_obligation_does_not_get_fabricated_due_date():
    assert obligation_due(None, 7) is None
    assert obligation_due(datetime(2026,10,21,tzinfo=timezone.utc),None) is None
    obj=SimpleNamespace(id=1,number='OB-001',contract_id=2,version_id=3,clause_reference='C1',description='Submit drawings',responsible_company_id=4,owner_user_id=5,trigger_name='NTP',trigger_at=None,due_days=7,due_at=None,required_evidence='signed submission',acceptance_required=True,status='Not Started',evidence=None,decision_evidence=None)
    result=obligation_view(obj)
    assert result['deadline_unresolved'] is True
    assert result['overdue'] is False

def test_triggered_date_computes_due_and_overdue():
    at=datetime(2026,10,21,12,tzinfo=timezone.utc)
    assert obligation_due(at,7)==at+timedelta(days=7)
    obj=SimpleNamespace(id=1,number='OB-002',contract_id=2,version_id=3,clause_reference='C2',description='Submit documents',responsible_company_id=4,owner_user_id=5,trigger_name='NTP',trigger_at=at,due_days=1,due_at=at+timedelta(days=1),required_evidence=None,acceptance_required=True,status='Not Started',evidence=None,decision_evidence=None)
    assert obligation_view(obj)['overdue'] is False
    obj.due_at=datetime(2020,1,1,tzinfo=timezone.utc)
    assert obligation_view(obj)['overdue'] is True
    obj.status='Accepted'
    assert obligation_view(obj)['overdue'] is False

def test_timezone_naive_date_is_rejected():
    with pytest.raises(HTTPException) as exc:
        obligation_datetime(datetime(2026,10,21))
    assert exc.value.status_code==422
